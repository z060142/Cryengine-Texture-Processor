# T-008 (T0) — texproc 輸入分組邏輯考古

狀態：OPEN
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
