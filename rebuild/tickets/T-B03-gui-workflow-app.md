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
