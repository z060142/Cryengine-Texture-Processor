# T-017 — 混合解析度貼圖組：免互相 match，副源硬縮就位

狀態：OPEN
業主裁決（2026-07-28）：「當同一組貼圖不同解析度時，不需要讓他們全部
match，只要目標有選就好。origin 就全部按原樣；選了目標，如果（目標）比
原圖更大就按原樣、更小就縮小、比例不對就硬縮。」

## 前置事實（開票偵察）

- 目標縮放 `ops::resize(image, max)`（ops.rs:98）**已經**符合裁決的單圖
  語意：源 ≤ 目標 → 原樣（絕不放大）；源 > 目標 → 等比縮到 max 邊。
  `OutputResolution::Original` → 原樣 clone。**此函數不動。**
- 真正擋人的是**組內合成點的尺寸相等硬檢查**（不合 → 整組報錯）：
  - `output.rs::multiply_ao_linear`（diff 的 AO 乘算，~466）
  - `output.rs` diff 的 alpha `copy_opacity` 併入（ops 層有無檢查需確認）
  - `output.rs::export_ddna` normal+gloss 併版（gloss 併入 normal 的 A 通道）
  - `pipeline.rs:448` INT-REFLECTION diffuse×metallic 尺寸檢查
  - stage1 其他 per-pixel 合成（albedo 變黑的 metallic 遮罩、AO 中間層等）
    ——**實作前全面盤點** `width !=`/`mismatch` 檢查點，逐一列入紀錄。

## 新語意

1. 每個輸出貼圖有**主源**（primary）：diff/albedo 鏈 = basecolor（diffuse）；
   ddna = normal；displ = height；emissive/sss = 各自源。輸出工作尺寸 =
   `resize_for_output(主源)`（語意不變：origin 原樣、目標只縮不放）。
2. **副源**（AO、alpha、gloss/roughness、metallic 遮罩等所有參與 per-pixel
   合成的第二輸入）不再要求與主源同尺寸：合成前**硬縮**（force resize）到
   主源當下的工作尺寸——含比例不同時的**非等比**拉伸（「比例不對就硬縮」）。
   新 op：`ops::resize_to(image, w, h)`（w/h 明確指定，可放大可縮小可變形；
   與既有 `resize` 的 filter 一致）。
3. 同尺寸輸入的行為**位元不變**（`resize_to` 在尺寸相等時必須直接 clone /
   no-op），確保既有 golden 與錨點零影響。
4. 尺寸檢查點改為：硬縮後仍不合（理論不可能）→ 保留 internal error。

## 驗收錨點

1. 混合解析度組（如 basecolor 4K、ao 1K、normal 2K、roughness 1K、
   height 1K），`Original`：處理成功無錯誤；diff = 4K（AO 上採樣就位）、
   ddna = 2K（roughness 就位）、displ = 1K——各輸出 = 各自主源原尺寸。
2. 同組 `Max(2048)`：diff = 2048、ddna = 2048、displ 維持 1K（小於目標
   不放大）。
3. 比例不合：base 512×512 + ao 256×128 → AO 非等比硬縮 512×512，合成
   成功；以梯度圖驗證 AO 乘算語意正確（非錯位/裁切）。
4. 回歸：全部既有測試不改而過（同尺寸路徑位元不變）；metallic 路徑
   （DEF-05/08、metal gate 測試）不受影響。
5. `run_gates.ps1` 全綠；GUI 測試另跑（閘門不含）。

## 明確禁止

- 不動 `ops::resize` 的目標縮放語意（不放大、等比、只縮小）。
- 不動 CLI 契約。不新增依賴。不加 UI 選項（無感修正，錯誤直接消失）。
- 不動 T-015 passthrough 與 T-016 判型。

## DoD

- 錨點全數通過；回報：盤點出的全部尺寸檢查點清單與各自的主源判定、
  `resize_to` 位置、新增測試名單。

## 實作紀錄（2026-07-28，Miss Fox）

### 新 op 位置

`ops::resize_to(image, width, height)`（`texproc/src/ops.rs`，緊接 `resize`
之後）。明確指定 w/h，可放大/縮小/非等比變形，filter 與 `resize` 一致
（Lanczos3）。**尺寸相等時直接 `clone`（no-op）**——同尺寸路徑位元不變，
既有 golden／anchor 零影響。`ops::resize` 目標縮放語意完全未動。

### 尺寸檢查點全面盤點與主源判定

grep `width !=` / `mismatch` / `ensure_same_dimensions`，逐點列出：

