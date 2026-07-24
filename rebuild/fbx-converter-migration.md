# CryEngine Asset 工具 — Rust 遷移計畫

> 基準：`feat/fbx-material-mapping` @ c87ea511
> 範圍：(a) 貼圖轉換管線、(b) FBX 材質資料 → CryEngine `.mtl` + RC import request JSON
> 明確排除：bpy 全部用途、模型幾何改寫、FBX 重匯出

---

## 1. 目標架構

Cargo workspace，兩個 binary，一個共用 crate：

```
workspace/
├── ce-schema/        共用 crate：CE 貼圖 map 型別、後綴表（source-backed，
│                     含 _em）、converter_schema.json 以 include_str! 嵌入。
│                     後綴命名政策的唯一事實來源，兩個 binary 都吃這裡。
│
├── texproc/          貼圖轉換 binary
│   ├── 影像 IO       image / exr crate；8/16-bit + EXR 輸入
│   ├── 內部表示      planar f32；顏色圖過 sRGB 解碼，資料圖不過
│   ├── 運算核心      OP-* 原語（texture-pipeline-spec.md §6）
│   ├── 管線編排      INT-* / OUT-* 規則，rayon 跨 group 平行
│   └── 輸出          8-bit TIFF/LZW + dither → RC.exe
│
└── converter/        FBX 轉換 binary
    ├── FBX 讀取      ufbx（C，vendored，build.rs 編譯，零執行期依賴）
    ├── 資料模型      材質槽 / 貼圖引用 / polygon 指派 / 場景階層
    ├── 政策層        sub_index 指派、physicalize、hazard 偵測
    ├── 序列化        .mtl (XML) + request JSON（serde）
    └── 診斷          slot mapping contract、evidence sidecar（沿用現有 JSON 形狀）
```

不進 Rust、且**不再存在**的東西：bpy、fbx_exporter、fbx_export_numpy_fix、
`.blend`/DAE/3DS 讀取、ImageMagick 與 Wand 依賴。

不進 Rust、但**以 Python 保留**的東西：
- Sandbox roundtrip 驗證（phase 37–39 那條線）→ 獨立驗證腳本

### 1.1 texproc 的規格來源

`texture-pipeline-spec.md` 是 texproc 的開工文件，本計畫不重複其內容，
但套用前先做三處修訂：
1. `OUT-EMISSIVE` 後綴 `_emissive` → `_em`（phase 111，source-backed）。
2. 規格 §5 的所有輸出檔名決策改為引用 ce-schema（即分支上
   `texture_output_paths.texture_output_suffix()` 的委派鏈），
   `_ddna`/`_ddn` 分支為唯一特例。
3. 規格 §8 的 12 個 DEF 為必修項，不沿用舊行為；驗證錨點見規格 §10
   （注意錨點 2：修正 DEF-09 後 `_diff` 刻意不等價，需人工確認新結果）。

---

## 2. 移植對照表

### 2.1 政策層（核心價值，優先移植）

| Python 來源 | 內容 | Rust 對應 |
|---|---|---|
| `rc_material_policy.py` | `RC_MAX_SUB_MATERIALS=128`、physicalize 正規化（`no/default/obstruct/no_collide/proxy_only`）、名稱推斷 proxy | `enum Physicalize` + `mod rc_policy`，常數與 pattern 表 |
| `material_index_assigner.py` | 指派優先序：explicit → `fbx_id−1` → MTL child order → first free；deleted/dummy 判定；診斷附掛 | `fn assign_sub_indices(&mut [MaterialRecord]) -> Vec<Diagnostic>` |
| `material_slot_table.py` | `<unassigned>` placeholder 三規則、expanded slot table、trailing slot | `mod slot_table` |
| `material_slot_mapping.py` | slot mapping contract 的規則表與狀態機 | `mod slot_contract`，contract 輸出保持同一 JSON 形狀 |
| `cryengine_mtl_schema.py` | CE 貼圖 map 型別、後綴表（source-backed，含 `_em`）、accepted suffixes、texmod、genmask | `mod ce_schema` — **表格資料考慮直接嵌入 `converter_schema.json`（include_str! + serde）而非改寫成程式碼**，保留單一事實來源 |
| `texture_output_paths.py` | 後綴解析委派鏈、`_ddna`/`_ddn` 特例 | `fn texture_suffix(key, normal_alpha) -> &str` |
| `rc_import_schema.py` | request 欄位 schema、必填欄位、animation/joint physics 欄位 | serde struct + `#[serde(deny_unknown_fields)]`，schema 即型別 |
| `rc_request_builder.py` | node 階層處理、material requests、import request 組裝 | `mod request_builder`（bpy 相關的 `extract_blender_scene_hierarchy` 不移植，改由 ufbx 場景樹供給） |
| `evidence_coercion.py` | 證據欄位型別強制 | serde 天然取代大半，殘餘部分做 helper |

