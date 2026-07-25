# T-011 (T3) — OUT-* 輸出層管線

狀態：DONE（2026-07-25 審查通過：gate 全綠含 4K 錨點 7 fixture 實測（max diff 全 0）；island 生產碼唯二（INT-REFLECTION、output.rs:414 AO multiply）。審查備註 R1：AO multiply 中 AO 值以 raw（視為 linear 資料圖）參與、未過 decode——語意上合理但為實作選擇，由錨點 2 目視仲裁。審查備註 R2：Fox 發現舊 _displ 實為 GrayA 而非規格宣稱的 RGBA（DEF-11 no-op 之證據），規格 §5 該句應視為 erratum，Rust 維持真 RGBA 正確。錨點 2 樣本已轉 PNG 交業主，Q5 簽核 T5 前完成即可）
上游文件：`texture-pipeline-spec.md` §5（六個 exporter）、§10（錨點 2–7）；`rust-workspace-design.md` D-03/D-04/D-05、T3 節
前置：T-010 中間層。**開工前先確認舊 Python 版可跑批次**（錨點 7 需要對照組；uv 環境 + ImageMagick 均在，`core/batch_processor.py` 可程式化呼叫）。

## 工作內容

1. **六個 OUT-\* exporter**（§5），輸出檔名一律經 ce-schema（`_em`！`_ddna`/`_ddn` 特例照規格）：
   - `OUT-DIFF`：base=albedo→diffuse；`diff_format=="diffuse_ao"` 時 AO **Multiply（linear island，D-04；本票唯一 island）**；alpha → CopyOpacity。
   - `OUT-SPEC`：reflection→specular；fallback gray62（`generate_missing_spec` 預設 **true**），fallback 尺寸 albedo→diffuse→1024²，resize 用 T-009 的 OP-RESIZE（消滅規格提到的第二套 resize 實作）。
   - `OUT-DDNA`：normal 必要；flip G 按 `normal_flip_green`；gloss 中間層存在 → 寫入 alpha（**不再反相**，OP-COPYOPACITY 註記）→ `_ddna`，否則 `_ddn`。gloss 只認 intermediate（規格）。
   - `OUT-DISPL`：height 優先序照 §5；`normalize_height` → autolevel；輸出 RGBA 四通道同值；DEF-11 的 no-op 參數不移植。
   - `OUT-EMISSIVE`：只認 source emissive；brightness clamp [0.1,5.0]；fallback 黑（預設 false）。
   - `OUT-SSS`：DEF-12 修正——`sss_intensity`（乘數，clamp [0.1,3.0]）與 `sss_contrast`（fallback A 的對比係數，預設 0.8）拆為兩鍵；fallback A（colorize 膚色調）、fallback B（rgb(40,25,25)）預設均 false。
2. **Stage 2 編排**：六個 exporter 無相依，任意順序；resize 目標按 `output_resolution`，主副圖同目標（§5 共通規則）。
3. 設定鍵補齊 §7 全表 + `sss_contrast`、`dither`（僅接受、實作可為 no-op stub，錨點通過前不啟用）。
4. **錨點驗證**（§10，DoD 核心）：
   - 錨點 3：`_displ` R==G==B==A 逐像素。
   - 錨點 4：有 gloss → `_ddna`；無 → `_ddn`。
   - 錨點 5：小圖不放大（512 圖 + output_resolution=1024 → 尺寸不變）。
   - 錨點 6：六個 fallback 旗標預設值測試固定（spec=true 其餘 false）。
   - **錨點 7（直通等價）**：以 `fixtures/textures/KB3D_ENC_AtlasA_*` 為輸入，舊 Python 版（寫最小 driver script 呼叫 batch_processor，入 `tools/`）與 Rust 版同設定跑：不經 DEF 修正的輸出（_ddna、_displ、_spec、_diff 無 AO 模式）逐像素差 ≤ ±1/255。含 resize 的案例若超差，按 D-07 註記歸因後排除並記錄。
   - **錨點 2（刻意不等價）**：`diff_format=diffuse_ao` 時產出新舊對照樣本各一組，**交業主目視**（Q5）；DEF-05 金屬路徑同樣出對照樣本。
5. TIFF 輸出走 T-009 `write_tiff_lzw`。

## 明確禁止

- linear island 僅 OUT-DIFF 的 AO Multiply 一處。
- 不做 CLI/scan/process（T4）。不做 dither 實作。不新增依賴。
- 錨點 7 超差不准調 Rust 輸出湊舊版——先歸因（resize 語意 vs 漂移），漂移即 bug。

## DoD

- 錨點 1/3/4/5/6/7 測試全綠；`run_gates.ps1 -SkipRC` 全綠。
- 錨點 2 樣本輸出路徑貼回報，等業主目視（不擋結票條件以外的工作，但 T5 前必須簽核）。
- 回報：OUT 規則 × DEF 對照、錨點 7 的比對統計（每輸出的 max diff）。

## 執行結果（2026-07-25）

### 舊版對照線

- 依 `rebuild/fixtures/README.md` 從
  `Z:\enchanted\KB3DTextures\4k\KB3D_ENC_AtlasA_*.png` 重建本機
  ignored fixture；沒有把 4K 二進位檔加入 git。
- 新增最小 driver `tools/run_t011_python_baseline.py`，直接建立單一
  `TextureGroup`、呼叫舊 `BatchProcessor`、等待 thread 完成並驗證輸出數。
- `uv 0.6.14` + ImageMagick `7.1.1-8 Q16-HDRI` 實跑成功，舊暫存目錄
  在 batch 結束時清除。

### 實作

