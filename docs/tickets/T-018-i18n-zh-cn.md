# T-018 — GUI 多語支援（首發 zh-CN）

狀態：OPEN
業主裁決（2026-07-28）：做多語支援，第一目標 **zh-CN（簡體中文）**。
翻譯政策：**專有名詞保持原樣**（diffuse、normal 等術語不翻，使用者得學
術語才能跟國際接軌），**操作類文字翻譯**（按鈕、選單、狀態、提示）。

## 範圍

- 只做 **texproc-gui**。CLI 輸出與 texproc/converter lib 的診斷訊息維持
  英文（技術診斷屬術語範疇，且 CLI 契約凍結）。
- 語言：`en`（預設）+ `zh-cn`。架構須讓日後加語言 = 加一個 const 實例。

## 機制（零依賴、編譯期完備）

- 新模組 `texproc-gui/src/i18n.rs`：
  - `enum Language { En, ZhCn }`（serde 字串 `"en"` / `"zh-cn"`）。
  - `struct Strings { import_textures: &'static str, … }` —— **一欄一句**，
    `const EN: Strings` 與 `const ZH_CN: Strings` 兩個實例。struct-of-fields
    的好處：**漏譯 = 編譯錯誤**，不需 runtime lookup / JSON 載入 / 新依賴。
  - 帶參數的動態訊息做成方法（`fn removed_n(count) -> String`）或模板欄位
    + `format!` at call site，模板裡用 `{}` 佔位。
- `prefs.rs`：加 `language` 鍵（字串，預設 `"en"`），round-trip 保存。
- 設定區加一個 Language combo（顯示 "English" / "简体中文"）；egui
  immediate mode 下切換即時生效。
- **中文字型**：egui 預設字型不含 CJK——必須掛系統字型（Windows：
  `C:\Windows\Fonts\msyh.ttc` 微軟雅黑，載入失敗時退回預設字型並保持
  英文可用，不得 panic）。用 `std::fs::read` 執行期載入註冊到
  `egui::FontDefinitions`，不內嵌字型檔（版權 + 體積）。

## 翻譯政策（硬規則）

- **不翻**（原樣保留，含在中文句子裡混排）：
  - 貼圖術語：diffuse、normal、specular、gloss(iness)、roughness、
    metallic、albedo、AO、height、displacement、emissive、opacity、
    alpha、SSS、cubemap、HDR
  - 輸出/格式：diff、spec、ddna、displ、em、sss、DDS、TIF、PNG…、
    mtl、cryasset、CGF、FBX、RC、Metal Gate 及全部設定鍵名
  - 檔名、路徑、副檔名、群組名、軸向記號（+Y、-Z+Y…）
- **翻**：動詞/操作（Import、Export、Browse、Remove、Add Related、
  Convert、Cancel…）、面板標題、狀態訊息的敘述部分、tooltip、
  錯誤訊息的操作指引部分。
- 範例：「Import textures」→「导入贴图」；「Delete TIF after DDS export」→
  「导出 DDS 后删除 TIF」；「Groups」→「贴图组」；「Physicalize」保留原樣。

## 驗收錨點

1. 文字全面路由：main.rs 的使用者可見字面量全部改走 i18n（審查將 grep
   殘留英文 UI 字面量抽查；動態 format 訊息含模板）。en 實例與現行文字
   逐字相同（英文模式位元不變）。
2. zh-CN 實例：術語混排正確（抽查含 diffuse/DDS/TIF 的句子，術語必須
   原樣出現）；簡體用字。
3. prefs round-trip：`language` 保存/載入；預設 en；未知值退回 en。
4. 字型：zh-CN 下中文可顯示（截圖證據）；字型檔缺失時不 panic、UI 仍可用。
5. `cargo test -p texproc-gui --release` 全綠；`run_gates.ps1` 全綠
   （GUI build 步驟確保 exe 重建）。

## 明確禁止

- 不新增依賴。不內嵌字型檔。不動 CLI/lib 診斷文字。不翻術語。
- 不做 en/zh-cn 以外的語言（架構預留即可）。

## DoD

- 錨點全數通過；回報：i18n.rs 結構、字串欄位數、字型載入策略與
  fallback 行為、zh-CN 模式截圖路徑。

## 實作紀錄（2026-07-28，Miss Fox）

狀態：DONE（待審）。範圍僅 texproc-gui，未動 converter/ce-schema/texproc/legacy/CLI。

### i18n.rs 結構
- `enum Language { En, ZhCn }`：`from_code(&str)`（未知→En）、`code()`
  （`"en"`/`"zh-cn"`）、`endonym()`（`"English"`/`"简体中文"`，語言選單顯示，
  不翻譯）、`strings() -> &'static Strings`。
- `struct Strings`：**251 個 `&'static str` 欄位**，每欄一句 UI 字串；帶參
  數者存 `{}` 模板。兩個 const 實例 `EN` / `ZH_CN`——漏譯即編譯錯誤，零
  runtime lookup、零 JSON、零新依賴。
- `pub fn fill(template, &[&str])`：依序把 `{}` 換成參數，供 call site 用
  （因 `format!` 需字面量，動態訊息一律走 `fill`）。多參數訊息（如
  processing_complete_status 6 參）維持同一佔位順序，中文照排。
