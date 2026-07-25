# T-004 (C1+C2) — converter 內部模型 + 政策層

狀態：REOPENED（2026-07-25 審查裁決，見文末「審查裁決」節；剩餘工作為 manifest 注入 + 子樹 golden 重跑）
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

## Fox 執行結果

### 已完成

- converter 已拆成 lib + thin main；ufbx 讀取結果升級為 `ConverterModel`、
  `MaterialRecord`、mesh slot/face 分佈、texture refs 與場景樹。
- `dump` 改由內部模型投影，對 T-003 car baseline 的 SHA-256 完全相同：
  `332F2A2ADB5DB0210797321C6F8F7ADB92AD9E94E1BC8C8543CD717049BB8FC0`。
- 已實作 `rc_policy`、`index_assigner`、`slot_table`、`slot_contract`。
- `slot_contract` 有單元測試直接與 `ce-schema/data/converter_schema.json` 的
  `material_slot_mapping` 整段逐鍵相等。
- 已新增 `converter report <in.fbx> --out report.json`。報告明示
  `material_slot_evidence` 是 source-FBX policy projection，不冒充 CGF readback。
- 新增 `tools/compare_json_golden.py`：遞迴逐鍵比較、JSON pointer 子樹選取、
  明示 key-path whitelist、路徑分隔符模式，並列出所有 whitelist hits。

### Python 測試移植

`test_material_index_assigner.py`：

- 已移植：MTL child order 解析；fbx id 優先於既有 MTL；fbx slot 保留；
  MTL name fallback；explicit/fbx/first-free 優先序；deleted 與已知使用量 hazard；
  explicit remap 無警告；duplicate explicit slot；slot-name conflict；
  case-insensitive collision；Blender `.001` 名稱保留；explicit 與 fbx id 超過
  128 的正規化/診斷。
- 未直接移植：malformed bool/float `sub_index`。Rust API 的
  `Option<i32>` 在進入政策層前已由型別拒絕，不存在 Python 動態 coercion 分支。

`test_material_slot_table.py`：

- 已移植：gap placeholder、metadata 保留、trailing `<unassigned>`、
  已有 unassigned 不重複追加、slot 127 不追加、empty default、deleted/out-of-range
  不輸出、`fill_gaps=false`。
- 未移植：`material_manifest_info` 先重排/釘死 slot 的單一 case。臨時
  `report <fbx>` CLI 沒有 manifest 參數，且 repo fixture 未附 car manifest；
  這也是本票 golden physicalize 差異的直接原因。

`test_material_slot_mapping.py`：

- 三個 case 全部移植：final slots/gaps/deleted 狀態、duplicate/out-of-range
  計數、對外 assignment policy；另加 frozen schema 整段相等測試。

`rc_material_policy.py`（repo 無獨立對應測試檔）：

- 新增 Rust 測試涵蓋 128 上限、五種 physicalize 正規化、unknown fallback
  warning、proxy pattern 與一般 `no_collide` 推斷。

### Golden 實跑與 blocker

使用：

```text
python tools/compare_json_golden.py EXPECTED ACTUAL \
  --expected-pointer /request_materials \
  --actual-pointer /golden_policy_projection/request_materials
```

對 `car_direct_rc_export_material_report.json` 與
`phase104_car_trailing_unassigned_material_report.json`：

- 17 rows 的 order/name/sub_index 全部一致；52 個 scalar 逐值相等。
- 非白名單差異共 16 筆，全部是 `$[0..15].physicalize`：
  golden = `no`，C2 raw-FBX policy projection = `no_collide`。
- 原因：golden 的 `no` 來自 manifest/request explicit metadata；
  本票 CLI 只有 `<in.fbx> --out`，fixture 也沒有 car manifest。依既有
  `resolve_rc_physicalize()`，無 explicit metadata 的一般名稱必須推斷
  `no_collide`；改成 `no` 只為湊 golden 會違反本票禁止事項。

完整報告逐鍵比較也無法在 C2 成立：

- `car_direct_rc_export_material_report.json`：47 個結構差異
  （33 missing、14 extra）。
- `phase104_car_trailing_unassigned_material_report.json`：27 個結構差異
  （16 missing、11 extra）。