- 新增 `texproc::output`：
  - `TextureSettings` 補齊 §7、`arm_order`、`sss_contrast`、`dither`；
    `dither` 本票只接受並保持 deterministic no-op。
  - `OutputTextures` / `OutputImage` 是六個具 ce-schema filename 的
    in-memory `PlanarImage` slot。
  - `process_stage2()` 原子產生啟用的六個 output；`write_stage2_outputs()`
    是唯一落地邊界，統一呼叫 T-009 的 8-bit TIFF/LZW writer。
  - `TextureGroup` 正式補上 output layer。
- `output_resolution` 使用 `Original | Max(N)`，六條路徑都重用 T-009
  Lanczos、只縮不放的 `resize()`；主圖與 AO/alpha/gloss 各自套同一目標，
  組合前尺寸不一致即 error，不偷偷拉伸。
- 沒有修改 Cargo manifest/lock，沒有新增依賴、產品 CLI、scan/process
  或 dither 演算法。

### OUT 規則 × DEF 對照

| OUT 規則 | 本票行為 | 修正／約束 |
|---|---|---|
| `OUT-DIFF` | intermediate albedo → source diffuse；`diffuse_ao` 才套 AO；alpha copy | DEF-09：只在此處 decode base color → 乘 linear AO → encode |
| `OUT-SPEC` | reflection → source specular → gray62 fallback；尺寸 albedo/diffuse/1024² | 重用單一 OP-RESIZE；fallback 預設 true |
| `OUT-DDNA` | normal 必要；可選 flip G；只認 intermediate gloss，直接 copy alpha | DEF-10：不重做 INT resize、不二次 invert；ce-schema 選 `_ddna/_ddn` |
| `OUT-DISPL` | height → displacement → source height；可選 auto-level；輸出 RGBA 同值 | DEF-11：不移植 no-op channel 參數 |
| `OUT-EMISSIVE` | 只認 source emissive；brightness clamp 0.1–5；黑 fallback | ce-schema 固定 `_em`，不是 `_emissive` |
| `OUT-SSS` | source × intensity；fallback A colorize+contrast；fallback B rgb(40,25,25) | DEF-12：`sss_intensity` 0.1–3 與 `sss_contrast` 0.8 拆鍵 |

全 repo 的 transfer-function 呼叫點仍只落在：

1. T-010 `INT-REFLECTION`（DEF-08）。
2. T-011 `OUT-DIFF` AO multiply（DEF-09）。

資料圖、fallback、resize、alias、invert、copy-opacity、colorize、brightness
與 contrast 均不碰 transfer function。

### 錨點

- **錨點 1**：roughness 全 256 值進 Stage 1+2，`_ddna.a` 量化後逐像素
  `255-r`，mismatch `0/256`。
- **錨點 3**：`_displ` R/G/B/A 四 plane 逐像素相等。
- **錨點 4**：有 intermediate gloss → `_ddna.tif`；無 → `_ddn.tif`，
  gloss alpha 不再反相。
- **錨點 5**：512 寬圖、`Max(1024)` 結果仍為 512，不放大。
- **錨點 6**：空 group 的六輸出 fallback 結果固定為
  `[diff=None, spec=gray62, ddna=None, displ=None, emissive=None, sss=None]`；
  spec explicit flag 預設 true，其餘 generation flags false，六個 output
  enable flags則全 true。
- **錨點 7**：AtlasA 4K 真 fixture，`process_metallic=false`、
  `diff_format=albedo`；emissive/sss 以同一 basecolor 作直通 source，
  覆蓋六個 OUT exporter：

```text
output     max pixel diff
diff       0.000000000
spec       0.000000000
ddna       0.000000000
displ      0.000000000
emissive   0.000000000
sss        0.000000000
limit      0.003921569 (1/255)
```

舊 Python `_displ` 在本機 ImageMagick 實際是 Gray+Alpha 兩通道，不是規格
宣稱的 RGBA；這證明舊 `-channel RGB +channel` 確為 no-op。比較器只把舊
GrayA 語意展開成 `R=G=B=gray, A=alpha` 後比較，像素 max diff 仍為 0；
Rust 產物保持錨點 3 要求的真 RGBA，不回退複製 DEF-11。

### 錨點 2 目視樣本（待 Q5 簽核）

本批 AtlasA 原始 AO 是全白、metallic 是全黑，直接拿來無法顯示兩個刻意
差異。因此樣本保留 AtlasA basecolor/opacity，並各以 AtlasA roughness
內容複製成有訊號的 AO/metallic probe；probe input 一併留在同個 ignored
目錄，沒有偽稱是原始貼圖。

```text
root:
E:\CryEngineTextureProcessor\rebuild\fixtures\t011-anchor2

DEF-09 AO:
ao\old\KB3D_ENC_AtlasA_diff.tif
ao\rust\KB3D_ENC_AtlasA_diff.tif
max diff = 0.239215702

DEF-05 metallic:
def05\old\KB3D_ENC_AtlasA_diff.tif
def05\rust\KB3D_ENC_AtlasA_diff.tif
max diff = 0.952941179
```

這四張只供業主目視，不進 git；T5 前仍需 Q5 簽核。

### 驗證

```text
cargo test -p texproc --release --locked
  unit:       43/43
  fixture:     2/2

cargo clippy --workspace --all-targets --release --locked -- -D warnings
  PASS

cargo fmt --all -- --check
  PASS

.\run_gates.ps1 -SkipRC
  ce-schema:       5/5
  converter:      38/38
  CLI contract:    5/5
  texproc unit:   43/43
  texproc fixture: 2/2
  asset_flow:     28 passed / 2 skipped
  RC policy:       3/3
  T-003/T-004/T-005 goldens: PASS
  ALL GATES PASSED
```
