# T-B02 (Backlog) — egui 最小 group 檢視/指派面板

狀態：UI/UX REWORKED／AWAITING OWNER RE-SIGNOFF（2026-07-26；核心、release build 與重做後原生 GUI 煙測已通過）
出處：DEF-17 業主裁決——像素猜測移除後，unknown 的人工指派由 UI 承接（對應舊 PySide `texture_group_panel` 的 unknown 指派功能）。

## 範圍（最小可用）

- 讀 `texproc scan` 的分組 JSON，表列 group × 型別格 × unknown 清單。
- unknown 可下拉指派型別，衝突（DEF-19 warning）高亮顯示。
- 存回修正後的分組 JSON，餵給 `texproc process --groups <json>`（process 需支援吃預先確認的分組——T4 CLI 定形時預留此入口）。
- egui/eframe，單 window，無主題客製。**不做**批次佇列、預覽縮圖以外的影像顯示、設定編輯器。

## 備註

- 依賴：`eframe`（含 egui），僅 texproc-gui 新 bin crate（或 texproc 的 feature-gated bin target，擇小者）；不得污染 texproc lib 的依賴面。版本鎖 minor。
- 接口已就緒（T-012）：`scan --out groups.json` / `process --groups groups.json`；UI 只是消費者，不得繞過或重實作分組邏輯。
- DoD 追加：`run_gates.ps1` 不納入 GUI（無 headless 驗證價值）；`cargo build --release` 產出 gui exe、對 KB3D groups JSON 手動煙測由業主驗收；unknown 指派後存檔 → `process --groups` 可直接吃。

## 實作紀錄（2026-07-26）

- 新增獨立 workspace crate `texproc-gui`；`eframe 0.33`、`serde_json` 與
  workspace `texproc` 只存在 GUI crate。`cargo tree -p texproc --depth 1 --locked`
  證明 `texproc` library 的依賴面未出現 eframe/egui。
- 單視窗 UI 直接 deserialize/serialize `texproc::ScanResult`：
  - 依舊 PySide `texture_group_panel` 回復「群組總覽 → 群組詳情 →
    單一 unknown 指派」的 master-detail 資訊架構；
  - 左側保留舊版 `Base Name / Detected Textures / Unknown` 三欄，並提供
    搜尋與 `Needs review` 篩選；有 unknown 時預設只顯示待處理群組；
  - 右側分開呈現 `Group Details` 與 `Unknown Textures`，一次只對選取的
    unknown 做 `Set Type`；
  - 指派完成後從待處理清單移除該組並自動前進到下一個 unknown；
  - 既有 DEF-19 diagnostics、unknown 計數與被佔用 target 的紅色衝突提示；
  - 被佔用 target 禁止靜默覆蓋；
  - 路徑輸入、拖放載入、另存路徑與 dirty `*`。
- 純 model 不重做 scan/classification；指派只把選定 `ScanEntry` 從
  `unknown` 移到既有 `slots` schema，並更新該 entry 的 `source_type`。
- `run_gates.ps1` 的 core workspace build/test 明確
  `--exclude texproc-gui`，維持「GUI 不進 headless gate」裁決。

## 驗證證據

- `cargo build -p texproc-gui --release --locked`：PASS；
  `target/release/texproc-gui.exe` 產出，大小 `6,748,672` bytes。
- `cargo test -p texproc-gui --release --locked`：4 tests PASS，涵蓋：
  unknown 指派、DEF-19 occupied-target 拒絕、save/ScanResult round-trip、
  version/unsupported slot 拒絕。
- `cargo clippy -p texproc-gui --all-targets --release --locked -- -D warnings`：
  PASS；`cargo fmt --all -- --check`：PASS。
- 原生 GUI 自動煙測：
  - 首輪發現路徑欄擠出 Load/Save，修正為雙列 top bar 後重測通過；
  - 單一 KB3D refraction unknown：載入 `1 group / 1 unknown`，下拉指派
    `diffuse` 後顯示 `0 unknown`，dirty `*` 出現，存檔後清除；
  - 存出的 JSON 由原 CLI
    `texproc process --groups ... --out ...` 無 `--allow-unknown` 直接成功消費，
    exit `0`，產出 `_diff.tif` 與 `_spec.tif`。
- KB3D `Z:\enchanted\KB3DTextures\4k` scan：GUI 載入 `132 groups / 5 unknown`；
  master-detail 群組清單、refraction unknown、下拉選項可見。
- 業主首輪視覺驗收判定 UI/UX 與舊版差距過大；12 欄橫向矩陣已移除。
  重做後再次以 KB3D `132 groups / 5 unknown` 原生視窗驗證：
  - 預設 `Needs review` 只列 5 組並選取第一組；
  - 點選第二組時右側詳情與 unknown 同步切換；
  - `Set Type` 後計數 `5 → 4`、dirty `*` 出現、完成組退出篩選，
    焦點自動前進到下一個待處理組。
- `run_gates.ps1 -SkipRC`：PASS；`run_gates.ps1`：PASS。
  converter RC `0`、material alignment `16/16`；texproc RC/DDS `8/8`、
  DDNA alpha `2/2`。

## 尚待 DoD

- 業主在重做後 release GUI 視窗確認 KB3D group/type/unknown 操作可接受；
  簽核後才能把本票改為 CLOSED。