- missing 的資料是 RC 結果、CGF chunk/readback、request、MTL、
  import-settings alignment、MTL/texture gates；它們屬 C3/C5，無法由
  `report <fbx>` 誠實產生。

對 `current_car_user_flow_material_slot_evidence.json`：

- 57 個 scalar 相等；245 個結構/值差異（123 missing、105 extra、17 value）。
- 16 個實際材質的 slot/name/used 狀態在 source projection 一致，但 golden
  要求 manifest/request/MTL/CGF 四方 readback 欄位及
  `matched_used_slot`；C2 只有 source-FBX，故刻意輸出
  `source_slot_projected`，不偽造 `cgf_mtl_name` 或 `used_by_cgf`。

三次比較的 whitelist hits 均為空；沒有用時間戳、絕對路徑或分隔符白名單
掩蓋任何差異。

### 最終驗證

- `cargo test --workspace --release --locked`：通過，`ce-schema` 5/5、
  `converter` 22/22。
- `cargo test -p converter --locked`：Windows 既有 debug build-script 執行權限
  問題會報 `存取被拒。 (os error 5)`；以隔離的 `CARGO_TARGET_DIR` 與
  `CARGO_PROFILE_DEV_BUILD_OVERRIDE_OPT_LEVEL=3` 重跑後通過 22/22。
- `cargo clippy --workspace --release --locked -- -D warnings`：通過。
- `cargo fmt --all -- --check`：通過。
- comparator 自驗（同一份 JSON 對自身）：197 個值一致、0 mismatches、
  0 whitelist hits。
- `converter report fixtures/car/car.fbx`：16 個 source materials、16 個 emitted
  materials、17 個 slot rows（含 trailing `<unassigned>`）、0 diagnostics。
- `git diff --check`：通過（僅 Git 提示現有 Windows LF/CRLF checkout 轉換）。

### 所需裁決

以下兩者需擇一，否則本票無法同時遵守 C2 範圍與「三份完整 golden 逐鍵相等」：

1. 將 T-004 golden 限定為 C2 可產生的 assignment/slot policy projection，
   完整 material report 與 CGF slot evidence 延至 C3/C5。
2. 擴大本票與 CLI，加入 manifest/request/MTL/CGF 輸入及 readback；這會跨入
   票單明確禁止的 C3/C5 範圍。

## 審查裁決（2026-07-25）

審查者獨立驗證後裁決如下。physicalize 歸因**證實**：golden 流程的 rc_work
目錄存在 `kb3d_citycarsessentialssedan-native.fbx_material_manifest.json`，
16 個材質全帶 explicit `"physicalize": "no"`；舊流程經
`material_manifest.py:457` 合併注入，`resolve_rc_physicalize` 走 explicit
分支。Fox 的移植正確，`no_collide` 是無 manifest 時的正確輸出。

裁決 = 兩案的交集，不是二選一：

1. **manifest 注入納入本票**（非 C3/C5 範圍——manifest 是政策層輸入，
   遷移計畫本就傾向保留它作為測試注入口）：
   - manifest 已收進 `fixtures/car/car.fbx_material_manifest.json`。
   - `converter report <in.fbx> --manifest <m.json>` 讀取 manifest，
     材質合併語意照 `material_manifest.py`（name 對 slot、explicit
     physicalize 等 metadata 注入）。
   - 這同時解鎖 slot_table 先前未移植的 `material_manifest_info` case，
     一併補上。
2. **golden 範圍限定為 C2 子樹**（採 Fox 案 1）：
   - 三份 golden 各比對 C2 可誠實產生的子樹：`request_materials`
     全欄位（含 physicalize，帶 manifest 跑）、slot evidence rows 的
     source 側欄位（slot/name/used/placeholder）。
   - RC/CGF readback、MTL、gate 區塊延至 C3/C5 驗收，屆時做全報告逐鍵。
   - 「不冒充 CGF readback、輸出標示 source projection」的做法**正確**，
     保持。

### 重開後的 DoD

- `report --manifest` 對 car 跑出 `physicalize` 16/16 == `no`，
  與 golden `request_materials` 子樹全欄位逐鍵相等（含 trailing slot 17 筆）。
- 無 manifest 跑維持 `no_collide`（政策正確性回歸測試固定此行為）。
- slot_table 的 manifest case 測試補上。
- 其餘 DoD（測試綠、dump 無 regression）不變。