### 2.2 讀取層（用 ufbx 重寫，不是移植）

| 被取代的 Python | ufbx 對應能力 |
|---|---|
| `model_loader.py`（bpy import） | `ufbx_load_file` → scene |
| `material_index_assigner.get_fbx_material_id` | `ufbx_material.element.element_id`（原始值，不經 Blender 轉譯） |
| `material_slot_usage.py`（polygon 指派） | `ufbx_mesh.face_material[]` |
| `material_texture_resolver.py` + `texture_extractor.py` | `ufbx_material.textures[]`、`ufbx_texture.filename / absolute_filename / content`（embedded） |
| `blender_material_inspector.py` | 不再需要 —— 它存在的目的就是穿過 Blender importer 的語意轉換看原始資料，ufbx 直接給原始資料 |
| `rc_request_builder.extract_scene_hierarchy_from_model` | `ufbx_scene.root_node` 遞迴 |

### 2.3 診斷與 gate

`material_diagnostics_exporter`、`texture_output_diagnostics`、slot mapping contract
的 **JSON 輸出形狀維持不變** —— 這是刻意的：現有 `docs/*.json` 才能繼續當
golden fixture，`tools/` 裡的 Python 比對腳本才能不改直接用。

### 2.4 測試分流（39 檔）

**邏輯直接轉成 Rust 單元測試**（純政策，無 bpy/UI 依賴）：
```
test_material_index_assigner   test_material_slot_mapping
test_material_slot_table       test_rc_request_builder
test_rc_import_schema 相關     test_cryengine_mtl_schema
test_cryengine_shader_flags    test_texture_output_paths
test_texture_type_resolver     test_evidence_coercion
test_material_manifest         test_rc_export_gate（gate 邏輯部分）
```

**保留為 Python 端到端驗證**（跑 Rust 執行檔、比對輸出）：
```
test_asset_flow_* 系列 → 改為 subprocess 呼叫 Rust CLI
test_material_editor_roundtrip → Sandbox 驗證腳本
```

**隨 bpy 陪葬**：
```
test_blender_material_fixture   test_blender_material_inspector
test_fbx_exporter               test_material_converter（bpy 部分）
test_model_loader_material_usage（改由 ufbx 讀取層的新測試取代）
test_pyside_*
```

---

## 3. Golden fixtures

驗收標準：Rust 版對同一輸入產出的 JSON 與下列既有證據檔**逐鍵相等**
（時間戳、絕對路徑類欄位除外，列入比對白名單）：

```
docs/car_direct_rc_export_material_report.json
docs/car_direct_rc_export_mtl_schema_gate.json
docs/current_car_user_flow_material_slot_evidence.json
docs/phase104_car_trailing_unassigned_material_report.json
docs/phase110_dev_example_mtl_schema_report.json
docs/phase123_car_roughness_opacity_mtl_schema_report.json
docs/phase125_roughness_alpha_split_mtl_schema_report.json
docs/phase126_heightmap_shader_feature_split_mtl_schema_report.json
```

MTL 輸出比對基準：`dev_example/*.mtl` 與 car 流程產出的 MTL，
以 **正規化後的 XML 樹**比對（屬性排序、空白不計），不做位元比對。

