# T-B02 (Backlog) — egui 最小 group 檢視/指派面板

狀態：BACKLOG（T 線 T5 完工後開工）
出處：DEF-17 業主裁決——像素猜測移除後，unknown 的人工指派由 UI 承接（對應舊 PySide `texture_group_panel` 的 unknown 指派功能）。

## 範圍（最小可用）

- 讀 `texproc scan` 的分組 JSON，表列 group × 型別格 × unknown 清單。
- unknown 可下拉指派型別，衝突（DEF-19 warning）高亮顯示。
- 存回修正後的分組 JSON，餵給 `texproc process --groups <json>`（process 需支援吃預先確認的分組——T4 CLI 定形時預留此入口）。
- egui/eframe，單 window，無主題客製。**不做**批次佇列、預覽縮圖以外的影像顯示、設定編輯器。

## 備註

- 依賴新增（egui/eframe）屆時需業主批准（D-02 封頂原則）。
- T4 的 CLI 需求：`scan --out groups.json` 與 `process --groups groups.json` 這對接口先做好，UI 只是接口的消費者。
