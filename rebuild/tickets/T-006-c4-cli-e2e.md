# T-006 (C4) — CLI 定形 + Python E2E 接軌

狀態：OPEN
上游文件：`fbx-converter-migration.md` §2.4「保留為 Python 端到端驗證」、C4 里程碑；`rust-workspace-design.md` D-09

## 前置閱讀

1. `tests/` 中 `test_asset_flow_*` 系列 — 現有 E2E 的斷言內容與夾具。
2. `tools/asset_flow_validator.py`、`tools/asset_flow_acceptance_gate.py`、`docs/asset_flow_acceptance_baseline.md` — 驗收 gate 的形狀。
3. T-004/T-005 票尾的 golden 指令（validator 應覆蓋同樣的比對）。

## 工作內容

1. **CLI 定形**：盤點四個子命令（dump / report / convert / validate）的旗標與輸出檔命名，收斂不一致處（如 `--out` vs `--out-dir`、gate 檔預設名）。若有 breaking 調整，列清單於回報；此後 CLI 契約凍結，變更需開票。
2. **退出碼契約**：0 = 成功；2 = 輸入/引數錯誤；3 = gate 失敗（validate 發現 schema 違規）；1 = 其他錯誤。寫進 `converter --help` 與本票。
3. **Python E2E 接軌**：`test_asset_flow_*` 中與 converter 相關者改為 subprocess 呼叫 Rust CLI（exe 路徑經環境變數 `CE_CONVERTER_EXE` 注入，預設 `rebuild/target/release/converter.exe`）。bpy 依賴的 case 標記 skip 並註明由哪個 Rust 測試取代。
4. **一鍵驗收腳本**：`rebuild/run_gates.ps1` —— build → cargo test → T-004/T-005 全部 golden 比對 → asset_flow E2E，任何一步失敗即非零退出。這是之後每張票的統一回歸入口。

## 注意事項

- 比對腳本在 Git Bash 下會被 MSYS 路徑轉換咬到（`/request_materials` 被改寫成檔案路徑）——run_gates 用 PowerShell 寫，文件註明 shell 要求。
- 不動 texproc；不跑 RC.exe（C5）。
- 不新增 Rust 依賴。Python 側僅可用 stdlib。

## DoD

- `run_gates.ps1` 在乾淨 checkout（含 fixtures）一鍵全綠，輸出貼回報。
- 改動後的 asset_flow 測試清單：接軌 / skip（附取代者）/ 刪除（附理由）。
- CLI 契約表（子命令 × 旗標 × 退出碼）寫入本票，作為凍結基準。
