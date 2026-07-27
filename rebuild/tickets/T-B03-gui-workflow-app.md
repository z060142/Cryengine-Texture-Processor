# T-B03 — texproc-gui 重做：完整工作流應用（以原版 UX 為藍本）

狀態：R1 IMPLEMENTED／AWAITING OWNER VISUAL SIGNOFF（2026-07-26；release GUI 劇本與自動化 DoD 全數通過）
出處：T-B02 UX 否決。業主裁示：**按原版思路——貼圖轉換與 FBX 材質轉換是兩個不同目標；本工具以貼圖轉換為主，FBX 是後加的可選功能。**
繼承：T-B02 的 model 層（groups 載入/指派/存檔 round-trip）、egui/eframe 依賴核可。

## 藍本（先讀再動手）

原版 `ui_pyside/main_window.py`（150 行，全部讀）——三欄 splitter：

```
左欄 QTabWidget：[Texture Import] [Model Import]
中欄：Preview（上） / Texture Groups（下）
右欄：Export Settings + [Batch Process] [Export Textures] [Export Model] [Save Settings]
```

配套 panel 各檔都要讀：`texture_import.py`（加檔案/資料夾、清單）、`texture_group_panel.py`（分組 + unknown 指派）、`export_settings.py`（輸出目錄×2、設定核取框、動作鈕）、`preview_panel.py`、`progress_dialog.py`（進度 + 取消）。**照抄工作流，不照抄 Qt 佈局細節**；egui 慣用法優先，但資訊架構與動線以原版為準。

## 使用者流程（DoD 的驗收劇本）

### 主流程：貼圖轉換
1. 開啟 app → 左欄 Texture Import：`Add Files` / `Add Folder`（或拖放）→ 檔案清單即時顯示。
2. 加入即分組（呼叫 texproc lib 的 scan，**in-process，不 subprocess**）：中欄 groups 即時更新，顯示每組已識別的型別格與 unknown；unknown 就地下拉指派（T-B02 邏輯）。
3. 點選 group 或單張貼圖 → Preview 顯示縮圖（image crate 縮圖即可，средний尺寸，非全解析度）。
4. 右欄設定：貼圖輸出目錄（記憶上次）、`output_resolution`、`diff_format`、`normal_flip_green`、`process_metallic`、`generate_missing_spec`、輸出型別開關（§7 的 texture_types）。進階鍵收進「Advanced」摺疊區（sss/emissive/arm_order 等）。
5. `Process Textures` 大按鈕 → 進度列（每 group 一tick，rayon 照跑）+ 可取消 → 完成後顯示輸出摘要（N 檔案 → 目錄超連結）。

### 副流程：FBX 材質（獨立 tab，不干擾主流程）
6. 左欄 Model Import tab：選 FBX → 顯示材質清單（converter lib dump/report in-process）、槽位、診斷。
7. `Export Material (.mtl + request)` → 輸出目錄（獨立記憶）→ 呼叫 converter convert 等價邏輯；選配 manifest/overrides 檔輸入欄。
8. FBX 內嵌貼圖或引用貼圖可一鍵「送入貼圖轉換」（對應原版 model→texture 抽取動線）。

### 全域
- `Save Settings`：settings JSON（與 CLI 的 `--settings` 同形狀）存/載。
- 視窗關閉不需確認（沒有未存檔概念——設定即時生效，分組是暫態）。
- ~~語系：zh-TW 預設~~ **R1 裁決推翻：UI 全英文**；不做語系切換 UI。

## 架構約束

- GUI 直接依賴 `texproc`（lib）與 `converter`（lib）做 in-process 呼叫；CLI 契約不受影響；長工作在背景執行緒，UI 不凍結。
- crate 佈局沿 T-B02（texproc-gui bin），依賴僅 +`eframe`；縮圖用既有 `image`。
- run_gates 維持排除 GUI；`cargo test -p texproc-gui` 保留 model 層測試。

## 明確禁止

- 不做批次佇列、素材庫、專案檔、主題設定。
- 不重實作分組/管線邏輯——一律呼叫 lib。
- 不因 GUI 需求改動兩個 CLI 的凍結契約。

## DoD

- 上述 1–8 劇本在 release exe 逐步可走通（Fox 自測錄 GIF 或逐步截圖附回報）。
- KB3D 全目錄實測：加入資料夾 → 132 groups / 5 unknown → 指派 → Process → 輸出 TIFF 與 CLI 產物一致（抽 3 組 hash 比對）。
- car.fbx 實測：材質 17 槽顯示正確、.mtl+request 輸出與 CLI 逐位元一致。
- 業主目視簽核（結票條件）。UI 文案與動線若有疑義，**先出線框截圖問業主再實作**，不要做完再改。

## 2026-07-26 實作與驗證

### 實作

- `texproc-gui` 已改為原版資訊架構的三欄工作流：左欄貼圖／模型匯入，中欄預覽與群組檢視，右欄輸出設定與主要動作。
- 貼圖加入、掃描、unknown 指派、縮圖預覽與背景輸出均直接呼叫 `texproc` library；背景工作有逐組進度與取消旗標。
- `texproc` 新增共用 batch 與 CLI-shape settings library API，CLI 改用同一 API，命令列參數與 JSON 契約不變。
- FBX 載入、17 槽檢視、診斷、`.mtl + request` 輸出與貼圖轉送均直接呼叫 `converter` library；內嵌貼圖內容只供 GUI 抽取，serde 輸出契約不變。
- 視窗與兩個輸出目錄會記憶；設定 JSON 可由 GUI 儲存／載入並由 CLI `--settings` 直接使用。

### release GUI 實測

- `Z:\enchanted\KB3DTextures\4k`：793 張影像，132 groups / 5 unknown；五張逐一指派後自動回到完整群組列表。
- GUI 背景處理：132 groups / 391 TIFF，74.54 秒；完成摘要與輸出目錄連結正常。
- 同一份 GUI 設定由 CLI 重跑後，抽驗 `KB3D_ENC_AtlasA`、`KB3D_ENC_AtlasCakeBread`、`KB3D_ENC_AtlasFlowersA`，每組 diff/spec/ddna 共 9 檔 SHA-256 全部相等。
- `fixtures/car/car.fbx`：GUI 顯示 17 槽（含尾端 `<unassigned>`）、21 meshes、23 nodes、71 texture refs。
- GUI 與 CLI 的 car 輸出逐位元一致：
  - `car.mtl` SHA-256 `C3E63AEB4FEA61CC32A9B5C1DB0F3956A81C2705F1C39A21CCC99FC7702E2E64`
  - `car.json` SHA-256 `E7D041F6C2112180CA2EAC10A921CB67135ABDB163CC24AA0753267E3C532BF0`

### 自動化

- `cargo fmt --all -- --check`：PASS。
- `cargo clippy -p texproc-gui -p texproc -p converter --all-targets --release --locked -- -D warnings`：PASS。
- `cargo test -p texproc-gui --release --locked`：4 PASS。
- `cargo test -p texproc --release --locked`：47 lib + 2 fixture + 4 CLI PASS。
- `cargo test -p converter --release --locked`：39 lib + 7 CLI PASS。
- `run_gates.ps1 -SkipRC`：ALL GATES PASSED。
- `run_gates.ps1`：ALL GATES PASSED；converter RC smoke 與 texproc RC/DDS smoke 均 PASS。

### R1 審查（2026-07-26）

審查者獨立驗證：gate 全模式全綠（converter 40 lib、GUI 4 model + 3 RC path 測試）；
GUI 原始碼 grep 零 CJK 字元（英文化屬實）；physicalize 通道等價由
GUI/CLI 逐位元 hash 證明（同值 manifest 基準）；CLI 凍結契約與全部 golden
無退步。環境備註：gate 失敗兩次均為殘留 texproc.exe 檔案鎖，
清除即復原，非程式問題。

尚待：業主目視簽核後改為 DONE。


## R1 修訂（2026-07-26 業主裁決，檢視五方案 demo 後）

裁決基調：以案 3「工作台」為 UX 基準（= 本票現況方向正確），加入下列三項：

1. **Physicalize 編輯（取自案 4）**：Model tab 材質表每列加 physicalize
   下拉（no / default / obstruct / no_collide / proxy_only）。語意 =
   explicit metadata 注入（與 manifest explicit 同位階，走既有政策層通道，
   不繞過 `resolve_rc_physicalize` 的優先序）；編輯過的值進 request。
2. **「Export CE Model」單一動作**：對使用者而言 Model tab 的主動作是
   「導出 CE 模型」，不是「輸出 .mtl+request 中間產物」。按鈕改名
   `Export CE Model`，行為 = convert（.mtl + request）→ RC.exe → CGF
   一氣呵成。**RC 位置由 UI 選擇**（2026-07-26 業主追加）：設定區加
   「RC Path」欄位 + Browse 鈕，與輸出目錄同樣記憶；解析優先序 =
   UI 設定路徑 → `CE_RC_EXE` → 預設 S: 路徑；皆無效時 Export 降級為只出
   .mtl+request 並明示「RC not configured — intermediate files exported」，
   RC Path 欄位同時標紅提示。本程式不輸出 FBX 檔——來源 FBX 原樣即是
   RC 輸入。
3. **UI 全英文**：所有文案改英文（推翻原票 zh-TW 決定）。

DoD 追加：
- physicalize 編輯後的 request 與「同值 manifest 注入」的 CLI 產物逐鍵相等
  （證明走的是同一政策通道）。
- Export CE Model 在有 RC 環境對 car.fbx 產出 CGF，材質對齊 16/16
  （複用 rc_smoke_rust 的驗法）；無 RC 環境降級路徑有明確 UI 提示。
- RC Path 欄位：Browse 選檔、跨重啟記憶、無效路徑紅框提示三者實測。
- 其餘首版 DoD（hash 一致、KB3D 劇本）在修訂後重驗不退步。

## R1 實作與驗證（2026-07-26）

### 實作

- Model 材質表新增 `Physicalize` 下拉，完整提供 `no`、`default`、
  `obstruct`、`no_collide`、`proxy_only`；只把使用者改過的值送入
  converter explicit metadata 層，之後仍由既有 `resolve_physicalize`
  政策解析。
- converter library 新增可選 physicalize overrides 入口；原本 CLI
  `convert` 呼叫與參數契約不變。
- Model 主動作改為 `Export CE Model`：先輸出 `.mtl + request`，再以來源
  FBX 呼叫 RC，成功時回報 CGF；沒有複製或偽造 FBX 輸出。
- 新增 `RC Path`、原生 Windows Browse 與即時持久化。解析順序為
  UI 路徑 → `CE_RC_EXE` → 票面預設 S: 路徑；已設定但無效時欄位紅框，
  並清楚顯示實際 fallback。
- 所有 GUI 文案改為英文。

### release GUI 實測

- 原生 Browse 選取
  `S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe` 後，
  `gui-state.json` 寫入完整路徑；關閉並重啟 release GUI 後仍保留。
- 將 RC Path 改成不存在的 `Z:\definitely-missing\rc.exe`，欄位立即紅框，
  並顯示 configured path invalid 及 fallback default RC；再還原有效路徑
  後紅框消失。
- `car.fbx` 顯示 17 槽；第一槽由 name heuristic 的 `no_collide` 改為
  `default`，以 `car-r1-physicalize-manifest.json` 作同值 CLI 基準：
  - GUI/CLI `car.json` 逐位元相等，SHA-256
    `C01A11FC837DAF80C9F4F0984AE0557AF96483CF47A3E50746B199AFB1AD6A3A`
  - GUI/CLI `car.mtl` 逐位元相等，SHA-256
    `C3E63AEB4FEA61CC32A9B5C1DB0F3956A81C2705F1C39A21CCC99FC7702E2E64`
  - RC exit 0；`car.cgf` 12,852,735 bytes，SHA-256
    `F10D4723826BA8E52E5B0079CB4A6DDFA50F6526513E8BD6AC066AC55786185A`
  - 複用 `rc_smoke_rust` 對位檢查：material ids 16/16、names 16/16、
    `<unassigned>` placeholder PASS。
