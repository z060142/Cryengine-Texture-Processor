# v2 UI 重構試做 — 交付說明

> 2026-07-31，分支 `v2-ui-refactor`。規格見 [SPEC.md](SPEC.md)。
> 定案設計：`docs/ux-demos/r2-hybrid2-stage-evo.html`（H2 舞台演化）。

## 完成範圍

現有功能**全數**遷移到 H2 新 UI（無新程式功能）；舊 UI 元素全部移除。
main.rs 從 ~3850 行縮到 ~1900 行（狀態/邏輯/worker 輪詢保留），
繪製層全部改由 `texproc-gui/src/ui/` 模組承擔：

| 檔案 | 內容 |
|---|---|
| `theme.rs` | mockup CSS token 逐字轉譯（唯一色彩真相）|
| `icons.rs` | 手繪線條圖示（rail 4 + 面板 8 + misc；無新字型依賴）|
| `widgets.rs` | 折疊面板（●N 徽章 + hover reset）、preset 列、rail 鈕、列元件、pill/chip、toast、任務膠囊 |
| `mod.rs` | UiMode/UiState、per-mode 面板記憶 + preset 機制（含單元測試）、WorkTracker 完成邊緣偵測、版面組裝 |
| `topbar.rs` | 品牌、語言、per-mode 輸出目錄、Profile ▾（settings 檔存取）、診斷 chip |
| `rail.rs` | Textures/Models + 停用的 Proxy/PBR 占位 + Help |
| `timeline.rs` | Work center：live/完成任務膠囊（點擊開 modal、✕ 取消）、完成 toast、session 進度、Convert All / Export All |
| `stage_textures.rs` | 預覽舞台（HUD chips、fitted 影像、caption pills、拖放空狀態）|
| `stage_models.rs` | 材質槽工作區（slots 表 + bulk physicalize、材質細節、診斷、軸向字幕）|
| `stack_textures.rs` | Import / Group Review（12 型別點、搜尋、unknown 指派 DEF-19 規則）/ Conversion Settings（含 Metal Gate 進階）/ RC-DDS |
| `stack_models.rs` | FBX List（含 SUMMARY）/ Transform / Export Options |
| `dialogs.rs` | 三個既有 modal（行為逐字移植）+ 診斷 popover（改錨頂欄）|

i18n：新增 23 key（en+zh-cn），刪除 35 個 v1 死 key（compile-error 驅動清理）。
prefs：新增 `ui_workspace`（面板記憶/preset 持久化），既有欄位不動。
依賴：僅新增 `image`（png feature，workspace 樹內已有同版本）供自我截圖。

## mockup 排除項（依規格 §0，功能不存在故不做）

Proxy/PBR 模式功能（rail 佔位停用）、viewport 視圖切換與 Split、
Material/Model Preview 參數面板、群組級覆寫與批次覆寫編輯器、
群組列 Delete Selected（現有刪除為檔案級，位於 Import 面板）。

## 已知偏差（有意為之）

- 任務膠囊時間戳為 session 相對值（`+MM:SS`）：std 無本地時區格式化，
  不為此加 chrono 依賴。
- RC.exe 路徑欄位同時出現在 Textures→RC/DDS 與 Models→Export Options
  （同一 pref，雙向同步），避免跨模式修路徑的摩擦。
- 面板記憶於 save_preferences / on_exit 時持久化（非每次開合）。

## 開發者工具

- **自我截圖**：`TEXPROC_GUI_SHOT=<png路徑>`（可選 `TEXPROC_GUI_SHOT_FRAMES`，
  預設 40 幀後截取）→ 由 `ViewportCommand::Screenshot` 取 framebuffer 存 PNG
  後自動關閉。視覺 QA 全靠它（見下）。
- 基準圖：`reference/mockup-textures-default.png`、`reference/mockup-models.png`
  （headless Chrome 1280×800 渲染定案 HTML）。

## 環境備忘（本機）

- 以自動化（PowerShell Start-Process）啟動 GUI 時，DWM 桌面呈現可能整窗白畫面
  （framebuffer 自我截圖證實 app 渲染正常；使用者手動啟動不受影響——
  若復現請回報）。螢幕擷取類 QA 一律改用自我截圖。
- `target/debug` 曾被防毒 pending-delete 卡住（LNK1104）；工作时用
  `CARGO_TARGET_DIR=target/v2ui` 繞過，重開機應可清除。
- 螢幕 125% 縮放：外部截圖工具需 SetProcessDPIAware。
