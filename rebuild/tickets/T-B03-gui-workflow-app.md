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