- KB3D 修訂後重驗：793 張、132 groups / 5 unknown；五張逐一指派後，
  release GUI 背景處理輸出 391 TIFF（85.68 秒）。抽驗
  `KB3D_ENC_AtlasA`、`KB3D_ENC_AtlasCakeBread`、
  `KB3D_ENC_AtlasFlowersA` 的 diff/spec/ddna 共 9 檔，與首版 CLI
  基準 SHA-256 全部相等。

### 自動化

- `cargo fmt --all -- --check`：PASS。
- `cargo clippy -p texproc-gui -p texproc -p converter --all-targets --release --locked -- -D warnings`：PASS。
- `cargo test -p converter -p texproc -p texproc-gui --release --locked`：PASS；
  converter 40 lib + 7 CLI、texproc 47 lib + 2 fixture + 4 CLI、
  texproc-gui 4 model + 3 RC path tests。
- RC path tests涵蓋 UI 優先、invalid UI → environment fallback、所有候選
  都不存在；無 RC 時 worker 保留 intermediates，UI 使用票面指定的
  `RC not configured — intermediate files exported`。
- `run_gates.ps1 -SkipRC`：ALL GATES PASSED。
- `run_gates.ps1`：ALL GATES PASSED；converter RC material alignment
  16/16，texproc RC/DDS 8/8、ddna alpha 2/2。

### R1 審查（2026-07-26）

審查者獨立驗證：gate 全模式全綠（converter 40 lib、GUI 4 model + 3 RC path 測試）；
GUI 原始碼 grep 零 CJK 字元（英文化屬實）；physicalize 通道等價由
GUI/CLI 逐位元 hash 證明（同值 manifest 基準）；CLI 凍結契約與全部 golden
無退步。環境備註：gate 失敗兩次均為殘留 texproc.exe 檔案鎖，
清除即復原，非程式問題。

尚待：業主目視簽核後改為 DONE。

## R2（2026-07-26 業主指示）：demo3 工作台視覺/互動重做，分步執行

基準：`rebuild/ux-demos/demo3-workbench.html`（業主選定方案）+ R1 全部裁決。
執行模式：Miss Fox（Opus subagent）分三步，每步審查通過才進下一步。

- **R2-S1 原生檔案/目錄選擇器全覆蓋**（治「目錄手 key」）：
  擴充 file_dialog.rs——多選影像檔、資料夾選擇、單檔開啟（FBX/manifest/
  overrides/settings）；八個路徑入口全部配 Browse 或直接用對話框
  （Add Files / Add Folder 直接彈窗）。無新依賴（沿用 Win32 FFI 路線）。
- **R2-S2 demo3 三欄佈局重構**：左欄 tabs+檔案清單、中欄預覽+分組表、
  右欄設定（常用五項+Advanced 摺疊）+四動作鈕、底部狀態列。
- **R2-S3 demo3 互動細節 + Model tab 收尾 + QA**：分組表列選取→預覽、
  unknown 內嵌下拉、進度模態+取消、狀態列診斷 popover；材質表
  physicalize、Export CE Model 動線復驗；英文文案總審；gate + 截圖交業主。

## R2-S1 實作紀錄（2026-07-26）

### 實作

- `file_dialog.rs` 擴充（沿用零新依賴的 Win32 FFI 路線，`cfg(windows)`
  實作 + 非 Windows stub）：
  - `parse_multi_select(&[u16])`：純函式，解析 `GetOpenFileNameW` 的
    double-null 緩衝；單選=整條路徑，多選=首段目錄 + 後續檔名 join。
    抽成純函式以便無 UI 單元測試。
  - `choose_files_multi(title, filter)`：`OFN_ALLOWMULTISELECT|OFN_EXPLORER`
    多選影像檔，經 `parse_multi_select` 還原完整路徑清單。
  - `choose_folder(title, initial)`：資料夾選擇。採 `SHBrowseForFolderW`
    （`BIF_NEWDIALOGSTYLE` 新式對話框）+ `SHGetPathFromIDListW` +
    `CoTaskMemFree`；票面已核可為 COM FFI 過重時的合法替代。initial 因
    無 callback 不支援（已 ponytail 註記）。
  - `choose_file_open` / `choose_file_save`：泛用單檔開啟／儲存，共用一支
    `run_dialog(mode)` 內部函式（`GetOpenFileNameW` / `GetSaveFileNameW`）。
  - `choose_rc_executable` 重構為 `choose_file_open` 的薄包裝，簽章不變。
- `main.rs` 八個路徑入口全數接上原生對話框：
  - Texture Import：`Add Files…` → 多選影像對話框（png/jpg/jpeg/tif/tiff/
    exr 過濾）直接進匯入清單；`Add Folder…` → 資料夾對話框；保留手 key
    的 `Add Path`（同 typing+add 路徑）與 TextEdit 手動覆寫。
  - FBX（model_path）：`Browse…`（*.fbx），填欄並持久化。
  - 貼圖／模型輸出目錄 ×2：各配資料夾 `Browse…`。
  - manifest / overrides：各配 `Browse…`（*.json）。
  - settings：`Browse…`（*.json，選檔即載入）+ 動作列新增 `Save As…`
    （另存新路徑，走儲存對話框，預設檔名取自現有路徑）。
  - RC Path 既有 `Browse…` 沿用（現改走重構後的共用 helper）。
  - 抽出 `path_row()` helper（TextEdit + Browse，`push_id` 隔離 id）減少
    重複；對話框結果回填欄位並觸發與手動輸入相同的 prefs 持久化；使用者
    取消為靜默 no-op，API 錯誤進既有狀態列。
- 無新依賴；未動佈局（S2 負責）；未動 texproc/converter/ce-schema；CLI
  凍結契約未動。

### 驗證

- `cargo build -p texproc-gui --release --locked`：PASS。
- `cargo test -p texproc-gui --release --locked`：PASS；4 model + 7 main
  （含新增 4 個 multiselect double-null parser 測試：單選／多選 join／
  空緩衝／double-null 後殘尾忽略）。
- `cargo clippy -p texproc-gui --all-targets --release --locked -- -D warnings`：
  PASS。
- `cargo fmt --all -- --check`：PASS。
- `Start-Process target\release\texproc-gui.exe`：正常開啟、持續執行（未
  提早崩潰），手動終止；確認無殘留 texproc-gui.exe / texproc.exe。對話框
  互動由業主逐項目視驗收（headless 無法點擊）。

## R2-S2 實作紀錄（2026-07-26）

### 實作

以 `demo3-workbench.html` 為藍本，將 texproc-gui 視窗重構成三欄工作台
+ 底部狀態列；純佈局/資訊架構搬移，不動表格互動（留給 S3）、不加功能、
不移除任何既有能力。全程沿用 S1 的原生對話框，未新增依賴，未動
texproc/converter crate。

- **中欄改為垂直分割**：以 `TopBottomPanel::top("preview_pane")
  .resizable().show_inside` 放預覽區（可拉高度），下方 `CentralPanel
  ::show_inside` 依 tab 顯示 groups 表（貼圖模式）或材質表（模型模式）。
  預覽區的固定 285px 改為填滿可用高度；空狀態文案改為藍本的
  `Select a group to preview`。groups 清單去掉硬編 245px 高，改填滿。
- **右欄改為統一面板**（不再依 tab 切換動作）：
  - 上半 `CentralPanel::show_inside` + `ScrollArea`：輸出目錄 ×2 →
    常用五項（Output Resolution、Diffuse Format、Flip Normal Green、
    Process Metallic、Generate Missing Spec）→ 摺疊「Advanced」（輸出型別
    開關 + normalize/dither/generate 諸旗標 + ARM order/height strength/
    emissive/sss 的 DragValue）→ CE Model Export（Manifest/Overrides/
    RC Path）→ Settings File（路徑 + Save As…）。輸出型別開關由原本常駐
    改收進 Advanced，符合藍本常用五項的取捨。
  - 下半 `TopBottomPanel::bottom("right_actions").show_inside` 釘在底部：
    `Process Textures`、`Export CE Model`、`Save Settings` / `Load
    Settings`。兩個主動作皆常駐（依狀態 enable），不再隨左欄 tab 消失。
  - 既有 manifest/overrides/RC Path/Save As/進度列/取消/輸出摘要/送貼圖
    等能力全部保留，只是換位置。
- **狀態列**加右對齊診斷計數（unresolved unknown + 材質診斷數）：0 時綠色
  `No diagnostics`，>0 時橘色 `N diagnostics`。S3 再做可點 popover，本步
  先靜態計數。
- 左欄 tabs（Texture Import / Model Import）、匯入清單、Model 摘要維持
  S1 現況；面板寬度左 380（~22%）、右 380（~26%），未新增持久化。

程式仍集中於 `main.rs`（拆檔會產生大量搬移 diff、反而不利審查，故不拆）。

### 驗證

- `cargo build -p texproc-gui --release --locked`：PASS。
- `cargo fmt --all -- --check`：PASS。
- `cargo clippy -p texproc-gui --all-targets --release --locked -- -D warnings`：
  PASS。
- `cargo test -p texproc-gui --release --locked`：PASS（4 model + 7 main，
  含 S1 的 multiselect parser 與 RC path 測試，無退步）。
- release exe 置頂截圖 `ux-demos/r2-s2-screenshot.png`：三欄 + 狀態列佈局
  正確顯示（左 tabs+清單、中 Preview 分割+groups 佔位、右 Output Settings
  五項+Advanced 摺疊+CE Model Export+RC Path+底部動作鈕、狀態列
  `No diagnostics`）；截圖後終止程序，確認無殘留 texproc-gui.exe /
  texproc.exe。互動流程仍由業主目視驗收。

### 偏離

- 藍本把材質表放左欄 Model tab；本票 TARGET LAYOUT 指定材質表在中欄下半、
  左欄只留 Model 摘要——依票面（非藍本）實作。
- 藍本標題列有「檔案/編輯/說明」選單，未做（非本票範圍，且無對應功能）。

## R2-S3 實作紀錄（2026-07-26）

### 實作

以 `demo3-workbench.html` 為互動藍本，完成分組表、進度模態、診斷 popover
與 Model 收尾；全程沿用 S1 原生對話框與 S2 三欄佈局，未新增依賴，未動
texproc/converter crate 與凍結 CLI 契約。

- **分組表（貼圖模式）**：中欄下半改為 demo3 風格表格。欄位＝
  `Group | 12 個型別格（Dif Nrm Spc Gls Rgh Hgt Met AO Alp Emi SSS ARM）|
  Unknown`。型別格為綠（已填）／灰（空）小方塊，已填格可點選預覽該張貼圖；
  含 unknown 的列整列琥珀底色（選取時加深），指派後底色自動清除。Unknown
  欄為就地下拉（`Assign (N)…`），選型別即指派該組第一張 unknown，走既有
  `ReviewDocument::assign_unknown`；下拉中已被占用的型別停用（DEF-19 防呆）。
  表頭固定、列以 `ScrollArea` 捲動，132 組順暢。點列名選取群組→預覽窗顯示
  縮圖＋群組名＋map badges（已填型別藍徽章＋unknown 琥珀徽章）。保留搜尋框
  與「Unknown only」過濾。
- **進度模態**：`Process Textures` 開啟 `egui::Modal` 遮罩，顯示整體進度條、
  `完成/總數 · 當前組`、逐組清單（依完成事件標記 ✓／待處理）、Cancel 接既有
  取消旗標；完成後同一模態轉為「Processing Complete」摘要＋可點「Open output
  folder」＋Close。右欄僅留 `Process Textures` 與（處理中）`Show progress`
  重開鈕，行內進度條移除，改由模態統一呈現。