⚠ repo 內沒有 FBX 測試資產（car 資產在本機）。第一步是把 car.fbx 與
最小重現用的小型 FBX 收進一個 `fixtures/` 目錄（或私有 LFS），
否則 golden 比對無法進 CI。

---

## 4. 前置驗證：ufbx 資料對齊（在寫任何轉換邏輯之前）

目的：確認 ufbx 讀出的原始值與 126 個 phase 逆向出的語意一致。

步驟（半天內可完成）：

1. 以 ufbx 官方 example（或 Python binding `ufbx`）dump car.fbx：
   材質名清單（含順序）、每材質 element_id、每 mesh 的
   `face_material` 分佈統計、每材質的 texture filename 列表。
2. 與 `blender_material_inspector` 對同一檔案的既有輸出比對。
3. 重點核對三件事：
   - **材質 id 的基底**：contract 記載 FBX id 為 one-based、
     raw slot = `fbx_material_id − 1`。確認 ufbx 的 element_id 或
     typed_id 哪一個對應此語意。
   - **材質順序**：Blender importer 可能重排；ufbx 保持檔案順序。
     若兩者不同，以 ufbx（原始檔案）為準，並記錄差異 —— 這可能
     解釋過去某些 phase 的順序異常。
   - **貼圖路徑**：relative / absolute / embedded 三種來源的
     優先序是否與 `material_texture_resolver` 的政策相容。
4. 產出一份 `docs/ufbx_alignment_report.json`，格式比照既有 evidence。

任一不一致都不是阻擋 —— 是需要記進政策層的新事實。

---

## 5. 里程碑

```
M0  workspace 建立 + ce-schema crate（converter_schema.json 嵌入）
    ＋ ufbx 對齊驗證（§4）＋ fixtures/ 目錄建立

converter 線：
C1  讀取層：FBX → 內部資料模型，dump 指令可輸出 evidence JSON
C2  政策層：sub_index 指派 + physicalize + hazard 診斷
    → golden 比對 material_report / slot_evidence 通過
C3  序列化：request JSON + .mtl
    → golden 比對 schema_gate / MTL 樹比對通過
C4  CLI 定形（dump / convert / validate 三個子命令）
    → Python 端 asset_flow 測試改接 Rust CLI
C5  RC 實跑 smoke（沿用 rc_smoke_test 的流程，指向 Rust 產物）

texproc 線（可與 converter 平行推進，共同依賴僅 M0 的 ce-schema）：
T1  影像 IO + planar f32 核心 + OP-* 原語（含單元測試）
T2  INT-* 管線 + DEF-03/04/05/06/08 修正
    → 錨點 1（ddna alpha = 255−roughness 逐像素）通過
T3  OUT-* 管線 + DEF-09/10/11/12 修正 + ce-schema 檔名
    → 規格 §10 錨點 3–6 通過；錨點 2 人工確認
T4  rayon 平行化 + CLI 定形，對照舊版跑 batch 比對報告
T5  RC.exe 端到端：texproc 產物 → DDS → 引擎內目視驗收
```

每個里程碑的完成定義都是「對應 golden fixture 通過」，
不是「程式碼寫完」。

---

## 6. 風險與已知未定事項

| 項目 | 狀態 |
|---|---|
| ufbx 材質 id 語意與 contract 是否一致 | **M0 驗證，最大單一風險** |
| `.blend`/DAE/3DS 支援消失 | 已接受（RC 只吃 FBX） |
| material_manifest（fixture 注入機制）是否還需要 | 傾向保留：它是不依賴 Blender 的測試注入口，正好適合新架構 |
| Sandbox roundtrip | Python 腳本保留，不進 Rust |
| GUI | 不在本計畫。CLI 穩定後再議 egui |
| 貼圖像素管線的 12 個 DEF | texproc 必修項（§1.1），驗證錨點在規格 §10 |
| texproc 的 golden 比對基準 | 舊 Python 版輸出**不可**直接當 golden（DEF-08/09 修正後刻意不等價）；改以規格 §10 錨點 + 引擎內目視驗收為準 |
```
