# T-007 (C5) — RC.exe 實跑 smoke

狀態：DONE（2026-07-25 審查通過：run_gates 含 RC 段獨立實跑全綠；審查者另以 --texture-dir 指向 example/car 真實 DDS 補跑 smoke，MTL 82 貼圖標籤、schema gate texture_maps 與舊 car_rc_smoke gate 逐項一致——票面「texture 計數為空」的差異純因未帶 texture-dir，非能力缺口。converter 線 C1–C5 至此完工）
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

## 執行結果（2026-07-25）

### 實作

- 新增 stdlib-only `tools/rc_smoke_rust.py`：
  1. 複製 FBX 到 `<work-dir>/rc_work/`。
  2. subprocess 呼叫凍結的 Rust `converter convert`，產生 request + MTL。
  3. 呼叫 RC.exe，固定使用 `/overwriteextension=fbx`、
     `/overwritesourcefile=<copied fbx>` 與 `/overwritefilename=<request stem>.cgf`。
  4. 檢查 RC return code 與 CGF 存在性，再以 `cgf_material_reader`
     讀取 material IDs、名稱序與 physicalize types。
  5. 以現有 `mtl_schema_report` 驗證 Rust MTL，並輸出 compact、只含本票
     能誠實讀回區塊的 smoke report。
- RC 路徑只接受 `--rc` 或 `CE_RC_EXE`；converter 接受 `--converter` 或
  `CE_CONVERTER_EXE`，後者未設定時使用
  `rebuild/target/release/converter.exe`。
- 新增 3 個 policy tests：trailing placeholder 正常省略、錯誤出現在 CGF
  時拒絕，以及 RC import command 形狀。
- `run_gates.ps1` 新增 optional RC smoke：
  `CE_RC_EXE` 優先，其次票面預設 RC；兩者皆不存在時印 SKIP。
  `-SkipRC` 可明確模擬無 RC/CI 路徑。

沒有修改 Rust CLI、沒有碰 texproc/DDS 內容，也沒有新增依賴。

### 真實 RC 指令

```powershell
$smokeRoot = Join-Path $env:TEMP 't007-rust-rc-smoke-car'

uv run python tools\rc_smoke_rust.py `
  --rc 'S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe' `
  --converter rebuild\target\release\converter.exe `
  --fbx rebuild\fixtures\car\car.fbx `
  --manifest rebuild\fixtures\car\car.fbx_material_manifest.json `
  --overrides docs\car_native_material_overrides.json `
  --work-dir $smokeRoot `
  --output docs\rust_rc_smoke_car.json
```

結果：

```text
ok: True
rc_returncode: 0
cgf_exists: True
material_alignment: 16/16
placeholder_ok: True
mtl_schema_gate_ok: True
```

正式報告：`docs/rust_rc_smoke_car.json`。報告記錄的 CGF 大小為
11,487,970 bytes；本次實跑 SHA-256 為
`2F85AAC2E0283A8A9D45198AA080DDDD445D4794E1417B995B4F47796366B5A2`。

### CGF 材質與 placeholder 裁決

- manifest `expect_cgf_material_ids`：`0..15`。
- CGF reader 實讀 material IDs：`0..15`，完全相等。
- manifest slot 0–15 名稱與 CGF MtlName sub-material table：
  **16/16 同 slot、同序、同名**。
- 16 個 CGF physicalize types 均為 `-1`，對應 manifest 的 `no`。
- request 與 MTL 都含 `<unassigned>`，slot 為 16。
- manifest 沒有把 slot 16 列進 `expect_cgf_material_ids`；RC 產生的 CGF
  也沒有 `<unassigned>`。因此分類為
  `trailing_unassigned_not_expected_in_cgf`，不是遺失材質，判定 `ok=true`。

### 舊 MTL schema gate 差異

比較基準：`docs/car_rc_smoke_mtl_schema_gate.json`。

- `/gate` **完整相等**：`ok=true`、0 diagnostics、0 errors、0 warnings。
- `/summary` 的既有四欄完全相等：
  `file_count=1`、`material_count=18`、
  `multi_material_file_count=1`、`tokenized_material_count=16`。
- 新報告多一個目前 analyzer 才有的
  `compatibility_preserved_default_count=19`。
- schema 共 13 個 key 不同，完整列舉如下：
  - 新 analyzer provenance，舊報告沒有：
    `material_attribute_compatibility_defaults`、
    `material_attribute_override_backed_values`、
    `material_attribute_policy_sources`、
    `public_param_compatibility_defaults`、
    `public_param_override_backed_values`、
    `texmod_compatibility_statuses`（空）。
  - 本次 smoke 刻意未提供 `--texture-dir`，Rust MTL 因此只序列化實際存在的
    processed outputs（本次為零）；下列舊報告的 65 筆貼圖/TexMod 統計在新報告
    為空：`texmod_attributes`、`texmod_statuses`、
    `texture_expected_suffixes`、`texture_map_policy_reasons`、
    `texture_maps`、`texture_maps_by_shader`、`texture_suffix_statuses`。

上述 texture counter 差異不影響本票 gate，且符合「不比對 DDS/貼圖內容」與
T-005 的 actual-processed-file-only 規則；沒有用假檔案湊舊計數。

### 統一 gate 雙路驗證

有 RC：

```powershell
cd rebuild
.\run_gates.ps1
```

結果：既有 Rust 48/48、asset_flow 28 passed / 2 skipped、RC policy 3/3、
T-003/T-004/T-005 goldens 全綠；optional RC smoke 為 return code 0、
CGF true、16/16、placeholder true、schema gate true，最後
`ALL GATES PASSED`。

無 RC／CI 模式（本機以 switch 明確模擬）：

```powershell
.\run_gates.ps1 -SkipRC
```

結果：印出 `Optional RC smoke: SKIP (-SkipRC)`；其餘相同 gates 全綠，
最後仍為 `ALL GATES PASSED`。若未指定 switch 且
`CE_RC_EXE`/預設路徑都不存在，也走相同 SKIP 分支。
