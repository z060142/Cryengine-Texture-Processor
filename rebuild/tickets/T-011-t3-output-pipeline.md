# T-011 (T3) — OUT-* 輸出層管線

狀態：OPEN
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
