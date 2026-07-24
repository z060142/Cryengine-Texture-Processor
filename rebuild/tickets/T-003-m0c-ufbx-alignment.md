# T-003 (M0c) — ufbx 資料對齊驗證

狀態：DONE（2026-07-25 審查通過。獨立重跑驗證：16 材質 typed_id 0..15 / element_id 45..60、71 貼圖引用 0 embedded、21 mesh / 111,972 faces / 68 local slots 全部吻合；ufbx 序 vs slot evidence 16/16 + slot 16 placeholder、vs reference mtl_slots 名單序一致均驗實。兩項備註：(1) dump 的 filename 欄位分隔符繼承 CLI 引數，同輸入不同寫法會產生無害 diff——golden 比對時列白名單；(2) Blender first-seen 表出處未獨立驗證，不承重（Q4 已裁定採 ufbx 序）。審查裁定：C1 的讀取層 DoD 已由本票 dump 實質達成，C1 不另開票，內部資料模型併入 C2 塑形）
上游文件：`fbx-converter-migration.md` §4（本票即該節的執行）、`rust-workspace-design.md` D-12、Q4
風險定位：整個 converter 線的最大單一風險。此票結論直接決定 C1/C2 的政策層寫法。

## 前置

- 素材已備妥（見 `fixtures/README.md`）：`fixtures/car/car.fbx`、小型 FBX `fixtures/KB3D_ENC_PropAxe_A_grp.fbx`。
- 額外比對材料：`fixtures/car/car-reference.material_report.json` 是既有工具鏈對同一資產的 material report，與 docs/ 證據並列比對。
- 讀 `docs/converter_contract.md` 中材質 id 基底的記載（one-based、raw slot = fbx_material_id − 1）。
- 讀既有 Blender 側證據：`docs/phase98_car_example_material_alignment.json`、`docs/current_car_user_flow_material_slot_evidence.json`（作為比對對象）。
- 讀 `model_processing/material_texture_resolver.py` 的貼圖路徑優先序政策（relative/absolute/embedded）。

## 工作內容

1. 在 `converter` 實作最小版 `dump` 子命令：`converter dump <in.fbx> --out report.json`。
   只讀不轉，輸出：
   - 材質清單（**檔案順序**）：name、element_id、typed_id。
   - 每個 mesh：name、材質槽列表、`face_material` 分佈統計（每槽 face 數）。
   - 每材質的 texture 引用：filename、absolute_filename、是否 embedded（content 非空）。
   - 場景樹：node 名稱階層（縮排或巢狀 JSON 均可）。
2. 對 car.fbx 跑 dump，與上述 Blender 側證據比對，逐項回答遷移計畫 §4 的三個核心問題：
   - **id 基底**：ufbx 的 element_id 還是 typed_id 對應 contract 的「fbx_material_id（one-based）」？拿實際數值對照，不接受推論。
   - **材質順序**：ufbx 檔案順序 vs Blender 匯入順序是否一致？不一致則列出兩邊順序全表。
   - **貼圖路徑**：三種來源在 car.fbx 上的實際樣貌，與 `material_texture_resolver` 政策是否相容。
3. 產出 `docs/ufbx_alignment_report.json`，形狀比照既有 evidence 檔（頂層含 schema 名與 generated_by）。
4. 結論寫進本票的「結論」節：三個問題各一段，附數值證據。

## 明確禁止

- 不寫任何政策層/轉換邏輯，dump 就是 dump。
- 不對不一致「自行修正」——不一致是資料，記錄後回報（Q4：以 ufbx 原始語意為準，重大分歧交業主裁決）。
- dump 的 JSON 形狀此階段不必符合最終 evidence 契約，夠比對即可。

## DoD

- `converter dump fixtures/car/car.fbx --out docs/ufbx_alignment_report.json` 可重跑（docs/ 指 repo 根的 docs）。
- 小型 FBX 也 dump 一次確認 reader 不是只對 car 特化（結果不必比對，跑得過即可）。
- 三個核心問題各有帶數值證據的結論。
- 與 Blender 側證據的差異全部列舉（零差異也要明說「零差異」）。

## 結論（Fox 填寫）

### 1. id 基底

car.fbx 的 16 個 ufbx 材質依檔案序讀得 `typed_id = 0..15`、`element_id = 45..60`。
既有 contract 的 one-based `fbx_material_id = 1..16` 對應關係是
`fbx_material_id = typed_id + 1`，也就是 raw slot 直接等於 `typed_id`；
`element_id` 是跨 element 類型的場景全域 id，不對應材質槽。

數值與順序全表如下（`current slot` 取自
`current_car_user_flow_material_slot_evidence.json`；16/16 都等於 ufbx index）：

