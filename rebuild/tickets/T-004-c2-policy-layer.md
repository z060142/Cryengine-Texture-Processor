# T-004 (C1+C2) — converter 內部模型 + 政策層

狀態：OPEN
上游文件：`fbx-converter-migration.md` §2.1（前四列）、§2.3、`rust-workspace-design.md` §4、T-003 結論
前情：讀取層已由 T-003 的 dump 實質完成，C1 不另開票；本票把 dump 的即拋結構升級為內部模型，並在其上實作政策層。

## 前置閱讀（動手前必讀，含對應測試檔）

1. `model_processing/rc_material_policy.py` + 其測試 — `RC_MAX_SUB_MATERIALS=128`、physicalize 正規化、名稱推斷 proxy。
2. `model_processing/material_index_assigner.py` + 測試 — 指派優先序：explicit → `fbx_id−1` → MTL child order → first free；deleted/dummy 判定；診斷附掛。
3. `model_processing/material_slot_table.py` + 測試 — `<unassigned>` placeholder 三規則、expanded slot table、trailing slot。
4. `model_processing/material_slot_mapping.py` + 測試 — slot mapping contract 規則表與狀態機。
5. T-003 結論：`fbx_material_id = typed_id + 1`（one-based）、raw slot = `typed_id`；材質採檔案序。

## 工作內容

1. converter 改為 lib + thin main。內部模型：MaterialRecord（name、typed_id、element_id、texture refs 保留 filename/relative/absolute 三原始欄位 + embedded 標記）、mesh 槽表、場景樹。dump 子命令改吃內部模型，輸出形狀不變（T-003 報告是 regression 基準，僅允許欄位新增）。
2. 政策層四個 module（對應前置閱讀 1–4）：
   - `rc_policy`：常數、`enum Physicalize` 與正規化、proxy 名稱推斷 pattern 表。
   - `index_assigner`：`fn assign_sub_indices(...) -> (assignments, Vec<Diagnostic>)`，優先序照 Python；fbx id 語意用 T-003 結論。
   - `slot_table`：placeholder 三規則、expanded table、trailing slot。
   - `slot_contract`：contract 狀態機，**輸出 JSON 形狀與現有 docs/*.json 逐鍵相同**。
3. 測試移植：`test_material_index_assigner`、`test_material_slot_mapping`、`test_material_slot_table`（遷移計畫 §2.4 第一組中屬於這四個 module 的部分）。移植斷言語意，不移植 Python 測試骨架。
4. 新增 `converter report <in.fbx> --out report.json`（暫名，C3 定形時可整併）：跑政策層產出 material report 與 slot evidence。

## Golden 比對（DoD 核心）

以 car.fbx 對照下列既有證據，逐鍵相等，白名單僅限：時間戳、絕對路徑、
路徑分隔符差異（T-003 備註 1）：

- `docs/car_direct_rc_export_material_report.json`
- `docs/current_car_user_flow_material_slot_evidence.json`（含 slot 16 `<unassigned>` placeholder）
- `docs/phase104_car_trailing_unassigned_material_report.json`

比對腳本：優先沿用 `tools/` 既有 Python 比對器；若無現成的，寫一個最小
`tools/compare_json_golden.py`（鍵路徑白名單制）供之後 C3/C4 重用。

## 明確禁止

- 不動 .mtl / request JSON 序列化（C3 的事）。
- 不新增依賴。
- 白名單不得超出上述三類——任何其他不一致都是 bug 或需回報的政策差異，不准塞白名單。
- golden 對不上時不准「調整輸出湊答案」——先查是政策移植錯誤還是 Blender/ufbx 語意差，後者回報業主裁決。

## DoD

- `cargo test -p converter` 全綠（含移植測試）。
- 三份 golden 逐鍵通過，比對指令與輸出貼在回報。
- dump 對 T-003 報告無 regression（欄位只增不改）。
- 回報：每個 Python 測試檔移植了哪些 case、放棄了哪些及原因；golden 比對中遇到的所有白名單命中列表。