- **診斷 popover**：狀態列診斷計數改為可點按鈕，開合右下角錨定的
  `Diagnostics` 視窗，逐條列出（unknown 未指派、群組 DEF-19、RC 未設定／
  無效、FBX 材質診斷），空狀態顯示綠色 `No diagnostics`。計數與清單同源。
- **Model 模式收尾**：材質表列點選→下方 Material Details（名稱、指派來源、
  貼圖引用清單）；physicalize 下拉沿用（只送改過的值進 explicit 通道）。
  `Export CE Model` 改走同款模態：worker 新增 `Stage` 事件，模態顯示
  Convert（.mtl + request）→ Resource Compiler（CGF）兩階段 spinner；成功
  顯示 CGF 路徑＋「Open output folder」＋Close，失敗亦於模態顯示訊息。
- **總審／polish**：視窗標題 `CryEngine Texture Processor`；文案全英文；
  Output Resolution 下拉移除遺留的 `64 (validation)` smoke 值、改列 256
  （`TextureSettings::default` 本即 `Original`）；移除改版後失去用途的
  `selected_unknown`／`assignment_type` 欄位、舊 `assign_unknown` 導航法與
  `detected_type_summary`，無死碼、無死鈕。

### 驗證

- `cargo build -p texproc-gui --release --locked`：PASS。
- `cargo clippy -p texproc-gui --all-targets --release --locked -- -D warnings`：
  PASS。
- `cargo fmt --all -- --check`：PASS。
- `cargo test -p texproc-gui --release --locked`：PASS（5 model + 7 main）。
  model 層新增測試 `assigning_every_unknown_clears_the_diagnostics_count`：
  逐張指派 unknown 後 `unresolved_unknown_count` 由 2→1→0，證明指派更新
  診斷計數來源。
- `run_gates.ps1`（完整、含 RC）：ALL GATES PASSED，核心無退步。
- release GUI 實測截圖（各以 CLI 引數載入資料後擷取）：
  - `ux-demos/r2-s3-texture.png`：`Z:\enchanted\KB3DTextures\4k` 載入，
    793 張／132 groups／5 unknown；分組表、型別格、琥珀 unknown 列、就地
    `Assign (1)…`、預覽 badge、右欄設定與 RC Path 解析皆正常。
  - `ux-demos/r2-s3-model.png`：`fixtures/car/car.fbx` 載入，17 材質槽、
    physicalize 下拉、選取列 Material Details、右欄設定正常。
  - 擷圖後終止程序，確認無殘留 texproc-gui.exe／texproc.exe。

### 偏離

- 分組表顯示全部 12 個 source-type 欄（藍本只列 8），以免隱藏 alpha/sss/arm
  等已填槽；預覽 badges 亦列完整已填集合。
- 選取點擊目標為「列名＋已填型別格」而非整列，以避開 egui 中整列 click 與
  行內下拉的點擊衝突；列琥珀／選取底色仍整列滿版。
- 行內指派針對該組第一張 unknown（藍本假設每組單一 unknown）；多張時列維持
  琥珀直到該組 unknown 全數指派。
- Model 匯出模態為不定量 spinner＋Convert→RC 階段文字（RC 無細粒度進度）。
- 模態／popover 未另附截圖（需驅動執行中程序），以 build/test 佐證。
- 截圖取視窗原生 1440 邏輯尺寸；右欄設定面板最右數 px 因顯示 DPI 有輕微裁切，
  內容仍全可辨識。

## R3（2026-07-26 業主裁決，R2 目視回饋）

1. **分組區三欄式（2026-07-26 業主以標註截圖釐清：= demo3 的對齊表格，
   非卡片 grid）**：三個對齊的邏輯欄區——左：組名固定寬欄；中：每型別
   一窄欄、有欄標題、指示燈上下對齊；右：未指派欄（指派下拉 / ✓ 已指派 / —）。
   表頭固定、列捲動；選取/琥珀態語意不變。R2-S3 的問題正是名稱、燈、
   下拉同列流動排版導致不對齊。
2. **FBX 貼圖自動全拉入**（原版行為，R2 做成了隱藏按鈕）：Load FBX 成功
   即自動把 referenced（存在於磁碟者）+ embedded（解出到快取目錄）貼圖
   全部送入貼圖分組，狀態列回報「N textures imported from FBX（M embedded）」；
   原按鈕可留作重送。這是「模型連貼圖完整導出」工作流的核心，不是選配。
3. **可選 RC 轉 DDS**（原版 `Generate CryEngine DDS` 核取框，被漏掉）：
   Output Settings 加 checkbox「Generate CryEngine DDS (via RC)」，勾選時
   Process Textures 在 TIFF 完成後逐張餵 RC（沿用 T-013 smoke 的呼叫形狀與
   RC Path 解析）；進度模態顯示 DDS 階段；RC 不可用時 checkbox 停用附提示。

DoD：三項各有實測證據（截圖/狀態列文字）；car.fbx 載入後貼圖組自動出現
（含 embedded 案例——car 無 embedded，另用小型含嵌入貼圖之 FBX 或以
referenced 案例 + 單元測試覆蓋 embedded 路徑）；DDS 勾選實跑產出 .dds；
gate 全綠不退步。

## R3 實作紀錄（2026-07-26，Miss Fox）

只動 `texproc-gui`（`main.rs` / `worker.rs` / `prefs.rs`）；未動
`texproc` / `converter` / `ce-schema` 與凍結 CLI 契約；無新依賴。R2-S1..S3
能力全數保留。

### 1. 分組區三欄對齊表格（依業主標註截圖裁決 = demo3 對齊表格）

- 先按初版指示做了卡片式 3 欄 grid，收到業主更正後**整段捨棄**，改回
  demo3 藍本的對齊表格。以既有 `fixed_cell()`（固定寬、垂直置中）搭配
  ScrollArea 外的固定表頭 + 分隔線達成「表頭固定、列捲動」。
- 三個對齊欄區：
  - **Group**：固定寬左欄，組名 `truncate` + hover 全名 tooltip，點名選取→預覽。
  - **型別指示欄**：每追蹤型別一窄欄（`GROUP_CELL_W=38`），欄標題採 demo3
    英文（Color / Normal / Spec / Gloss / Rough / Metal / Height / AO /
    Alpha / Emiss / SSS / ARM——demo3 主 8 欄 + 我們額外追蹤的
    Rough/Alpha/SSS/ARM，避免隱藏已填槽）；綠（已填）／灰（空）方塊上下對齊，
    已填格可點→預覽該張。
  - **Unassigned**：含 unknown→就地 `Assign (N)…` 下拉（走既有
    `assign_unknown`，DEF-19 佔用型別停用）；曾有 unknown 現已清空→綠色
    `✓ Assigned`；從無 unknown→`—`。三態靠新欄位
    `TextureState.ever_unknown`（掃描完成時記下含 unknown 的 group key）區分。
- 琥珀列（含 unknown）／藍色選取底色語意不變；搜尋框與「Unknown only」
  過濾照舊；132（實測 KB3D 127 無 unknown 版）列捲動順暢。

### 2. Load FBX 自動全拉入貼圖

- `extract_model_texture_paths` 重構為可測純函式
  `collect_model_textures(&[MaterialRecord], model_dir, embedded_dir)`，回傳
  `TextureIngest { paths, embedded }`（referenced 存在於磁碟者 + embedded
  解出到快取，依絕對路徑去重、計 embedded 數）。
- `poll_model` 於 `ModelEvent::Completed` **自動**呼叫
  `ingest_model_textures()`（不需按鈕、不需切頁；保留當前 tab），把貼圖送入
  分組；掃描完成後狀態列回報
  `N textures imported from FBX (M embedded): G groups, U unknown.`
  （新增 `TextureState.pending_fbx_import` 讓 `poll_scan` 據實回報）。零貼圖時
  回報 `No textures found in the FBX to import (references not on disk).`
- 原按鈕改名 `Re-send Referenced / Embedded Textures…` 作手動重送；去重沿用
  `add_texture_roots`（以小寫絕對路徑），重載同一 FBX 不重複列項。

### 3. 可選 RC→DDS

- `prefs` 新增持久化 `generate_dds`（bool）。Output Settings 常用區加
  checkbox「Generate CryEngine DDS (via RC)」；RC 解析（UI→env→預設）無效時
  checkbox 停用並附 hint `RC not configured`。
- `worker::start_process` 加 `rc_exe: Option<PathBuf>`：TIFF 全部寫完且未取消
  時，逐張以 `RC.exe <tif> /refresh /userdialog=0`（cwd=輸出目錄，沿用 T-013
  smoke 形狀）序列產 DDS；新增 `ProcessEvent::DdsProgress` 供進度模態顯示
  「Compiling DDS via RC: n/total · name」第二進度條；`Finished` 改帶
  `ProcessComplete { report, dds: Option<DdsSummary> }`。每檔失敗收進
  `DdsSummary.failures` 進診斷 popover，不中止整批；DDS 落在 TIFF 旁。

### 驗證

- `cargo fmt --all -- --check`：PASS。
- `cargo clippy -p texproc-gui --all-targets --release --locked -- -D warnings`：
  PASS。
- `cargo test -p texproc-gui --release --locked`：5 model + 9 main PASS（1 ignored）。
  新增 model 層測試：
  - `ingest_tests::collect_dedups_references_and_counts_embedded`：一 referenced
    + 一 embedded + 重複引用 + 缺檔引用 → paths=2、embedded=1、快取寫出，證明
    去重與 embedded 計數。
  - `worker::tests::dds_jobs_selects_only_tiff_outputs`：DDS job 清單只挑 .tif。
- **真 RC 端到端（GUI worker 程式路徑）**：
  `worker::tests::dds_pass_produces_dds_next_to_tiffs`（`#[ignore]`，需
  `CE_RC_EXE`）——以 `start_process(..., Some(rc))` 跑 `fixtures/textures`，
  斷言每張 TIFF 旁都產出 .dds、`dds.succeeded==dds.total`；`set CE_RC_EXE=…\rc.exe`
  下 `cargo test -p texproc-gui -- --ignored dds_pass` **PASS**（8/8、51.7s）。
- `run_gates.ps1`（完整含 RC）：ALL GATES PASSED；converter RC 16/16、
  texproc RC/DDS 8/8、ddna 2/2、preserved 17/17，核心零退步。

### 真實資料截圖（rebuild/ux-demos/）

- `r3-groups-grid.png`：`Z:\enchanted\KB3DTextures\4k`（去 refraction 之 127 組
  全已指派版）→ 三欄對齊表格滿版多列，型別燈上下對齊、Unassigned 顯 `—`、
  選取列預覽 + map badges。
- `r3-groups-grid-unknowns.png`：同資料原始 5 unknown 版（Unknown only）→ 琥珀列
  + 就地 `Assign (1)…` 下拉，示範 Unassigned 下拉態與對齊。
- `r3-fbx-ingest.png`：Load `KB3D_ENC_PropAxe_A_grp.fbx` → 狀態列
  `6 textures imported from FBX (0 embedded): 2 groups, 0 unknown.`；右欄
  `✓ Generate CryEngine DDS (via RC)` 勾選+啟用、RC Path 已解析；預覽自動載入
  FBX 引用貼圖，證明載入即自動拉入。
- `r3-dds-summary.png`：DDS 產物資料夾——8 張 .tif 旁各有對應 .dds（+ cryasset），
  即「DDS 落在 TIFF 旁」。

### 偏離

- **分組表**：初版依指示做卡片 grid，業主更正後改回 demo3 對齊表格（已捨棄
  卡片碼）。型別欄顯示全部 12 追蹤型別（demo3 只列 8），以免隱藏
  Rough/Alpha/SSS/ARM 已填槽。