| ufbx index / typed_id | element_id | fbx_material_id | ufbx 檔案序材質 | Blender first-seen index |
|---:|---:|---:|---|---:|
| 0 | 45 | 1 | KB3D_CEV_UndercarriageTrim | 0 |
| 1 | 46 | 2 | KB3D_CEV_SeatsDriverATrim | 1 |
| 2 | 47 | 3 | KB3D_CEV_TiresSedans | 14 |
| 3 | 48 | 4 | KB3D_CEV_WheelRimsA | 15 |
| 4 | 49 | 5 | KB3D_CEV_RubberTrim | 2 |
| 5 | 50 | 6 | KB3D_CEV_PlasticTileableA | 3 |
| 6 | 51 | 7 | KB3D_CEV_PlasticTrimA | 4 |
| 7 | 52 | 8 | KB3D_CEV_SedanExteriorBody | 5 |
| 8 | 53 | 9 | KB3D_CEV_CarAtlas | 6 |
| 9 | 54 | 10 | KB3D_CEV_CarsLicensePlates | 7 |
| 10 | 55 | 11 | KB3D_CEV_TapesTrimA | 8 |
| 11 | 56 | 12 | KB3D_CEV_WindowFritsTrim | 9 |
| 12 | 57 | 13 | KB3D_CEV_FeltA | 10 |
| 13 | 58 | 14 | KB3D_CEV_FeltB | 11 |
| 14 | 59 | 15 | KB3D_CEV_GlassMirror | 12 |
| 15 | 60 | 16 | KB3D_CEV_TranslElemSedans | 13 |

另外，ufbx dump 的 21 meshes、111,972 faces、68 個 mesh-local material slots
與 `phase98_car_example_material_alignment.json` 的 Blender/CGF 證據數量一致；
每個 mesh 的 local slot 及 `face_material` face 數已逐列保存在報告。

### 2. 材質順序

ufbx 檔案序與目前 RC/MTL slot evidence **16/16 一致，零差異**；
`car-reference.material_report.json` 的 request/MTL 前 16 槽也 **16/16 一致，
零差異**（reference 另有 slot 16 `<unassigned>`，ufbx 原始 FBX 材質表沒有此
RC placeholder）。ufbx 與 Blender first-seen 序則只有 index 0、1 一致，
index 2..15 共 14 個位置不同，但材質集合 16/16 相同，沒有新增或遺失。
完整兩邊順序如下，這也是全部順序差異：

| index | ufbx 檔案序 | Blender first-seen 序 |
|---:|---|---|
| 0 | KB3D_CEV_UndercarriageTrim | KB3D_CEV_UndercarriageTrim |
| 1 | KB3D_CEV_SeatsDriverATrim | KB3D_CEV_SeatsDriverATrim |
| 2 | KB3D_CEV_TiresSedans | KB3D_CEV_RubberTrim |
| 3 | KB3D_CEV_WheelRimsA | KB3D_CEV_PlasticTileableA |
| 4 | KB3D_CEV_RubberTrim | KB3D_CEV_PlasticTrimA |
| 5 | KB3D_CEV_PlasticTileableA | KB3D_CEV_SedanExteriorBody |
| 6 | KB3D_CEV_PlasticTrimA | KB3D_CEV_CarAtlas |
| 7 | KB3D_CEV_SedanExteriorBody | KB3D_CEV_CarsLicensePlates |
| 8 | KB3D_CEV_CarAtlas | KB3D_CEV_TapesTrimA |
| 9 | KB3D_CEV_CarsLicensePlates | KB3D_CEV_WindowFritsTrim |
| 10 | KB3D_CEV_TapesTrimA | KB3D_CEV_FeltA |
| 11 | KB3D_CEV_WindowFritsTrim | KB3D_CEV_FeltB |
| 12 | KB3D_CEV_FeltA | KB3D_CEV_GlassMirror |
| 13 | KB3D_CEV_FeltB | KB3D_CEV_TranslElemSedans |
| 14 | KB3D_CEV_GlassMirror | KB3D_CEV_TiresSedans |
| 15 | KB3D_CEV_TranslElemSedans | KB3D_CEV_WheelRimsA |

依 Q4，後續政策層應採 ufbx 檔案序 / `typed_id` 原始語意，不採 Blender
first-seen 序。

### 3. 貼圖路徑

car.fbx 共讀得 71 筆材質貼圖引用：71/71 有 `filename`、
`relative_filename`、`absolute_filename`，0/71 embedded。典型一筆為：

- relative：`KB3DTextures\4k\KB3D_CEV_UndercarriageTrim_basecolor.png`
- ufbx resolved filename：`fixtures/car\KB3DTextures\4k\KB3D_CEV_UndercarriageTrim_basecolor.png`
- absolute（FBX 內保存的舊來源）：`D:\EkkoRunner\...\KB3D_CEV_UndercarriageTrim_basecolor.png`
- embedded：`false`、content size 0

目前 fixture 不含 car 貼圖，故 71/71 的 resolved/relative/absolute 路徑在本機都
不存在。既有 `material_texture_resolver.resolve_base_name()` 接受單一 ref path，
先對「存在的路徑」做分類，否則取第一筆 ref 的 basename 並移除已知 suffix；
car 的三個字串 basename 相同，所以此 fallback 與 ufbx 資料相容。

但既有 resolver 並未定義 ufbx 三來源間的 relative → absolute → embedded
優先序，而 car 也沒有 embedded content，故 embedded 提取與「relative、absolute
同時存在時選哪個」均是本素材未覆蓋項，不宣稱已驗證。此差距不阻擋 M0c，
但 C1 建立 texture reference 內部模型時必須保留三個原始欄位，C2 再依 Q4
把可重現的優先序寫成明確政策。
