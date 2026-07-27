# T-010 (T2) — INT-* 中間層管線

狀態：DONE（2026-07-25 審查通過：gate 全綠 33/33；linear island 邊界抽查精確——sRGB helper 全 crate 僅 INT-REFLECTION 消費，gray62 有 decode（pipeline.rs:401-418）；錨點 1 全 256 值零差異）
上游文件：`texture-pipeline-spec.md` §3.1（順序）、§4（規則）、§8（DEF）；`rust-workspace-design.md` D-03（linear island）、D-06.7（簽核）、T2 節
前置：T-009 核心；DEF-05 分支優先序已簽核（albedo 專屬鍵 → diffuse+metallic linear burn → 裸 diffuse）。

## 工作內容

1. **TextureGroup 核心型別**：source slots（規格 §1.1 + unknown list）、intermediate slots（§1.2），全部持 in-memory `PlanarImage`——不寫暫存檔（DEF-02/06 就地消滅）。
2. **七條 INT-* 規則**（§4），修正照規格 §8 與簽核：
   - `INT-ARM`：通道拆解按 `arm_order` 設定（DEF-04 修正，預設 ARM；檔名 alias orm/rma 覆蓋預設，見 D-06.7 DEF-16）。
   - `INT-ALBEDO`：DEF-05 簽核順序；linear burn 化簡式 `max(0, diffuse − metallic_gray)`（§4 OP-LINEARBURN 註記）。
   - `INT-NORMAL`：DX/GL 檔名判定用規格第一層正則（`_` 邊界版）；**DEF-07 的第二層子字串比對不移植**。GL → flip G。無 normal 有 height → OP-NORMALFROMHEIGHT(strength)。
   - `INT-REFLECTION`：DEF-08 修正 = 真 `lerp(gray62, diffuse, metallic)`，**linear island**（gray62 也 decode，D-03）；DEF-03 修正 = 執行順序改為 gloss 先於 reflection（specular 分支讀 intermediate glossiness 時已存在）。
   - `INT-GLOSS`：§4 來源優先序四層照舊（含 roughness 反相）；in-memory，不再重複 resize（DEF-10 一併消滅）。
   - `INT-HEIGHT` / `INT-AO`：灰階化為真正的 in-memory 中間產物（不再是 DEF-06 的假別名）。
3. **執行順序**：Stage 1 依賴圖 = ARM → ALBEDO → NORMAL → GLOSS → REFLECTION → HEIGHT → AO（GLOSS 提前是 DEF-03 修正，其餘照 §3.1）。
4. 設定鍵：`process_metallic`、`normal_from_height_strength`、`arm_order`（§7 + D-08）。

## 測試（DoD 核心）

- **錨點 1**：合成 roughness 圖進管線 → intermediate glossiness 量化後逐像素 == 255−roughness（全 256 值覆蓋）。
- **DEF-08 island**：純黑 metallic → reflection == gray62；純白 → == diffuse；中間值 → linear 域 lerp 手算比對；並驗 gray62 有 decode（0.5 metallic 的結果 ≠ encoded 域 lerp）。
- **DEF-05**：diffuse+metallic 組走 linear burn；albedo 鍵存在時勝出；裸 diffuse 仍別名。
- **DEF-03**：specular 分支能讀到已生成的 glossiness（非 None 等價情境）。
- `arm_order` 三種排列各一測試；DX/GL 檔名判定含 DEF-07 誤判名（`glass_normal` 必須判 DX 預設，不受 `gl` 子字串影響）。
- 記憶體不落地：整條 Stage 1 跑完 temp 目錄零檔案（測試斷言）。

## 明確禁止

- 不做 OUT-*（T3）。不做 CLI。不新增依賴。
- linear island 僅限 DEF-08 此一處（DEF-09 在 T3）；其他運算禁止 transfer function。

## DoD

- 上述測試全綠；`run_gates.ps1 -SkipRC` 全綠。
- 回報：INT 規則 × 修正 DEF 對照表、錨點 1 實跑輸出。