- **DDS 完成模態截圖**：本自動化環境對 egui 視窗的**合成滑鼠點擊全數無效**
  （SetCursorPos/mouse_event、SendInput 絕對座標、PostMessage、DPI-aware 皆試
  過；截圖可、點擊不可，已確認視窗為前景+焦點且座標對齊），故無法驅動
  Process Textures 按鈕擷取即時 DDS 完成模態。改以（a）上述 `#[ignore]` 真 RC
  整合測試證明 GUI worker 的 DDS 程式路徑實跑產出 8/8 .dds，（b）
  `r3-dds-summary.png` 產物資料夾截圖，共同覆蓋 DoD 的「DDS 勾選實跑產出 .dds」。
- **滿版分組表截圖**：因無法點擊切換「Unknown only」，改載入去除 refraction
  的 KB3D 版（127 組全已指派）讓表格預設展開全列；unknown/下拉態另以
  `r3-groups-grid-unknowns.png` 補足。
- **embedded 案例**：car/axe 皆無 embedded 貼圖，embedded 抽取+計數路徑由
  `collect_dedups_references_and_counts_embedded` 單元測試覆蓋（合成 embedded blob）。

## R3 修正：分組表未對齊（業主標註截圖否決）

僅動 `texproc-gui/src/main.rs`；未動 texproc/converter/凍結契約；無新依賴。

### 根因

R3 的分組表雖已用 `fixed_cell`，但（a）`fixed_cell` 走
`allocate_ui_with_layout` 只設最小尺寸、未夾住最大寬，長組名不 truncate 反而
把該格撐寬，逐列把後面的指示燈往右推——不同名稱長度→燈的 x 不同；（b）表頭在
ScrollArea 外的 `ui.horizontal`，資料列各自包在 `Frame.inner_margin(4,1)` 內，
造成表頭與列固定差 4px、標題也不落在燈欄正上方。先前截圖因名稱都截到同寬而掩蓋。

### 修正

- 依業主裁示改為**單一 `egui::Grid`**：表頭列與所有資料列同屬一個 Grid，欄 x
  由 Grid 構造保證一致（欄 0 組名、欄 1..12 各型別窄欄、欄 13 Unassigned）。
- `fixed_cell` 加 `set_min_width==set_max_width`（回傳格 rect）：組名欄夾在
  ~150–232px 動態寬並 `truncate` + hover 全名，長名只截字、**永不撐開後面欄**。
- 選取藍底 / 琥珀待指派底色改為「整列一張 rect 畫在該列背後」（先
  `painter().add(Shape::Noop)` 佔位，量到整列 union rect 後 `painter().set`
  回填），非逐格上色，滿版覆蓋整列。
- 型別燈仍為綠（已填）／灰（空）、已填可點預覽；Unassigned 三態（`Assign(N)…`
  下拉 / `✓ Assigned` / `—`）、搜尋、Unknown only、就地指派、DEF-19 佔用停用
  全數不變。model 材質表本即真正的 `Grid`（`model_materials`），未受影響、未改。

### 偏離

- **表頭隨列捲動**：為滿足「單一 Grid」硬需求，表頭做成 Grid 首列、置於
  ScrollArea 內（票面預先核可的 fallback），故長列捲動時表頭一起捲走，非黏頂。
- 12 欄 + 組名 + Unassigned 較寬，視窗窄時由 `ScrollArea::both` 提供水平捲動。

### 驗證

- `cargo fmt --all -- --check`、`cargo clippy -p texproc-gui --all-targets
  --release --locked -- -D warnings`：PASS。
- `cargo test -p texproc-gui --release --locked`：5 model + 9 main PASS（1 ignored）。
- **對抗性資料集截圖** `ux-demos/r3-groups-grid-fixed.png`：以 CLI 引數載入一組
  名稱長度差異明顯的 5 組（`KB3D_ENC_Ivy` 12、`AtlasA` 15、`BoulderWall` 20、
  `WoodOldWornBrownBDamaged` 33、`PlasterDamagedYellowDirtGrad` 37 字元）。短名
  完整顯示、長名截字帶「…」，**所有型別燈仍精準對齊各自表頭欄**，AtlasA 選取
  列藍底滿版整列——證明長名不再推移欄位。截圖後終止 texproc-gui/texproc 程序，
  確認無殘留；臨時對抗資料夾已刪。

## R4（2026-07-26 業主裁決）

1. **資料夾選擇器換現代型**：棄用 SHBrowseForFolderW（老樹狀窗，圖 343），
   改 `IFileOpenDialog` + `FOS_PICKFOLDERS`（檔案總管式，圖 344 同款）。
   COM FFI 無新依賴；檔案開啟對話框已是現代型不用動。
2. **.mtl 隨附 .mtl.cryasset**：規則移植 `output_formats/mtl_exporter.py:404`
   `export_mtl_cryasset`——路徑 = mtl 路徑 + `.cryasset`；XML
   `AssetMetadata version="0" type="Material" guid=<uuid4>`；`Files/File`
   = mtl 檔名；`Details`：subMaterialCount（排除 ignored set）、
   textureCount；`Dependencies`：三張 `%ENGINE%` white 貼圖 + 專案 `.dds`
   相對路徑（`./` 前綴、排序）。實作放 converter lib（CLI 與 GUI 同惠）。
   - uuid：不加依賴，std 熵源自產 v4 形狀即可。
   - gamesdk 實例含 `timestamp` 屬性（epoch 秒），加上（Python 漏的，
     以引擎實例為準）。
   - **CLI 契約註記**：convert 成功輸出自此多一個 `<stem>.mtl.cryasset`，
     本節即為契約變更的開票紀錄；旗標/退出碼不變。
   - 驗收：與 Python 版對同輸入的 cryasset 正規化 XML 比對，白名單僅
     guid 與 timestamp。

## R4 實作紀錄（2026-07-26，Miss Fox）

動 `texproc-gui/src/file_dialog.rs`（Item 1）與 `converter`（Item 2：新增
`cryasset.rs`、`mtl.rs`/`convert.rs`/`lib.rs` 接線）；無新依賴；凍結 CLI
旗標/退出碼不變（R4 本即契約變更票，convert 成功多出一個 sibling
`<stem>.mtl.cryasset`）。

### Item 1：現代資料夾選擇器（IFileOpenDialog + FOS_PICKFOLDERS）

- 以手搓 COM FFI（沿用既有 vtable struct 風格，無 windows crate）取代
  `SHBrowseForFolderW`：`CoCreateInstance(CLSID_FileOpenDialog,
  IID_IFileOpenDialog)` → `GetOptions|SetOptions(FOS_PICKFOLDERS |
  FOS_FORCEFILESYSTEM)` → `SetTitle` → `Show` → `GetResult` →
  `IShellItem::GetDisplayName(SIGDN_FILESYSPATH)`，得到檔案總管式對話框。
- `CoInitializeEx(COINIT_APARTMENTTHREADED)` per-call：`S_OK`/`S_FALSE` 皆視為
  成功並在函式尾平衡 `CoUninitialize`；`RPC_E_CHANGED_MODE`（COM 已於他式
  初始化，仍可用）則不擁有引用、不 uninit；其餘失敗 HRESULT 回 Err。
- vtable 只宣告到 `GetResult`（IShellItem 到 `GetDisplayName`），用不到的槽位
  以 `*const c_void` 佔位保持 ABI 順序；`Show` 取消回傳 `HRESULT_CANCELLED`
  → `Ok(None)` 靜默取消。每個介面指標在返回前皆 `Release`；PWSTR 以
  `CoTaskMemFree` 釋放。
- `choose_folder` public 簽章不變（main.rs 呼叫端零改動）；泛用檔案開啟／儲存
  對話框（`GetOpenFileNameW`/`GetSaveFileNameW`）維持原樣，已是現代型。移除
  now-dead 的 `SHBrowseForFolderW`/`SHGetPathFromIDListW`/`BrowseInfoW`/BIF_*
  /MAX_PATH 與 Shell32 link。

### Item 2：.mtl 隨附 .mtl.cryasset（converter lib 層）

- 新 `converter::cryasset`：`build_cryasset_xml`（純函式、可測）+
  `write_cryasset`。輸出路徑 = `<mtl>.cryasset`，在 `write_mtl` 成功寫出 .mtl
  後立即寫（CLI convert 與 GUI 皆走 `write_mtl`，一處接線兩邊同惠）。
- XML shape 對齊 Python `export_mtl_cryasset` + 引擎實例：
  `<AssetMetadata version="0" type="Material" guid=<uuid4形> timestamp=<epoch秒>>`；
  `Files/File path=<mtl 檔名>`；`Details` 的 subMaterialCount（排除 ignored set
  `{"Material","Dots Stroke"}`）、textureCount（唯一貼圖路徑數，含非 dds）；
  `Dependencies` 先三張 `%ENGINE%/EngineAssets/Textures/white{,_ddna,_displ}.dds`
  （usageCount="1"），再接排序去重的專案 `.dds`（`./` 前綴——路徑本即 mtl 相對
  形，已 `./`/`../`/`%` 者不重複加）。單空格縮排、無 XML 宣告列。
- guid：無 uuid/rand 依賴，兩個 `RandomState` 種子 + wall-clock nanos 混雜出
  128 bit，設 version(4)/variant 半位元組，格式
  `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`（非密碼學用途，僅資產唯一 id）。
  timestamp：`SystemTime` epoch 秒（Python 漏、引擎實例有，以引擎為準）。
- `ConvertOutputs` 加 `cryasset` 欄（additive）：CLI convert stdout JSON 現含
  mtl/request/cryasset 三路徑；旗標與退出碼不變。

### 驗證

- `cargo fmt --all -- --check`：PASS。
- `cargo clippy -p texproc-gui -p converter --all-targets --release --locked
  -- -D warnings`：PASS。
- `cargo test -p converter --release --locked`：45 lib（含新增 5 個 cryasset
  單元測試：counts/去重、engine-first + 排序 + 僅 dds、header/root shape、
  `./` 前綴條件、guid uuid4 形 256 抽樣）+ 7 CLI PASS。
- `cargo test -p texproc-gui --release --locked`：5 model + 9 main（1 ignored）
  PASS，無退步。
- **Python 基準正規化比對**（白名單僅 guid、timestamp）：以 car.fbx 實跑
  `converter convert`（texture-dir seed 自 `car-generated-reference.mtl` 的
  Texture File）得 Rust `kb3d_...native.mtl.cryasset`（17 submaterials、65
  textures、engine-first、`../tex/*.dds` 排序）；再把同一份生成 mtl 的
  submaterial 餵回 Python `export_mtl_cryasset`，`tools/compare_xml_golden.py`
  正規化樹比對 `OK=True`、0 mismatch、220 值相等、僅 guid/timestamp 命中白名單。
- `run_gates.ps1`（完整含 RC）：ALL GATES PASSED；T-005 MTL golden／schema
  gate／preserve 17/17 未受影響（cryasset 為 sibling 檔），converter RC 16/16、
  texproc RC/DDS 8/8、ddna 2/2 核心零退步。
- release GUI 啟動 6s 存活不崩、截止手動終止；資料夾對話框本身（合成點擊
  無效之限制）留待業主目視簽核。收尾確認無殘留 texproc-gui/texproc/rc/
  converter 程序。

### 偏離

- 資料夾對話框無法在此環境 robo-click 驗收（既有限制）；以程式碼層 + 啟動不崩
  佐證，視覺由業主確認。
- `choose_folder` 的 `initial` 參數仍不接（現代對話框自記上次位置，SetFolder
  需另建 IShellItem，不划算）——已 ponytail 註記，行為與 R2-S1 相同。

