# T-006 (C4) — CLI 定形 + Python E2E 接軌

狀態：DONE（2026-07-25 審查通過：run_gates.ps1 獨立實跑 ALL GATES PASSED（48 Rust 測試、7 組 golden 零差異、asset_flow 28 passed/2 skipped）；退出碼契約已入 --help 並有 process-spawn 測試；CLI 契約自此凍結）
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

## CLI 凍結契約（2026-07-25）

本票沒有 breaking CLI 調整。`--out` 明確表示一個輸出檔；只有同時產生 request
與 MTL 的 `convert` 使用 `--out-dir`。此差異是輸出基數的語意，不再視為命名不一致。

| 子命令 | 凍結旗標 | 成功輸出 |
|---|---|---|
| `dump <in.fbx>` | `--out <evidence.json>`（必填） | 指定的單一 ufbx evidence JSON |
| `report <in.fbx>` | `--manifest <m.json>`（選填）、`--out <report.json>`（必填） | 指定的單一政策 report JSON |
| `convert <in.fbx>` | `--manifest <m.json>`、`--overrides <o.json>`、`--texture-dir <dir>`（皆選填）、`--out-dir <dir>`（必填） | `<request source stem>.json` + 同 stem `.mtl`；stdout 為兩路徑 JSON |
| `validate <request.json>` | `--out <gate.json>`（選填） | 指定 gate；省略時為 request 同目錄的 `<request stem>.schema_gate.json` |

全域退出碼：

| code | 契約 |
|---:|---|
| 0 | 成功 |
| 1 | 其他 operational error，例如建立或寫入輸出失敗 |
| 2 | clap 引數錯誤，或 FBX / manifest / overrides / texture dir / request 輸入錯誤 |
| 3 | 僅 `validate`：gate 已寫出，但 request schema/type/value 驗證失敗 |

`converter --help` 已列出相同退出碼。Rust integration tests 實際 process-spawn
驗證 help/0、clap/2、missing input/2、schema gate/3、output I/O/1。
此後修改子命令、旗標、命名或退出碼均須另開 ticket。

## Python asset_flow 測試遷移清單

接軌：

- `test_asset_flow_rust_converter.py::test_rust_converter_asset_flow`
  透過 stdlib `subprocess` 呼叫真實 Rust CLI；exe 取
  `CE_CONVERTER_EXE`，未設定時預設
  `rebuild/target/release/converter.exe`。
- 同一 case 覆蓋 `dump` 位元 golden、`report` 兩份政策子樹、
  `convert` request + generated MTL，以及 `validate` default gate 命名與 summary。

skip：

- `test_asset_flow_validator.py::test_rc_case_collects_acceptance_checks`：
  舊 bpy + RC.exe mock harness 屬 C5/現場 RC 範圍；converter 部分由上述真實
  subprocess case 取代。
- `test_asset_flow_validator.py::test_rc_case_defaults_manifest_to_work_dir_and_passes_it_to_rc`：
  舊 bpy manifest generation；由 T-004 Rust manifest-injection tests 與上述
  subprocess case 取代。

刪除：**無**。其餘 `test_asset_flow_*` 純 spec builder、texture-process、
report formatting、baseline 與 acceptance-gate 測試保留。

## 一鍵 gate

統一入口：

```powershell
cd rebuild
.\run_gates.ps1
```

腳本僅支援 PowerShell；不可改由 Git Bash 包裝，避免 MSYS 將 JSON pointer
（例如 `/request_materials`）轉換成檔案路徑。腳本：

1. `cargo build --workspace --release --locked`
2. `cargo test --workspace --release --locked`
3. T-003 dump hash + T-004 三組 golden
4. T-005 request / generated MTL / schema-gate golden
5. 全部 `test_asset_flow_*.py`，並注入 release `CE_CONVERTER_EXE`

任何 native step 非零即 throw 並讓腳本非零退出；temp evidence 在 `finally`
清理，原有 `CE_CONVERTER_EXE` 與目前目錄會還原。

## DoD 執行結果（2026-07-25）

```text
cargo build --workspace --release --locked
  PASS

cargo test --workspace --release --locked
  ce-schema unit:       5/5
  converter unit:      38/38
  CLI integration:      5/5
  total:               48/48

T-003 dump SHA-256:
  332F2A2ADB5DB0210797321C6F8F7ADB92AD9E94E1BC8C8543CD717049BB8FC0

T-004:
  direct RC request materials:       68/68, 0 mismatch, 0 whitelist
  trailing unassigned materials:     68/68, 0 mismatch, 0 whitelist
  current material-slot evidence:    68/68, 0 mismatch, 0 whitelist

T-005:
  request JSON:                     171/171, 0 mismatch, 0 whitelist
  generated MTL normalized tree:   999/999, 0 mismatch, 0 whitelist
  schema-gate summary:                4/4, 0 mismatch, 0 whitelist

Python asset_flow:
  28 passed, 2 skipped

run_gates.ps1:
  ALL GATES PASSED
```

沒有執行 RC.exe、沒有修改 texproc 行為、沒有新增 Rust dependency；
Python 新接軌程式只使用 stdlib。
