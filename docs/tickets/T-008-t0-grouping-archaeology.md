# T-008 (T0) — texproc 輸入分組邏輯考古

狀態：DONE（2026-07-25 審查通過：行號抽查屬實（__n 雙底線 name_parser.py:163、CE 硬編碼層 221-238、arm 無 _orm regex 117-124）、diff 純文件、判例可複核。DEF-13–24 裁決見 D-06 附錄簽核紀錄；T1 待裁決後放行）
上游文件：`rust-workspace-design.md` D-06（本票就是它的補完）、`texture-pipeline-spec.md` §1.1
性質：**純考古票，不寫 Rust**。產出是文件，業主簽核後 T1 才開工。

## 背景

`texture-pipeline-spec.md` 涵蓋中間層與輸出層，但「檔名 → source type → TextureGroup」的分組規則不在規格內；`arm` 型別甚至不在 `suffix_settings.json`。此洞不補，T1 的核心型別無從定義。

## 工作內容

考古對象：`core/`（texture_manager / batch_processor 上游）、`utils/`、`suffix_settings.json`、UI 的檔案匯入路徑。把以下問題的**實際行為**（不是意圖）寫成 D-06 的補完章節，附 Python 檔名與行號：

1. **後綴匹配**：token 怎麼切（`_` 分隔？大小寫？位置限定結尾？）；`suffix_settings.json` 內 `_n`、`a`、`d` 這類高誤判鍵的實際匹配語意；同檔名命中多型別時的優先序。
2. **stem 提取與分組**：去除後綴後的 base name 如何生成；`removable_suffixes`（dx/gl）何時移除；同 stem 不同副檔名/解析度的合併規則；大小寫衝突。
3. **arm 偵測**：從哪裡來（寫死？獨立 pattern 表？），支援哪些拼法（arm/orm/rma…）。
4. **unknown 的去向**：進 `unknown[]` 之後有無下游行為。
5. **副檔名白名單**：接受哪些輸入格式；16-bit/EXR 是否真的能進來。
6. **邊界案例**：抓 3–5 個 `Z:\enchanted\KB3DTextures\4k` 的真實檔名 + 規格 DEF-07 提到的誤判名（`glass_normal` 等）做成判例表：輸入檔名 → 判定型別 → base name。

## 產出

1. `rust-workspace-design.md` D-06 節改寫為完整規則（含判例表與 Python 行號引用）。
2. 發現的缺陷比照規格格式編 `DEF-13+` 附在 D-06（例如 `a`/`d` 後綴誤判、大小寫問題），並標記「修 or 沿用」建議——**裁決權在業主**。

## DoD

- D-06 補完，判例表至少 10 條（含全部 DEF-07 誤判名）。
- 每條規則附來源行號，可被複核。
- 新 DEF 清單附建議裁決。
- 不含任何 Rust 程式碼變更。

## 執行結果（2026-07-25）

### 權威路徑

- 現行入口為 `main.py` 的 PySide6 UI。
- UI 檔案選取、模型抽取貼圖與直接 API 匯入最後都走
  `ui_pyside/texture_import.py` → `TextureManager.add_texture()` →
  `TextureNameParser.parse()`。
- `utils/` 沒有另一套分組邏輯。
- `ui/texture_import.py` 的 Tkinter `classify_textures()` /
  `group_textures()` 全 repo 無呼叫者，且規則與 active core 不同；D-06 已明確
  標為不得移植。

### 可重現探針

以 `Z:\enchanted\KB3DTextures\4k\KB3D_ENC_AtlasA_basecolor.png`
作可解碼內容，複製為各判例檔名後直接呼叫 active parser/manager。重點結果：

```text
glass_normal.png    -> normal / glass
single_nrm.png      -> normal / single
shingle_n.png       -> normal / shingle      (analyzer fallback)
plaza_a.png         -> diffuse / plaza
facade_d.png        -> diffuse / facade
packed_arm.png      -> arm / packed
packed_rm.png       -> arm / packed
packed_rma.png      -> arm / packed
packed_orm.png      -> diffuse / packed_orm  (本次像素結果；無 ORM pattern)
stone_normal_4k.png -> normal / stone
stone_4k_normal.png -> normal / stone_4k
```

同一 manager 依序加入 `same_normal.tif`、`same_normal.exr`，最後 group
`same/normal` 只留下 EXR，證明是輸入順序 last-write-wins。

格式入口另以本機 ImageMagick 7.1.1-8 Q16-HDRI 建立兩張 2×2 depth=16：

```text
probe_normal.tif depth=16 -> normal / probe
probe_normal.exr depth=16 -> normal / probe
```

兩者均成功進分組層。此結果不外推為 downstream decoder 全路徑保證；D-06
已把「picker filter」與「真正 decode whitelist」分開。

### D-06 產出摘要

- 判例表 21 列，其中 5 列為 KB3D 真實檔名，並含 DEF-07 的
  `glass_normal`、`single_nrm`、`shingle_n`。
- 後綴匹配、CE hardcoded priority、JSON key order、fallback、stem 清理、
  removable suffix、解析度位置、case-sensitive group、跨副檔名覆蓋、
  ARM spelling、unknown 下游與輸入格式入口均附 Python/JSON 行號。
- 新增 `DEF-13`–`DEF-24`，每項均列「修」建議並明標
  **裁決權仍在業主**。
- 本票只修改 Markdown；沒有 Rust/Python/JSON 行為或 dependency 變更。

### 驗證

```powershell
cd rebuild
.\run_gates.ps1 -SkipRC
```

結果：Rust workspace 48/48、T-003 dump hash、T-004 三組 golden、
T-005 request/MTL/schema-gate golden、Python asset_flow
28 passed / 2 skipped、RC smoke policy 3/3 全綠；RC 依本票範圍明確 skip，
最後 `ALL GATES PASSED`。

`git diff --check` 通過；最終 diff 只有：

```text
rebuild/rust-workspace-design.md
rebuild/tickets/T-008-t0-grouping-archaeology.md
```