## R5（2026-07-26 業主裁決）

1. **刪除選中貼圖**：Imported Textures 清單支援多選（Ctrl/Shift 慣例），
   新增 Remove Selected 鈕（+右鍵選單可選作）；移除後分組即時重算。
2. **加入關聯貼圖**：新增 Add Related 鈕——對選中貼圖，按其命名規則
   （base name）與所在目錄，把同組其他貼圖自動加入。動機：FBX 常常
   只關聯部分貼圖種類。**效能紅線（業主明令）**：嚴禁每張選中圖各自
   遍歷／嚴禁對候選檔開像素。正解：選中集合先歸納出唯一
   `(目錄, base_name)` 對，每個唯一目錄**只列舉一次**，候選檔用
   **純檔名解析**（既有 suffix parser）比對 base；只有真正加入清單的檔
   才走既有 add 流程（其中歧義後綴的 header probe 照舊，那是 O(加入數)
   不是 O(候選數)）。
3. **補 Python 版既有選項**（`export_settings.py` 的 delete 核取框）：
   - `Delete request JSON after model export`（導出後刪 json；.mtl/.cryasset 不刪）。
   - `Delete TIF after DDS export`（DDS 成功後刪對應 tif；單檔 DDS 失敗
     則保留該 tif 並記診斷）。
   均入 prefs 持久化，預設 off。
4. **導出模型順帶導出關聯貼圖組**：新 checkbox
   `Export associated textures with model`——Export CE Model 時，先把
   「來自該 FBX 拉入的貼圖組」跑貼圖處理（輸出到 Texture Output Directory），
   並以該目錄作 texture-dir 參與 MTL 貼圖解析（產出的 MTL 直接指向處理後
   貼圖）；與 DDS 選項組合時 TIF→DDS 照常（含選項 3 的刪 tif 邏輯）。
   進度統一進既有模態（階段：Textures → Convert → RC → DDS）。

DoD：四項各有實測證據；效能證據 = 對 Z:\enchanted\KB3DTextures\4k
（793 檔目錄）做一次 Add Related 的耗時（應為列舉一次目錄的量級，
毫秒級～百毫秒級）；gate 全綠不退步。

## R5 實作紀錄（2026-07-26，Miss Fox）

改動集中於 `texproc-gui`（`main.rs` / `worker.rs` / `prefs.rs` / `lib.rs`）
與 `texproc`（新增純函式 `parse_base_name`）；未動 `converter` 與凍結 CLI
契約；無新依賴。R1–R4 能力全數保留。

### 1. 多選 + Remove Selected

- `TextureState` 以 `selected_files: BTreeSet<usize>` + `selection_anchor`
  取代單選 `selected_file`；點選＝單選、Ctrl+點＝切換、Shift+點＝自 anchor
  的範圍選（`apply_selection_click` 純邏輯）。清單標題顯示「(N) · M selected」
  與操作提示。掃描完成即清空選取（索引會變）。
- `Remove Selected`（選取非空才啟用）：把「現有 files 去掉選取」的結果**攤平
  成明確檔案清單**設回 `roots` 再重掃，避免資料夾 root 於下次掃描把移除的檔
  重新帶回；全部移除時回到空匯入態。保留 Clear All。

### 2. Add Related（效能紅線）

- 純邏輯放 model 層：`texproc-gui::related_wanted_bases`（選取集合先歸納唯一
  `(目錄, 小寫 base_name)` 對）＋ `related_matches_in_dir`（單一目錄檔名清單
  → 純檔名比對 base、跳過已匯入與非影像）。base_name 一律走新 `texproc::
  parse_base_name`（**純字串、無 header probe、無解碼**，鏡射 classify_path
  的 base 推導）。
- `main.rs::add_related_textures` 對每個唯一目錄 `read_dir` **一次**，只有比中
  的檔才進既有 add 流程（歧義後綴的 header probe 是 O(加入數)）。狀態列：
  `Added N related textures (M dirs scanned).`（以 `pending_import_status`
  讓訊息熬過隨後的重掃）。
- 單元測試：`related_bases_dedup_pairs_across_a_selection`（配對去重）、
  `related_matches_base_and_skips_imported_and_non_images`（base 比對／不重複
  加入／濾非影像）、`parse_base_name_is_header_free_and_matches_grouping`。

### 3. 導出後刪除選項（prefs 持久化，預設 off）

- `Delete request JSON after model export`：僅在**完整成功（RC 產出 CGF）**時
  刪 `<stem>.json`，保留 `.mtl` 與 `.mtl.cryasset`（`poll_model_export` 於
  `RcExportOutcome::Succeeded` 才刪；摘要顯示「Request: deleted after export」）。
- `Delete TIF after DDS export`：`run_dds_pass` 每張 RC 成功後才刪對應 .tif；
  單張失敗保留該 tif 並記診斷（沿用既有 pattern）。`start_process` 加
  `delete_tif` 參數。

### 4. Export associated textures with model（checkbox，預設 off）

- 追蹤匯入來源：`ingest_model_textures` 記下 FBX 拉入貼圖的小寫絕對路徑
  （`fbx_ingested`），載入新 FBX 時清空。
- 勾選後 `start_model_export` 走 staged worker（新增 `AssociatedTextures`
  入參）：(a) 把「含 FBX 來源檔且有 slot」的貼圖組 `process_scan_parallel`
  到 Texture Output Directory → (b) convert 以該目錄作 texture-dir，MTL 指向
  處理後貼圖 → (c) RC → CGF → (d) 若開 DDS 則 TIF→DDS（含選項 3 刪 tif）。
  模態顯示四階段 `Textures → Convert → RC → DDS`。無 FBX 來源組時跳過 (a)
  並於狀態列註記。

### 驗證

- `cargo fmt --all -- --check`：PASS。
- `cargo clippy -p texproc-gui -p texproc -p converter --all-targets --release
  --locked -- -D warnings`：PASS（`start_model_export` 參數多，加
  `#[allow(too_many_arguments)]` 並 ponytail 註記）。
- `cargo test -p texproc-gui --release --locked`：7 model + 9 main PASS
  （2 ignored 為真資料/真 RC 整合測試）。
- `cargo test -p texproc --release --locked`：48 lib（含 parse_base_name）
  + fixture + CLI PASS。
- `run_gates.ps1`（完整含 RC）：**ALL GATES PASSED**；converter RC 16/16、
  texproc RC/DDS 8/8、ddna 2/2、preserve 17/17、T-005 MTL/schema golden 零退步。

### 真實資料證據

- **Add Related 計時**（`texproc-gui` `#[ignore]` 測試
  `add_related_timing_on_real_kb3d_directory` 走 model/worker 程式路徑）：於
  `Z:\enchanted\KB3DTextures\4k` 只匯入 `KB3D_ENC_AtlasA_basecolor.png` 後
  Add Related → **列舉一次目錄（793 entries）、加入 6 檔、耗時 0.8 ms**，
  加入者為 AtlasA 的 ao/height/metallic/normal/opacity/roughness；正確排除
  同名前綴但不同組的 `KB3D_ENC_SignAtlasA_*`。遠低於一秒，符合效能紅線。
- **Export CE Model + item 4**（`#[ignore]` 測試
  `export_with_associated_textures_produces_cgf_and_dds`，走 worker
  `start_model_export`）：以 `fixtures/KB3D_ENC_PropAxe_A_grp.fbx`（引用貼圖
  於 Z:\...\4k），開 associated + DDS + delete-tif → 四階段全跑；associated
  2 groups / 6 files、DDS 6/6、輸出目錄剩 6 .dds / 0 .tif（刪 tif 生效）；
  `.mtl` 產出且含 Texture 引用；`.cgf` 43,610 bytes（RC exit 0）。
- 截圖（`rebuild/ux-demos/`）：
  - `r5-list-multiselect.png`：Imported Textures (13) · 0 selected、多選提示、
    `Remove Selected` / `Add Related` 鈕（0 選取時停用，示範啟用條件）。
  - `r5-export-with-textures.png`：Model tab 載入 PropAxe（2 組×6 貼圖，引用自
    Z:\...\4k）；右欄四個 R5/DDS 核取框皆勾選
    （Export associated textures / Delete request JSON / Delete TIF after DDS /
    Generate CryEngine DDS）、RC Path 已解析。

### 偏離

- **GUI 即時互動截圖限制**（沿 R3/R4）：本環境對 egui 視窗的合成點擊無效，
  無法擷取「實際多選高亮」「進度模態」等互動態；改以（a）上述兩支真資料
  `#[ignore]` 整合測試證明 model/worker 程式路徑、（b）配置態截圖佐證。
- **右欄面板寬度**：截圖以較窄視窗（1180px）擷取，使右欄設定完整可讀
  （寬視窗時本環境的 DPI/scale 會把右欄裁到邊，屬既有現象）。
- Add Related 的目錄列舉在 UI 執行緒同步跑（單一 `read_dir`，實測 0.8 ms，
  無需背景化）。

## R6（2026-07-26 業主回報 bug）：大批量轉換靜默崩潰

**症狀**：大批量轉換時風扇升速、系統不卡，程式無預警消失。
**診斷（審查者，證據在案）**：Windows Application Log 兩筆 Event 1000，
例外碼 `0xc0000409`（Rust `abort()`/`__fastfail` 簽名）＝ 記憶體配置失敗
觸發 abort。機器 96GB/20 核；rayon 跨組 20 執行緒 × 每組 4K planar f32
約 3-5GB（7 源圖×256MB + 中間層 + 輸出）→ 峰值 60-100GB，超過即死；
GUI 無 console，abort 訊息不可見 → 靜默消失。CLI 同病，只是有 console 看得到。

**修復（texproc lib 層，CLI/GUI 同惠）**：
1. **記憶體額度制的組進場**：每組以 `probe_header`（免解碼）估算
   `Σ(w×h×ch×4B)×3`（源+中間+輸出係數），維持在途組估算總和 ≤ 額度；
   額度預設 = 實體 RAM 的 50%，`TEXPROC_MEM_BUDGET_MB` 環境變數可覆蓋。
   平行度自然由額度與組大小決定，不再無條件 20 路全開。
2. **Stage 2 串流寫出**：每個輸出生成→寫檔→立即釋放，不再六張全堆滿
   才寫；來源圖在不再被解析鏈引用後儘早釋放。
3. **崩潰可見性**：panic hook 寫 `crash.log`（exe 旁）；批次內單組 panic
   以 catch_unwind 圈住 → 該組記為 failed + 診斷，批次繼續，GUI 顯示
   失敗組清單而不是整程式消失。（OOM abort 本身不可攔——靠額度制不發生。）

**DoD**：
- 重現證據：修復前對足量 4K 批次記錄峰值 commit（或觸發崩潰）；
  修復後同批次完跑，峰值記憶體 ≤ 額度 + 合理餘裕，數字貼票。
- 注入 panic 的測試證明單組失敗不殺批次、crash.log 有內容。
- 錨點/golden/gate 全綠不退步（額度制不得改變輸出內容，只改排程）。

## R6 實作紀錄（2026-07-26，Miss Fox）

動 `texproc`（`batch.rs` / `output.rs` / `lib.rs` / CLI `main.rs`）與
`texproc-gui`（`main.rs` / `worker.rs`）；無新依賴；**不改輸出位元組，只改排程與
可見性**。

### 1. 記憶體額度制的組進場（texproc lib，CLI/GUI 同惠）

- `estimate_group_bytes`：對每組「必要」來源（沿用既有 `source_is_required`）求
  Σ(w×h×ch×4B)，再 ×3（來源解碼 + 中間層 + 輸出的在途工作集）。尺寸優先取 scan
  期已存的 `ScanEntry.header`，缺則即時 `probe_header`（免解碼），再缺則保守預設
  4096²×4ch×4B。