| # | 位置 | 合成 | 主源 (primary) | 副源→硬縮 | 處置 |
|---|------|------|----------------|-----------|------|
| 1 | `pipeline.rs` `process_albedo`（INT-ALBEDO，diffuse×metallic 遮罩變黑）| `effective_metallic` + `linear_burn` | **diffuse** | metallic、gloss → `resize_to(diffuse 尺寸)` | 合成前硬縮；`linear_burn`→`ensure_same_dimensions`(ops.rs:274) 保留為 internal error（不可達）|
| 2 | `pipeline.rs:448` `metal_reflection`（INT-REFLECTION，diffuse×metallic lerp）| 顯式 `diffuse.width != metallic.width` 檢查 + `effective_metallic` | **diffuse** | metallic、gloss → `resize_to(diffuse 尺寸)`（在 `process_reflection` 內硬縮後才傳入）| 硬縮後舊檢查保留為 internal error（不可達）|
| 3 | `output.rs:466` `multiply_ao_linear`（diff 的 AO 乘算）| 顯式 `base.width != ao.width` 檢查 | **albedo/diffuse**（= diff 工作尺寸 `image`）| ao → `resize_to(image 尺寸)` | 由 `resize_for_output` 獨立縮放改為硬縮到 `image` 當下尺寸；舊檢查保留為不可達 |
| 4 | `output.rs` `export_diff` alpha `copy_opacity` 併入 | `copy_opacity`→`ensure_same_dimensions`(ops.rs:72) | **albedo/diffuse**（`image`）| alpha → `resize_to(image 尺寸)` | 同上改硬縮；ops.rs:72 檢查保留為不可達 |
| 5 | `output.rs` `export_ddna` gloss `copy_opacity` 併入 A 通道 | `copy_opacity`→`ensure_same_dimensions`(ops.rs:72) | **normal**（`image`）| glossiness → `resize_to(image 尺寸)` | 同上改硬縮 |

其餘 ops 層通用檢查（`compatible_channels` ops.rs:259、`ensure_same_dimensions`
ops.rs:274、`copy_opacity` ops.rs:72）全部**保留**為內部保證，硬縮到位後
在上述路徑不可達。單源輸出（spec / displ / emissive / sss）無跨源 per-pixel
合成，不需改動。`batch.rs` 只從 header 估記憶體，無合成邏輯。

### 主源工作尺寸來源（未動 `resize_for_output`）

- diff/albedo 鏈 = `resize_for_output(basecolor/diffuse)`；ddna =
  `resize_for_output(normal)`；displ = `resize_for_output(height)`。語意凍結：
  Original→clone、Max(n)→只縮不放。副源一律 `resize_to` 到主源當下工作尺寸。

### 新增測試

- `ops.rs`：`op_resize_to_clones_on_match_and_forces_arbitrary_dims`
  （相等→clone、允許放大、非等比 2x2→4x1、0 維報錯）。
- `output.rs`：
  - `t017_anchor1_original_keeps_each_primary_size`（錨點 1：混合解析度
    Original，diff 512 / ddna 256 / displ 128）。
  - `t017_anchor2_max_caps_but_never_upscales`（錨點 2：Max(256)，diff 256 /
    ddna 256 / displ 維持 128 不放大）。
  - `t017_anchor3_aspect_mismatch_ao_hard_scaled_without_crop`（錨點 3：
    base 512×512 + AO 256×128 水平梯度 → 非等比硬縮 512×512，驗證乘算變黑
    隨梯度 left<mid<right、非裁切/錯位）。

### 驗證

- `cargo test -p texproc --release`：69 unit + t011 golden(bit-identical) +
  t012 CLI，全過。
- `.\run_gates.ps1`：ALL GATES PASSED。
- 未觸碰 texproc-gui。

## 審查紀錄（2026-07-28，協調者）

- 獨立重跑：texproc 69+2+4 測試全綠（t011 golden 位元不變，DEF-05/08 與
  metal gate 回歸未動而過）、`run_gates.ps1` 全綠（含 real-RC smoke）。
- 程式碼審：`resize_to` 尺寸相等短路 clone 屬實（同尺寸位元不變的保證成立）；
  五個合成點的主源判定正確（INT-ALBEDO / INT-REFLECTION 主源 diffuse、
  diff 的 AO/alpha 主源 albedo 工作圖、ddna 的 gloss 主源 normal）；舊尺寸
  檢查保留為不可達 internal error，符合票面。副源 resize 於 encoded domain
  執行，與 D-03 島嶼政策一致（縮放非既有 linear 島）。
- 錨點 1–3 測試（Original 各持主源尺寸 / Max 只縮不放 / 梯度 AO 非等比硬縮
  語意驗證）設計合格，含證偽性（梯度方向斷言排除錯位/裁切）。