## 執行結果（2026-07-25）

### 實作

- 新增單一 `pipeline` module，公開 `TextureGroup`、完整 source/intermediate
  slots、`IntermediateSettings`、固定順序 `process_stage1()` 與可檢查的
  `Stage1Report`。source 影像一律是帶原始檔名 metadata 的 in-memory
  `PlanarImage`；沒有 path resolver、暫存檔或輸出編碼。
- `process_stage1()` 在工作副本完成七步後才一次替換 group intermediate，
  中途 error 不留下半套結果；trace 固定為：
  `ARM → ALBEDO → NORMAL → GLOSS → REFLECTION → HEIGHT → AO`。
- source slots 依 §1.1 含 `unknown[]`，另保留規格 INT 分支實際要求的
  `albedo` / `height` compatibility slots；intermediate 含 §1.2 六項與
  ARM 實際產生的 `roughness` / `metallic`。
- 設定只新增票面三鍵的 Rust 契約：`process_metallic=true`、
  `normal_from_height_strength=10.0`、`arm_order=ARM`。沒有修改
  Cargo manifest/lock，沒有新增依賴、CLI 或 OUT-*。

### INT 規則 × DEF 對照

| INT 規則 | 本票行為 | 修正 DEF |
|---|---|---|
| `INT-ARM` | ARM/ORM/RMA 拆 channel；`arm/orm/rma` terminal alias 覆蓋設定；`_rm/_ra` 報 diagnostic 後用設定 | DEF-04、DEF-16 |
| `INT-ALBEDO` | dedicated albedo → diffuse+metallic `max(0,diffuse-metallic_gray)` → naked diffuse | DEF-05、DEF-06 |
| `INT-NORMAL` | 只用第一層 `_` 邊界 DX/GL patterns；GL flip G；否則 DX；缺圖由 height/displacement Sobel 生成 | DEF-06、DEF-07 |
| `INT-GLOSS` | gloss source → existing intermediate gloss → ARM roughness invert → source roughness invert；無 resize/IO | DEF-03、DEF-10 |
| `INT-REFLECTION` | specular alias 或 metallic mask；gray62 與 diffuse 只在此規則做 decode → linear lerp → encode | DEF-03、DEF-08 |
| `INT-HEIGHT` | displacement/height 真正灰階成 in-memory buffer | DEF-06 |
| `INT-AO` | 保留 ARM AO，否則 source AO 真正灰階成 in-memory buffer | DEF-06 |

`glass_normal`、`single_nrm`、`shingle_n` 均測得走預設 DX，不移植
DEF-07 第二層的 `"gl" in filename`。reflection 的 specular 分支另由
report 證明讀取時 intermediate glossiness 已存在。

### 錨點 1 實跑

```text
input roughness u8:  0, 1, 2, ... 253, 254, 255
output glossiness: 255,254,253, ...   2,   1,   0
compared: 256 pixels
mismatches: 0
```

同組測試另覆蓋：

- DEF-08 metallic=0 → 量化後 `rgb(62,62,62)`；metallic=1 → diffuse；
  metallic=0.5 與手算 linear-domain lerp 誤差 ≤ 1e-6，且明確不等於
  encoded-domain lerp。
- DEF-05 三分支優先序、ARM/ORM/RMA 三設定與 filename override、
  ambiguous alias diagnostic、DX/GL/誤判名、height/AO 灰階。
- 所有 source filename 指向專用 temp directory 路徑，整條 Stage 1
  完成後該目錄檔案數為 0。

### 驗證

```text
cargo test -p texproc --release --locked
  33 passed, 0 failed

cargo clippy --workspace --all-targets --release --locked -- -D warnings
  PASS

cargo fmt --all -- --check
  PASS

.\run_gates.ps1 -SkipRC
  ce-schema:       5/5
  converter:      38/38
  CLI contract:    5/5
  texproc:        33/33
  asset_flow:     28 passed / 2 skipped
  RC policy:       3/3
  T-003/T-004/T-005 goldens: PASS
  ALL GATES PASSED
```