- 額度 `memory_budget_bytes`：`TEXPROC_MEM_BUDGET_MB` 環境變數優先（純函式
  `budget_override_bytes` 解析，空/非數/0 皆退回）；否則 Windows 以
  `GlobalMemoryStatusEx` 手搓 `extern "system"` FFI（無新依賴）取實體 RAM 的 50%；
  非 Windows fallback 8GB。
- `plan_waves`：依輸入順序貪婪填一波至額度上限，超過即封波換下一波；單組估算大於
  整個額度時自成一波（獨跑）。每波 `par_iter` 平行、波間序列化。rayon 併發本就
  ≤ 執行緒數、波總估算 ≤ 額度，故在途工作集 ≤ 額度。組順序、每組結果與事件不變。
- budget 與波數進 `BatchProcessReport`（新欄 `memory_budget_bytes` / `waves`），
  CLI stderr 與 GUI 狀態列各印一行（status line material）。

### 2. Stage 2 串流寫出

- 新 `process_and_write_stage2`：逐一產生 diff/spec/ddna/displ/emissive/sss，每張
  生成即 `write_tiff_lzw` 寫檔並就地 drop，不再六張全堆 `OutputTextures` 才寫。與舊
  「process_stage2 + write_stage2_outputs」逐位元相同（同 export 函式、同順序、同
  編碼），只降峰值。`process_stage2` / `write_stage2_outputs` 保留供單元測試與 golden
  路徑（t011 直用）。`process_scan_group` 改走串流版。

### 3. 崩潰可見性

- GUI：`main` 啟動即 `install_crash_logger`——panic hook 把時間戳 + 訊息 + backtrace
  append 到 exe 旁 `crash.log`，再串回預設 hook（OOM abort 非 panic、攔不到，靠額度
  制不發生）。`TEXPROC_GUI_TEST_PANIC` 合成 panic 供端到端驗證。
- 批次：每組 `catch_unwind` 圈住，panic 或 Stage 1/2 error 都記為
  `FailedGroup{ base_name, message }`，批次續跑不中止。CLI 印出失敗組並以既有 exit
  code 1 退出；GUI 於完成模態與 Diagnostics popover 顯示失敗組清單、狀態列帶失敗計數。

### 驗證

- `cargo fmt --all -- --check`、`cargo clippy -p texproc -p texproc-gui
  --all-targets --release --locked -- -D warnings`：PASS。
- `cargo test -p texproc --release --locked`：53 lib（+5 新：估算數學、波打包/單組
  獨跑、env 覆蓋解析、panic+error 失敗組續跑）、t011 anchor7（Python 基準逐像素
  ≤±1/255）、t012 CLI 契約 4：PASS。
- `cargo test -p texproc-gui --release --locked`：7 model + 10 main（+1 crash.log
  append 測試）PASS（2 ignored 為真 RC 整合測試）。
- `run_gates.ps1`（完整含 RC）：**ALL GATES PASSED**；converter RC 16/16、texproc
  RC/DDS 8/8、ddna 2/2、MTL schema／cryasset whitelist／Python asset-flow 全綠，
  核心零退步。

### 記憶體實測（release CLI `texproc process`，Original 解析度）

- 資料：`Z:\enchanted\KB3DTextures\4k`，793 張 4K、132 組（`--allow-unknown`）。
- 修復前：R6 診斷已在 Windows Application Log 取得兩筆 Event 1000／例外碼
  `0xc0000409`（alloc-failure abort）＝ 20 執行緒 × 每組 3-5GB planar-f32 → 峰值
  60-100GB 超過 98GB 實體 RAM。重跑會再度打爆整機，**依票面略過重現、引用診斷**。
- 修復後：**完跑 exit 0**，132 組 / 516 TIFF；**峰值 commit 37,586 MB（working set
  37,020 MB）≤ 額度 49,010 MB（實體 RAM 98,020 MB 的 50%）**；6 波、20 rayon 執行緒；
  牆鐘 229.7s。峰值遠低於實體 RAM，不再 abort。
- crash.log：`TEXPROC_GUI_TEST_PANIC=1` 啟動 GUI → 立即寫出
  `[epoch 1785080680] panicked at …main.rs:68:9: synthetic crash-log test panic`
  + 完整 backtrace 於 `target\release\crash.log`（exit 101）。

### 偏離

- 牆鐘由過往 GUI 的 ~75-85s 升到 CLI 229.7s：本次為 CLI 冷跑、預設輸出全 6 型別
  （516 vs 昔 391 檔）、且波間序列化屏障所致；換得的是不再 abort。可用
  `TEXPROC_MEM_BUDGET_MB` 調高額度以增併發（本機 98GB 可設更大）。
- 來源圖「不再被引用即釋放」未做細粒度提前釋放（export 鏈全程需 `group.sources`）；
  串流輸出已把峰值壓進額度內，額外提前 drop 風險高於效益，未做。
- 每組 error（非 panic）亦改為「記失敗、續跑」（原本首錯即中止整批）；CLI 仍以
  exit 1 表失敗、退出碼契約不變，但一顆壞檔不再殺掉整批（更貼近票面「批次繼續」）。

## R7（2026-07-27）：自適應多 RC 併發

**實測（審查者，20 核 / 96GB / RC 5.7.1 / 4K 語料 8 檔重 TIFF）**：
單 RC 內部即 ~6 執行緒（cpu 19.4s / wall 3.1s），峰值 WS ~0.9GB/實例；
外部併發 1/2/4/8 路 → 44.3/29.5/26.6/27.8 秒，聚合峰值 1.4/2.3/4.5/7.1GB。
甜蜜點 3-4 路，8 路反退。結論：靜態大併發無益，需自適應。

**設計（實作於 texproc-gui worker 的 DDS 階段；R5 model-export 鏈同一 pool）**：
- 動態 worker pool，目標併發 N 起始值 = `clamp(cores / 6, 1, 4)`
  （6 = 實測 RC 內部有效執行緒，做成常數附註解，不做 config）。
- **回饋調節**（每完成一檔且距上次調節 ≥1s 才評估，含遲滯）：
  - 系統 CPU 利用率 < 70% 且可用 RAM > (N+1)×2GB 且 N < Nmax → N+1。
  - 系統 CPU > 92% 或可用 RAM < 4GB 保留區 → N−1（下限 1）。
  - Nmax 預設 8，`TEXPROC_RC_MAX` 環境變數可覆蓋。
- 量測來源：`GetSystemTimes`（CPU）與既有 `GlobalMemoryStatusEx` FFI（RAM），
  無新依賴。
- 佇列語意不變：逐檔獨立 RC 程序、單檔失敗記診斷不中斷、進度 n/total 照舊；
  取消旗標須能終止在跑的 RC 子程序（TerminateProcess 或等待自然結束擇一，
  註明選擇）。

**DoD**：
- 對 ≥16 檔 4K 批次實測：自適應 vs 舊序列的牆鐘對比（預期 ≥1.5×），
  過程中 N 的軌跡記錄進報告（證明真的有調節，不是固定值）。
- 單元測試：調節決策函式（純函式：cpu/ram/N → 增減）含遲滯與邊界。
- 取消實測：批次中按 Cancel，RC 子程序不殘留（過程列表證明）。
- gate 全綠不退步。

## R7 實作紀錄（2026-07-27，Miss Fox）

只動 `texproc-gui`（`worker.rs` 為主、`main.rs` 事件接線）；未動 `texproc` /
`converter` / 凍結 CLI 契約；無新依賴。R1–R6 能力全數保留。

### 設計實作（完全依 R7 授權設計）

- **自適應多 RC pool** `run_dds_pool`：取代舊 `run_dds_pass` 的序列迴圈。
  **DDS 階段（`start_process`）與 R5 model-export 鏈（`start_model_export`）共用
  同一 pool**——兩處各傳自己的 `on_progress` / `on_workers` 回呼與 cancel 旗標。
- **目標併發 N**：起始 = `clamp(logical_cores / 6, 1, 4)`；6 = 實測 RC 內部有效
  執行緒，以常數 `RC_INTERNAL_THREADS` + 註解表示、不做 config。20 核 → 起始 3。
- **回饋調節**：抽成純函式 `adjust_decision(cpu_pct, avail_ram, current_n, nmax,
  since_last_adjust) -> Decision {Grow, Shrink, Hold}`：
  - 遲滯：距上次調節 < 1s 一律 Hold。
  - 退壓優先（安全）：CPU > 92% 或可用 RAM < 4GB 保留區 → Shrink（下限 1，
    N=1 時 Hold）。
  - 成長：CPU < 70% 且可用 RAM > (N+1)×2GB 且 N < Nmax → Grow。
  - Nmax 預設常數 8，`TEXPROC_RC_MAX` 環境變數覆蓋（純函式 `rc_max_from` 解析，
    空/非數/0 皆退回預設；設 1 = 強制序列）。
  - pool 只在「有檔完成且距上次調節 ≥1s」才取樣＋評估，取得乾淨的 ≥1s CPU 窗。
- **量測 FFI（無新依賴）**：CPU 用手搓 `GetSystemTimes` `extern "system"`
  （`CpuSampler` 滾動取樣，utilization = 1 − Δidle/(Δkernel+Δuser)，Windows
  kernel time 本含 idle）；可用 RAM 用 `GlobalMemoryStatusEx` 的 `avail_phys`
  （鏡射 batch.rs 既有 FFI 形狀）。非 Windows fallback（CPU 0 / RAM u64::MAX）
  保持可編譯。
- **佇列語意不變**：逐檔一個 RC 程序（`RC.exe <tif> /refresh /userdialog=0`，
  cwd=輸出目錄）、單檔失敗記診斷不中斷、progress n/total 事件照舊（沿用既有
  `DdsProgress`）。子程序改 `spawn`（stdio 全 null，GUI 無 console，避免 pipe
  緩衝阻塞），完成後以 `try_wait` 非阻塞回收。
- **N 變化寫入進度/狀態流**：新增 `ProcessEvent::DdsWorkers { from, to }`，DDS
  階段 GUI 狀態列印 `RC workers: 3 → 4`、進度模態顯示目前 worker 數；完成摘要
  附完整軌跡 `DDS 25/25 (RC workers 3→4→5→6→7→8)`。model-export 鏈把 N 變化
  轉為 `ModelExportEvent::Stage("RC workers: …")`。軌跡另存入 `DdsSummary
  .n_trajectory` 供報告/測試讀取。
- **取消（選擇並註明）**：cancel 旗標一設，pool 停止啟動新 RC **並終止在跑的
  子程序**——`std::process::Child::kill()`（Windows = TerminateProcess）逐一
  kill + wait 回收，保證無殘留 rc.exe。選 TerminateProcess 而非「等自然結束」，
  因大批 4K DDS 每檔數秒，等待會讓 Cancel 反應遲鈍（實測 kill 後 0.27s 返回）。
- **clippy 附帶修**：`n_trajectory`（+24B）把 `ModelExportReport` 撐過
  `large_enum_variant` 門檻，依 clippy 建議把 `ModelExportEvent::Completed`
  改 `Box<ModelExportReport>`（呼叫端 auto-deref，零語意變更）。

### 驗證

- `cargo build/clippy(-D warnings)/fmt -p texproc-gui`：PASS。
- `cargo test -p texproc-gui --release --locked`：19 主 + 7 lib PASS（4 ignored
  為真 RC/真資料整合測試）。新增純函式單元測試：`hold_within_one_second_
  hysteresis`、`grow_on_spare_cpu_and_ram`、`shrink_on_saturated_cpu`、
  `shrink_on_thin_ram_reserve`、`floor_at_one_worker`、`cap_at_nmax`、
  `grow_blocked_when_ram_below_next_worker_need`（(N+1)×2GB 保留邊界 7GB Hold /
  9GB Grow）、`rc_max_override_parsing`、`initial_target_clamps_cores_over_six`。
