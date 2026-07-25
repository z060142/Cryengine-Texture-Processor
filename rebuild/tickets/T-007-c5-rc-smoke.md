# T-007 (C5) — RC.exe 實跑 smoke

狀態：OPEN
上游文件：`fbx-converter-migration.md` C5 里程碑；T-006 凍結的 CLI 契約
RC 位置：`S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe`（見 docs/material_override_batch.md 的舊指令）

## 前置閱讀

1. `tools/rc_smoke_test.py` — 舊 smoke 流程：request+MTL 餵 RC → 檢查 CGF 產出 → material report / gate。
2. `utils/cgf_material_reader.py` — CGF 材質 chunk 讀取（名稱表 + physicalize_types）。
3. `fixtures/car/car.fbx_material_manifest.json` 的 `expect_cgf_material_ids` — CGF 端期望值已在 manifest 裡。
4. `docs/car_rc_smoke_mtl_schema_gate.json` — 舊 smoke 的 gate 基準。

## 工作內容

1. 新增 Python 驗證腳本 `tools/rc_smoke_rust.py`（stdlib only）：
   - 以 Rust `convert` 產出 request + MTL（work dir 佈局照舊流程：`rc_work/`）。
   - 呼叫 RC.exe（路徑走 `--rc` 參數或 `CE_RC_EXE` 環境變數）。
   - 驗證：RC 退出碼 0；CGF 檔存在；`cgf_material_reader` 讀出的材質名稱序
     與 slot 對齊 manifest 的 `expect_cgf_material_ids`；`mtl_schema_report`
     對產出 MTL 的 schema gate 綠。
   - 產出 smoke 報告 JSON（形狀比照舊 `car_rc_smoke_*`，僅含能誠實產生的區塊）。
2. 對 car 實跑一次，報告存 `docs/rust_rc_smoke_car.json`。
3. `run_gates.ps1` 增加**選配** RC 段：偵測到 `CE_RC_EXE` 或預設 RC 路徑存在才跑，
   否則印 SKIP（CI 無 RC 環境時 gate 仍可全綠）。

## 明確禁止

- 不動 Rust CLI（契約已凍結；若 smoke 暴露 CLI 缺陷，停下回報開新票）。
- 不比對 DDS/貼圖內容（texproc T5 的事）。
- 不新增 Rust 依賴；Python stdlib only。

## DoD

- `python tools/rc_smoke_rust.py --fbx rebuild/fixtures/car/car.fbx ...` 實跑 RC 全綠，報告與指令貼回報。
- CGF 材質序核對 16/16 + placeholder 判定明確記錄。
- `run_gates.ps1` 在無 RC 環境 SKIP、有 RC 環境全綠，兩種都驗證過。
- 與舊 `car_rc_smoke_mtl_schema_gate.json` 的差異列舉（零差異也明說）。