- 翻譯政策落實：術語原樣（diffuse/normal/spec/gloss/roughness/metallic/
  albedo/AO/displacement/emissive/SSS/DDS/TIF/mtl/CGF/FBX/RC/Metal Gate/
  Physicalize/Forward/Up/軸向 -Z+Y/設定鍵名/檔名副檔名），只翻操作文字。

### 路由範圍
- main.rs（~3800 行）全數 UI 字面量改走 `WorkflowApp::t()`（回傳
  `&'static Strings`，不借用 self，可與 `&mut self` 並存）或 `fill`。涵蓋
  top_bar/status_bar/diagnostics/三個 modal/左右面板/groups 表/model
  workspace/所有 status 訊息與 dialog 標題/hint/tooltip。
- `path_row` 共用函式新增 `browse_label` 參數，5 處呼叫傳 `t.browse`。
- **EN 逐字對照現行文字**（含 `\` 續行、`·`/`→`/`…` 等符號），English
  模式位元不變。
- 蓄意保留為英文字面量（政策允許）：產品名 APP_TITLE、檔案對話框 filter
  spec（IMAGE/FBX/JSON_FILTER）、enum 值標籤（albedo/diffuse_ao/ARM/ORM/
  RMA/Original/physicalize 值/unit 值）、severity 鍵（Warning/Error/Info）、
  RcPathResolution.source 鍵（RC Path/CE_RC_EXE/default RC）、Metal Gate、
  Physicalize、FBX 欄名、路徑範例 hint、內嵌貼圖 IO 內部錯誤、lib 診斷內容。

### 語言選單
- 右側 Output Settings 頂部新增 Language combo（`language_selector`），
  顯示 English / 简体中文；egui immediate mode 下切換即時生效並存檔。

### prefs
- 新增 `language: String`（預設 `"en"`），依現有欄位模式 round-trip。
- `normalize_language()`：載入時 `"zh-cn"` 保留、其餘（空/未知/legacy）→
  `"en"`。存檔寫 `self.language` 原值，正規化只在載入端。

### 字型載入策略 + fallback
- 啟動時於 eframe creation callback 無條件呼叫 `install_cjk_font`
  （只加 fallback glyph，不影響英文）。
- `load_cjk_fonts(path) -> Option<FontDefinitions>`：`fs::read` 系統字型
  `C:\Windows\Fonts\msyh.ttc`（微軟雅黑），成功則以 owned `FontData` 掛到
  Proportional + Monospace family 末端當 fallback；**讀取失敗回 None、
  絕不 panic**，caller 保留 egui 預設字型（英文仍可用）。不內嵌字型檔。
- 結構化為可測純函式：bogus path 走 None 分支（單元測試驗證）。

### 測試（cargo test -p texproc-gui --release，31 passed / 6 ignored 全綠）
- `i18n::tests::fill_replaces_in_order`、`language_round_trips_and_falls_back`
- `prefs::tests::language_defaults_to_en`、`language_normalizes_unknown_to_en`、
  `language_survives_save_load_round_trip`（LOCALAPPDATA 隔離的磁碟 round-trip，
  含未知碼→en）
- `rc_path_tests::missing_cjk_font_is_graceful_none_not_panic`、
  `present_cjk_font_registers_fallback`

### 證據
- 錨點 1（路由 + EN verbatim）：reviewer grep 殘留英文 UI 字面量僅剩上列
  蓄意保留項。
- 錨點 2/4（zh-CN 正確 + 字型渲染）：截圖 `docs/ux-demos/t018-zh-cn.png`
  （PrintWindow 對 glow swapchain 回黑，改用前景視窗 rect 螢幕截圖）。
  可見「贴图导入/模型导入/转换设置/输出设置/语言/另存为…」等操作文字翻譯，
  FBX/Physicalize/Forward/Up/-Z/+Y/no/Diffuse/RC Path/CE Model/KB3D_* 術語原樣。
- 錨點 3：見 prefs 測試。
- 錨點 5：`cargo test -p texproc-gui --release` 全綠；
  `.\run_gates.ps1 -SkipRC` → ALL GATES PASSED（RC smoke 為 RC-gated 選配步驟）。

## 審查紀錄（2026-07-28，協調者）

- 獨立重跑：texproc-gui 42 測試全綠、完整 `run_gates.ps1` 全綠（含真 RC
  smoke——Fox 用 -SkipRC，審查補跑完整版）。
- 截圖親驗（t018-zh-cn.png）：中文渲染正常（微軟雅黑 fallback 生效）、
  簡體用字正確、操作文字全翻（贴图导入/模型导入/转换设置/另存为…）、
  術語原樣混排（FBX/Physicalize/Forward/Up/-Z+Y/RC Path/Diffuse/DDS/TIF）。
- 殘留字面量 grep：僅剩 `"Metal Gate"` checkbox 一處，屬政策允許的術語
  保留項；其餘蓄意保留清單（enum 值標籤、filter spec、severity 鍵）合規。
- 偏差接受：severity/RC-source 鍵維持英文（兼作內部 match 鍵 + 診斷英文
  規則）；截圖用前景視窗抓屏（PrintWindow 對 OpenGL swapchain 回黑，
  合理）。