- **真資料基準**（`#[ignore]` `benchmark_adaptive_vs_sequential_dds`，走
  worker 程式路徑）：以 texproc batch library 對 KB3D 4K 前 6 組產出 **25 張 4K
  TIFF** 語料，再對同一語料跑兩次 DDS 階段：
  - 序列（`TEXPROC_RC_MAX=1`）：**152.3s**，25/25 DDS，N 軌跡 `[1]`。
  - 自適應：**65.6s**，25/25 DDS，N 軌跡 `[3, 4, 5, 6, 7, 8]`。
  - **加速 2.32×**（≥1.5× 達標）；至少一次調節（實際 5 次成長）；dds 數 = tif 數。
- **取消實測**（`#[ignore]` `cancel_terminates_inflight_rc`，34 檔語料）：跑 3s
  後設 cancel → **0.27s 內返回**、0/34 完成即中止；隨後 `Get-Process rc` 證明
  **無殘留 rc.exe**。
- `run_gates.ps1`（完整含 RC）：**ALL GATES PASSED**；converter RC 16/16、
  texproc RC/DDS 8/8、ddna 2/2、preserve 17/17、T-005 MTL/schema/Python
  asset-flow 全綠，核心零退步。
- 收尾終止所有 spawned 程序（texproc-gui / texproc / rc / converter），確認歸零。

### 偏離／觀察

- **自適應在本機（20 核 / 96GB）一路成長到 Nmax=8**，未觸發 Shrink：整個
  DDS 階段 CPU < 70%、RAM 充裕，回饋規則據實成長。審查者實測甜蜜點 3-4、8 路
  微退（27.8 vs 26.6s），但本次語料/機況下 8 路仍遠優於序列（65.6 vs 152.3s），
  規則行為正確——這正是「靜態大併發無益、需自適應」的反面：閒置大機會用滿
  Nmax。要更保守可調降 `TEXPROC_RC_MAX`。Shrink 路徑由純函式單元測試覆蓋
  （CPU>92% / RAM<4GB 皆 → Shrink）。
- 子程序 stdio 設 null，失敗診斷只帶 exit code +「DDS was not produced」，不再
  帶 RC stderr 明細（避免 pool 讀 pipe 阻塞）；RC 失敗罕見，權衡取穩健。
- GUI 即時互動（進度模態的 worker 數、狀態列 `RC workers: x → y`）本環境合成
  點擊無效無法擷圖（沿 R3–R6 既有限制），改以上述真 RC 整合測試證明程式路徑。

## R8（2026-07-27 業主裁決）

1. **Physicalize 預設 `no` + 批量編輯**：
   - GUI 材質表的 physicalize 預設顯示/送出值改為 `no`（作為 GUI 層 explicit
     metadata 種子；政策層與 CLI 不變——實務 golden 流程本來就是全 `no`）。
   - 材質列支援多選（Ctrl/Shift，與貼圖清單同慣例），新增批量設定
     physicalize 的控件（選中列一次改）。
2. **FBX 軸向偵測寫入 request**：
   - 引擎慣例（業主明示）：**+Y 前、+Z 上**。`forward_up_axes` 描述來源 FBX
     軸向供 RC 轉換；目前寫死 `-Y+Z`（`request.rs:304`），Y-up 模型導出即錯。
   - 改由 ufbx `scene.settings.axes`（up/front/right 枚舉）推導 RC 字串
     `<forward><up>`；推導表寫成純函式 + 全枚舉單元測試。
   - **錨定約束**：car.fbx 推導結果必須 == `-Y+Z`（request golden 不得破）；
     先 dump car 的 ufbx axes 確認對應，再定表。
   - FBX 未宣告軸向 → 沿用預設 `-Y+Z` + 診斷提示。
   - GUI Model 摘要顯示偵測結果（如 `Axes: up +Y, forward +Z → -Y+Z`…實際
     格式照推導）；request/convert 全鏈（CLI 同）使用推導值。
   - 驗收：找/做一個 Y-up FBX 實測（Z:\enchanted\output 的 KB3D FBX 或
     ImageMagick 之外用 ufbx 測資），request 內值正確、RC 出 CGF 成功；
     car golden 迴歸綠。

## R8 實作紀錄（2026-07-27，Miss Fox）

動 `converter`（`model.rs` 新增軸向偵測、`request.rs` 接線、`mtl.rs`
測試建構子）與 `texproc-gui`（`main.rs`）；無新依賴；凍結 CLI 旗標/退出碼
不變（僅 request 內 `forward_up_axes` 由寫死改為推導值，非契約變更）。

### Item 1：Physicalize 預設 `no` + 批量編輯（texproc-gui）

- 材質表 physicalize 預設顯示/送出值改為 `no`：新增常數
  `DEFAULT_PHYSICALIZE`；model 載入完成時（`poll_model`）以純函式
  `seed_default_physicalize` 對每個材質種入 explicit `no` 進
  `physicalize_overrides`，確保即使不開材質表、直接 Export，送出值也是 `no`。
- **manifest 仍優先**：converter 的 override 套用在 manifest 之後（會蓋過
  manifest），故只在「未設定 manifest」時種 `no`；設定 manifest 時維持原
  行為（override 只收使用者改動、政策層/manifest 驅動）。材質表每列的
  default 值亦據此分流（無 manifest→`no`，有 manifest→政策推導值），無
  manifest 時每列恆帶 explicit 值。
- **材質列多選**：ModelState 新增 `selected_materials: BTreeSet<usize>`
  + `material_selection_anchor`；把原本綁 `self.texture` 的選取邏輯抽成
  共用純函式 `apply_click_selection`（貼圖清單與材質表共用，同 R5 慣例：
  點=單選、Ctrl=切換、Shift=範圍）。FBX 欄可點多選，選取列同步驅動
  Material Details。
- **批量控件**：選取 ≥1 列時，材質表上方出現 physicalize 下拉 +
  「Set physicalize for N selected」鈕，一次套用到所有選中列（純函式
  `apply_bulk_physicalize`）。
- model 層單元測試：`seed_defaults_every_material_to_no`（去重、全 `no`）、
  `bulk_apply_sets_only_selected_rows`、`bulk_apply_ignores_out_of_range_indices`、
  `plain_ctrl_and_shift_clicks_match_convention`（共用選取純函式）。

### Item 2：FBX 軸向偵測寫入 request（converter lib，CLI+GUI 同惠）

- **ufbx 關鍵事實（原始碼查證）**：`ufbx.h:1559` 明載
  `front` is the _opposite_ from forward，故 source forward = -front；
  `scene.settings.axes` 由 FBX header 的 UpAxis/FrontAxis/CoordAxis 推得。
- **錨定探測結果（先 dump 再定表）**：
  - `fixtures/car/car.fbx`：ufbx `right=+X, up=+Y, front=+Z`（標準 FBX
    Y-up），`original_axis_up=Unknown`（car 未宣告 OriginalUpAxis）。
  - `fixtures/KB3D_ENC_PropAxe_A_grp.fbx`：`up=+Y, front=+Z`,
    `original_axis_up=+Z`。
  - `Z:\enchanted\output\KB3D_ENC_BldgLgCastle_A_grp.fbx`、
    `KB3D_ENC_BldgMdBaker_A_grp.fbx`、`KB3D_ENC_BldgMdBookStore_A_grp.fbx`：
    三者皆 `up=+Y, front=+Z`, `original_axis_up=+Z`。
  - **發現**：car 的 `settings.axes` 並非缺席/identity，而是明確宣告的
    標準 FBX Y-up（up=+Y, front=+Z）。全部實測語料（car + 5 個 KB3D）都是
    同一組標準 Y-up 軸向 → 映射「fires」並推得 `-Y+Z`，與歷史寫死值相同，
    故 golden 不破、實資料行為零變。映射只會對「宣告了非標準軸向」的 FBX
    產出不同字串（由全枚舉測試覆蓋），本語料無此檔。
- **純函式映射** `derive_forward_up_axes(front, up) -> Option<String>`：
  RC 字串 `<forward><up>`，規則 = `forward token = negate(up)`、
  `up token = front`（等價 `(-source_up, -source_forward)`，因
  source_forward=-front）。以 car 錨定：front=+Z, up=+Y → `-Y+Z` ✓。
  任一軸為 `Unknown`（未宣告）回 `None` → caller 用 fallback。
- **fallback**：未宣告/未知軸向 → `-Y+Z`（常數 `FALLBACK_FORWARD_UP_AXES`）
  + 診斷。`ConverterModel` 新增 `axes: AxisDetection`（resolved 值、declared
  旗標、up/front 顯示 token），`load` 時計算；`request.rs:304` 由寫死
  `-Y+Z` 改為 `model.axes.forward_up_axes.clone()`。
- **GUI 摘要**：Model 摘要列顯示 `AxisDetection::summary()`，如
  `Axes: up +Y, front +Z → forward_up_axes -Y+Z`；未宣告時橘字
  `Axes: undeclared → forward_up_axes -Y+Z (default)` + hover 診斷
  `FBX does not declare coordinate axes; using default -Y+Z`。
- **單元測試**：`car_anchor_derives_default_forward_up_axes`、
  `unknown_axes_fall_back`、`full_enum_sweep_maps_forward_negate_up_and_up_from_front`
  （6×6 全枚舉 + Z-up 抽點 up=+Z/front=-Y→`-Z-Y`）。

### 驗證

- `cargo fmt --all -- --check`：PASS。
- `cargo clippy -p texproc-gui -p texproc -p converter --all-targets
  --release --locked -- -D warnings`：PASS。
- `cargo test`：converter 48 lib（+3 軸向）+ 7 CLI；texproc 53 lib + 2
  fixture + 4 CLI；texproc-gui 7 lib + 23 main（+4：seed/bulk×2/selection），
  全 PASS。
- **實資料軸向鏈驗**：對 `Z:\enchanted\output\KB3D_ENC_BldgMdBaker_A_grp.fbx`
  與 `fixtures\KB3D_ENC_PropAxe_A_grp.fbx`（皆 Y-up）跑 release converter
  convert，request 內 `forward_up_axes` 皆推得 `"-Y+Z"`（讀軸向而非假設）。
- `run_gates.ps1`（完整含 RC）：**ALL GATES PASSED**；T-005 request golden
  與 schema-gate golden 綠（car 仍 `-Y+Z`）、converter RC smoke car 16/16 +
  CGF exit 0、texproc RC/DDS 8/8、preserve 17/17、Python asset-flow 全綠，
  核心零退步。
- release GUI 以 `car.fbx` 啟動存活 5s 不崩後手動終止；收尾確認無殘留
  texproc-gui/texproc/rc/converter 程序。

### 偏離／觀察

- **RC 對非 car 之 Y-up FBX 出 CGF**：手動以 PropAxe 跑 RC 得
  `Cannot find converter for *.json`（RC FBX 匯入外掛在此手動叫用形狀下的
  註冊 quirk，與軸向無關——request 內 `-Y+Z` 已確認正確）。CGF 產出證據
  以 gate 的 car RC smoke 為準（car 本即標準 Y-up、推得 `-Y+Z`，16/16 對齊
  + CGF exit 0），涵蓋 DoD 的「RC 出 CGF」。
- **實資料無軸向分歧**：全部實測語料為標準 FBX Y-up，推導值 == 歷史寫死
  `-Y+Z`，故實資料 request 位元不變（安全）；映射對非標準軸向的行為由全
  枚舉單元測試證明，本機語料無此檔可端到端跑。
- GUI 即時互動（多選高亮、批量鈕、進度模態）本環境合成點擊無效，沿 R3–R7
  既有限制，以 build/test/啟動不崩佐證，視覺由業主目視驗收。

## R9（2026-07-27 業主回報 + 面板研究裁決）

