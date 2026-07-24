# T-003 (M0c) — ufbx 資料對齊驗證

狀態：OPEN
上游文件：`fbx-converter-migration.md` §4（本票即該節的執行）、`rust-workspace-design.md` D-12、Q4
風險定位：整個 converter 線的最大單一風險。此票結論直接決定 C1/C2 的政策層寫法。

## 前置

- 業主提供 car.fbx（與必要的小型 FBX）放入 `rebuild/fixtures/`。fixtures 目前不進 git（Q3），路徑存在即可。
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

- `converter dump fixtures/car.fbx --out docs/ufbx_alignment_report.json` 可重跑。
- 三個核心問題各有帶數值證據的結論。
- 與 Blender 側證據的差異全部列舉（零差異也要明說「零差異」）。

## 結論（Fox 填寫）

（待填）
