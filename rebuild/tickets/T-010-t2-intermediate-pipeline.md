# T-010 (T2) — INT-* 中間層管線

狀態：OPEN
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