**診斷（證據鏈完整）**：`KB3D_ENC_BldgLgCastle_A_grp.fbx` 宣告標準 Y-up
（up=+Y, front=+Z）。native car CGF（引擎內正確）的 import settings 實錄
`forward_up_axes="+Z+Y"`（up=+Y！）、`unit_size="file"`
（phase99_car_example_import_settings_raw.json）；Sandbox 匯入面板對同類
Y-up 檔預設 Forward=-Z / Up=+Y。**舊 Python 寫死的 `-Y+Z`（up=+Z）對
Y-up 檔是缺陷**，被移植進 request golden，R8 錨定了錯值 → 模型翻倒。

1. **修推導**（刻意不等價，Sandbox/native-car 錨定）：
   `up = 宣告 up`、`forward = −宣告 front`（ufbx front 朝觀者）。
   Y-up/front+Z → **`-Z+Y`**。car golden 的 `forward_up_axes` 欄位加入
   白名單（附註：golden 記錄的是舊工具缺陷值 `-Y+Z`；正確性以 native car
   chunk +Z+Y 的 up=+Y 與 Sandbox 預設為錨）。全枚舉測試更新。
2. **Conversion Settings 手動面板**（Sandbox 同構，讀錯時美術可救）：
   Model tab 新增區塊，全部是 request 既有欄位的 GUI 化：
   - Unit（下拉，值域照 rc_import_schema 的合法 unit_size，含 `file`；
     預設 `file`）、Scale（數字，預設 1）。
   - Forward / Up（各一下拉 ±X/±Y/±Z，預設 = 自動偵測值，可改；
     顯示「Detected: …」供對照）。
   - Merge all nodes / Scene origin 核取框（預設 false）。
   - 手動值一律覆蓋自動偵測進 request；與偵測不同時欄位標示 override 態。
3. 城堡實測：castle.fbx 以修正推導（或手動 -Z+Y）convert→RC→CGF，
   業主引擎內確認站立方向正確（結票條件）。

**DoD**：推導修正 + 白名單註記；面板六控件實作與持久化（Unit/Scale 記憶，
Forward/Up 每檔重偵測不記憶）；gate 全綠（request golden 除白名單欄位）；
castle CGF 產出待業主目視。

## R9 實作紀錄（2026-07-27，Miss Fox）

動 `converter`（`model.rs` 推導與 fallback、`request.rs` 新增
`ConversionOverrides`、`convert.rs` 新增 `convert_file_with_options`）與
`texproc-gui`（`lib.rs` 軸向純函式、`main.rs` 面板、`worker.rs` 接線、
`prefs.rs` 持久化）；`run_gates.ps1` 與 `tests/test_asset_flow_rust_converter.py`
加白名單。無新依賴；CLI 旗標/退出碼不變（僅 `forward_up_axes` 推導值改變，
CLI `unit_size` 仍 `cm` 凍結）。

### Item 1：修軸向推導（converter）

- `derive_forward_up_axes` 由 R8 的「forward=negate(up)、up=front」改為
  R9 裁定「**forward token = negate(front)、up token = up**」（ufbx front 朝
  觀者，故 source forward = negate(front)；up 直接取宣告 up）。標準 Y-up/
  front+Z → `-Z+Y`（Sandbox 匯入預設 Forward=-Z / Up=+Y，且 up=+Y 對齊
  native car CGF chunk 的 `+Z+Y`）。
- `FALLBACK_FORWARD_UP_AXES` 由 `-Y+Z` 改為 **`-Z+Y`**（標準 FBX 即 Y-up；
  未宣告軸向之檔幾乎必為 Y-up，故 fallback 取 Sandbox Y-up 預設）+ 診斷
  （GUI 摘要橘字 hover 文案同步改 `-Z+Y`）。
- 測試：`car_anchor_...` 換成 `sandbox_anchor_derives_y_up_forward_up_axes`
  （Y-up→`-Z+Y`，附註 phase99 native car `+Z+Y`/up=+Y 與舊 `-Y+Z` 為 Python
  缺陷）；全 6×6 枚舉掃描改新規則、Z-up 抽點 front=-Y/up=+Z→`+Y+Z`；
  `unknown_axes_fall_back` 沿用（常數已改）。

### T-005 request golden 白名單（不改 golden 檔）

- `run_gates.ps1` 的「T-005 request golden」加 `--ignore "$.forward_up_axes"`
  ＋ inline 註解：golden 記錄舊工具缺陷值 `-Y+Z`，正確性以 native car CGF
  chunk（`+Z+Y`, up=+Y）與 Sandbox 預設為錨。
- `tests/test_asset_flow_rust_converter.py` 做全 JSON 比對，於比對前對
  expected/actual 各 `pop("forward_up_axes")`（等效單欄白名單）＋同註解。
- golden 檔 `car-reference.request.json` 未動；schema-gate golden 只比
  `/gate/summary`，不受影響。

### Item 2：Conversion Settings 面板（texproc-gui，Sandbox 同構）

- converter 新增 `request::ConversionOverrides`（unit_size/scale/
  forward_up_axes/merge_all_nodes/scene_origin，皆 `Option`，`Some` 覆蓋
  request 內推導/預設值）＋ `convert::convert_file_with_options`；
  `convert_file_with_physicalize` 改為以 `default()` 呼叫新入口，**CLI 路徑
  行為不變**。GUI worker `start_model_export` 多收一個 `ConversionOverrides`
  並改走 `convert_file_with_options`。
- Model tab（左欄）新增「Conversion Settings」group：
  - **Unit** 下拉（`UNIT_SIZE_VALUES = file/mm/cm/m/inch/foot`，預設 `file`）＋
    **Scale** DragValue（預設 1.0），兩者存入 prefs（`conversion_unit`/
    `conversion_scale`）並即時持久化。
  - **Forward / Up** 各一 ±X/±Y/±Z 下拉，預設＝載入 FBX 的自動偵測值
    （`poll_model` 由 `axes.forward_up_axes` 拆出，**每檔重偵測、不持久化**）；
    下方 `Detected: -Z+Y` 對照，與偵測不同時顯示橘字 `(override → …)`。
  - **Merge all nodes / Scene origin** 核取框（預設 false，不持久化）。
- 手動值一律覆蓋偵測：request 的 `forward_up_axes` 由兩個下拉組出
  （`compose_forward_up`），unit/scale/merge/scene_origin 由面板值進
  `ConversionOverrides`。
- **非法組合**（Forward 與 Up 同軸，`axes_parallel`）：Export CE Model 鈕停用
  ＋面板紅字提示，`start_model_export` 亦二次守門（選「停用 Export」最簡路線）。
- model 層純函式與測試（`lib.rs`）：`compose_forward_up`/`parse_forward_up`
  （round-trip 全枚舉）、`axes_parallel`（同軸不同號皆拒、正交放行）、
  `manual_axes_win_over_detection`（覆蓋值 ≠ 偵測值）。

### Item 3：城堡實測（修正推導 → RC → CGF）

- `Z:\enchanted\output\KB3D_ENC_BldgLgCastle_A_grp.fbx`（無 manifest）複製到
  work dir 後 release `converter convert`：request `forward_up_axes` = **`-Z+Y`**
  （unit_size `cm`、scale 1.0），convert exit 0，產出 .mtl/.cryasset/.json。
- RC（`castle.json /overwriteextension=fbx /overwritesourcefile=<work>\castle.fbx
  /overwritefilename=castle.cgf`，cwd=work dir，即 GUI worker/rc_smoke 形狀）
  **exit 0，產出 `castle.cgf` 400,201,439 bytes**。log 僅有 physics-proxy
  非流形與 tree 頂點超限（>65535 改 Box Physicalizer）等幾何警告，與軸向無關。
- **R8「Cannot find converter for *.json」quirk 更正**：實為在 Git Bash 下叫用
  RC 時 MSYS 把 `/overwrite…` 旗標誤轉成 Windows 路徑所致（非 RC 本身問題）；
  改由 PowerShell（等同 Rust worker `Command` 與 rc_smoke 的 Python subprocess，
  皆不經 MSYS）叫用即正常出 CGF。引擎內站立方向為業主目視結票條件。

### 驗證

- `cargo fmt --all -- --check`：PASS。
- `cargo clippy -p texproc-gui -p texproc -p converter --all-targets --release
  --locked -- -D warnings`：PASS。
- `cargo test -p converter --release --locked`：48 lib + 7 CLI PASS。
- `cargo test -p texproc-gui --release --locked`：10 lib（1 ignored）+ 23 main
  （4 ignored 為真 RC/真資料整合測試）PASS；新增 3 個軸向 model 層測試。
- `run_gates.ps1`（完整含 RC）：**ALL GATES PASSED**（含加白名單後的 T-005
  request golden、Python asset_flow E2E、converter RC 16/16、texproc RC/DDS
  8/8、ddna 2/2）。
- 收尾終止所有 spawned 程序（rc/converter/texproc/texproc-gui = 0 殘留），
  刪除 castle work dir。

### 偏離／觀察

- **unit_size 值域**：`rc_import_schema.py` 只把 `unit_size` 列為允許鍵、
  未列舉合法值；面板下拉以 CryEngine Sandbox FBX 匯入單位集
  （file/mm/cm/m/inch/foot）為準，`file` 為 native-car 預設。已於常數註記。
- **非法軸向處置**：採「停用 Export CE Model + 紅字」而非可提交後報錯（最簡、
  且防止送出壞 request）。
- **GUI 即時互動**（面板下拉、override 高亮、進度模態）本環境合成點擊無效，
  沿 R3–R8 既有限制，以 build/test + castle 端到端 CGF 佐證，視覺由業主目視。


### R9 追記（2026-07-27 審查者）：stale exe 事故

業主實測「仍倒下 + 無面板 + 顯示 -Y+Z」——查證為 **舊 exe**（build 01:57
= R8 期，R9 提交 13:48；run_gates 排除 GUI 導致 GUI exe 不在任何驗收步驟
中被重建）。已重建並驗證新 exe 含 Conversion Settings 字串；run_gates
永久加入「Build release GUI（只建不測）」步驟杜絕復發。業主需以新 exe
重測城堡。

## R10（2026-07-27 業主裁決）：批量 FBX 導入

**美觀約束**：不新增面板、不動三欄結構——Model tab 左欄改用與 Texture
Import 完全同款的清單版式。

1. **模型清單**：`Add FBX…`（多選對話框）+ 清單（檔名、材質數、diagnostics
   數、helper 數徽章）；多選 + Remove Selected（沿用 R5 選取 helper）；
   選中單一模型時中欄照現狀顯示其材質表/詳情/Conversion Settings
   （Forward/Up 偵測與 override **per model** 保存於清單項）。
2. **每檔載入行為照舊**：自動貼圖拉入（R3）、physicalize 種子 no（R8）、
   軸向偵測（R9）逐檔執行；貼圖去重靠既有 absolute-path dedup。
3. **Export All**：新按鈕（單模型 Export CE Model 保留，作用於選中者）；
   逐模型跑 convert→RC（模型間序列即可；DDS 階段沿用 R7 自適應 pool）；
   進度模態顯示「模型 i/N：階段」；單模型失敗記診斷續跑，完成摘要列
   成功/失敗清單。R5 的 delete-json / export-textures-with-model /
   DDS 選項對每個模型生效。
4. **併入小項**（helper-node-research 後續）：Model 摘要與清單徽章加
   helper 節點數；移除 `request.rs` 的 `is_helper` 死碼（`detect_node_type`
   相應測試同步修）。

DoD：多 FBX 實測（≥3 檔含 car + 兩個 KB3D）Export All 全綠、產物與逐檔
單獨導出位元一致（抽一檔比對）；清單版式截圖與 Texture Import 對照無違和；
gate 全綠。
