# T-005 (C3) — request JSON + .mtl 序列化

狀態：OPEN
上游文件：`fbx-converter-migration.md` §2.1（後五列）、`rust-workspace-design.md` D-09/D-10、T-004 產出

## 前置閱讀

1. `output_formats/rc_import_schema.py` + 相關測試 — request 欄位 schema、必填欄位、animation/joint physics 欄位。
2. `output_formats/rc_request_builder.py` — node 階層處理（helper/proxy 判定、joint physics 關係）、import request 組裝。場景樹來源改用 T-004 內部模型（ufbx），`extract_blender_scene_hierarchy` 不移植。
3. `output_formats/mtl_exporter.py` + `output_formats/cryengine_mtl_schema.py` — MTL XML 結構、shader/GenMask/StringGenMask/MtlFlags/PublicParams、貼圖 map 寫出規則（經 ce-schema 查表）。
4. `docs/material_override_batch.md` + `tools/mtl_override_extractor.py` — override 注入通道（`cryengine_material`/`ce_material`/`mtl_overrides`）；`docs/car_native_material_overrides.json` 是 car 的現成 override。
5. `output_formats/evidence_coercion.py` — serde 天然取代大半，殘餘做 helper。
6. `output_formats/texture_output_paths.py` 的委派已在 ce-schema，直接用。

## 工作內容

1. **request JSON**：serde struct（`#[serde(deny_unknown_fields)]`），schema 即型別；
   `build_import_request` 等組裝邏輯移植（材質部分直接吃 T-004 政策層輸出）。
   `converter convert <in.fbx> [--manifest m.json] [--overrides o.json] --out-dir DIR` 產出 request JSON。
2. **validate 子命令**：讀 request JSON，跑 schema 驗證（= `rc_import_schema` 的必填/型別/值域檢查），輸出 gate JSON（形狀照現有 schema_gate）。
3. **.mtl writer**：quick-xml；子材質順序 = slot 順序；override 注入通道支援上述三個鍵；貼圖 map 檔名經 ce-schema 後綴表。
4. 測試移植：`test_rc_import_schema*`、`test_rc_request_builder`（純政策部分）、`test_cryengine_shader_flags`、evidence coercion 殘餘。

## Golden 比對（DoD 核心）

1. **request JSON**：`convert` 對 car（帶 manifest）產出的 request 與
   `S:\...\e2e_car_user_flow_phase127_material_overrides\rc_work\kb3d_citycarsessentialssedan-native.json`
   逐鍵相等（白名單：絕對路徑、時間戳、分隔符）。先把該檔複製進
   `fixtures/car/car-reference.request.json`。
2. **MTL**：`convert` 帶 manifest + `car_native_material_overrides.json` 產出的 .mtl 與
   `fixtures/car/car-reference.mtl` 以**正規化 XML 樹**比對（屬性排序、空白不計；
   比對器用 Python 寫進 `tools/`，可比照 compare_json_golden.py 的白名單制）。
3. **schema gate**：`validate` 對產出 request 的 gate JSON 與
   `docs/car_direct_rc_export_mtl_schema_gate.json` 中 request 側欄位一致
   （gate 檔含 MTL/texture 側區塊者，僅比對本票能誠實產生的子樹，
   延續 T-004 裁決的子樹原則）。

## 明確禁止

- 不新增依賴。
- 不做 RC.exe 實跑（C5）。
- 白名單三類原則不變；golden 對不上先歸因，不准湊。
- XML 不做美化排版以外的語意性調整——與 RC/Sandbox 相容性以 reference.mtl 為準。

## DoD

- `cargo test --workspace` 全綠（含新移植測試）。
- 上述三組 golden 通過，指令與輸出貼回報。
- dump/report 對 T-004 基準無 regression。
- 回報：移植/放棄的測試 case 清單、白名單命中列表、任何 XML 形狀上與 reference 的刻意差異。
