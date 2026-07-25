# T-B02 (Backlog) — egui 最小 group 檢視/指派面板

狀態：OPEN（2026-07-25 排程啟動；egui/eframe 依賴已依 D-02 程序獲業主同意，寫入依賴清單）
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
