# Rust Workspace 設計與任務分派

> 上游文件：`texture-pipeline-spec.md`（texproc 行為規格）、`fbx-converter-migration.md`（遷移計畫）。
> 本文件不重複兩者內容，只補「落地決策」與「可分派的任務包」。
> 決策編號 D-nn 可被引用；標 ⚖ 者為業主保留否決權的現場決策。

---

## 1. 已鎖定的決策

### D-01 Workspace 位置與形狀

```
rebuild/
├── Cargo.toml            # [workspace] members = ce-schema, texproc, converter
├── .cargo/config.toml    # [target.x86_64-pc-windows-msvc] rustflags = ["-C", "target-feature=+crt-static"]
├── ce-schema/            # lib crate
├── texproc/              # bin crate
├── converter/            # bin crate
└── fixtures/             # 測試資產（見 D-12）
```

Edition 2021。靜態 CRT，兩個 exe 零執行期依賴（含 ImageMagick 歸零）。

### D-02 依賴清單（封頂，新增需業主同意）

| crate | 依賴 | 用途 |
|---|---|---|
| ce-schema | `serde`, `serde_json` | schema 型別 + `include_str!` 嵌入 |
| texproc | `image`（png/jpeg/tiff/exr features）, `tiff`（直接用 encoder 以取得 LZW）, `rayon`, `clap`, `serde`, `serde_json` | IO / 平行 / CLI / settings |
| converter | `ufbx`（crates.io 官方 binding，vendored C，build.rs 編譯）, `quick-xml`（writer）, `clap`, `serde`, `serde_json` | FBX 讀取 / .mtl / CLI |

注意：`image` crate 的 TIFF encoder 不暴露壓縮選項，**輸出一律走 `tiff` crate 的 encoder 指定 LZW**；`image` 只負責解碼輸入。

### D-03 像素工作域：encoded f32 + per-op linear islands（業主裁決，定案）

內部表示 = planar f32、值域 0–1、預設保持 sRGB 編碼值。**僅兩個修正點內部做 linear 往返（decode → 運算 → encode）**：

- `DEF-08` 修正：`lerp(gray62, diffuse, metallic)` 在 linear 域計算。常數 rgb(62,62,62) 是 encoded 值，進 island 前同樣要 decode。
- `DEF-09` 修正：`OUT-DIFF` 的 AO Multiply 在 linear 域計算。

其餘所有路徑（resize、alias、invert、copy-opacity、colorize、fallback…）不碰 transfer function。

**錨點 7（新增，機器可檢查）**：「差異範圍 = 缺陷範圍」。直通路徑（不經過任一 DEF 修正的輸入組合）之輸出與舊 Python 版逐像素差 ≤ ±1/255；超出即為未經授權的行為漂移，測試失敗。

### D-04 DEF-09 修正的混合語意

`OUT-DIFF` 的 AO 改用 **Multiply（linear island，見 D-03）**。錨點 2 的人工確認以此為準。

### D-05 ⚖ 量化與 dither

- 量化：`(x * 255).round()` clamp 0–255。
- **資料圖（gloss/normal/height/mask/alpha）永不 dither** —— 錨點 1（ddna.a == 255−roughness 逐像素）必須位元精確。
- 顏色圖 dither 做成 `--dither` 開關，**預設 off**。遷移計畫寫「+ dither」，此處降級為 opt-in；若引擎內目視出現 banding 再翻預設。

### D-06 輸入分組（規格未涵蓋，需從 Python 移植)

- 後綴分類語意移植自 repo 根的 `suffix_settings.json` + `core/` 的分組邏輯（Fox 任務 T0 先定位並摘錄該邏輯，寫進本節再實作）。
- 預設表以 `include_str!` 嵌入，`--suffixes <json>` 可覆蓋，格式與現有 `suffix_settings.json` 相容。
- 注意 `arm` 不在 suffix_settings.json 內，其偵測樣式（arm/orm…）要從 Python 碼裡挖出並記錄。
- DEF-04 修正：`--arm-order` 設定通道排列，預設 `ARM`。

### D-07 Resize

Lanczos3、只縮不放（`>` 語意）、保持長寬比。不追求與 ImageMagick 位元一致（錨點只要求語意一致）。副圖與主圖套用同一目標尺寸。

### D-08 texproc CLI

```
texproc scan    [--suffixes s.json] INPUTS...          # 印出分組結果 JSON（乾跑）
texproc process [--settings cfg.json] [--suffixes s.json] --out DIR INPUTS...
```

settings JSON 鍵名 = 規格 §7 的表，外加 `arm_order`、`sss_contrast`（DEF-12 拆鍵）、`dither`。

### D-09 converter CLI（= 遷移計畫 C4）

```
converter dump     <in.fbx> --out evidence.json        # 讀取層證據
converter convert  <in.fbx> --out-dir DIR [--manifest m.json]   # .mtl + request JSON + 診斷 sidecar
converter validate <request.json>                      # schema gate
```

診斷/gate JSON 形狀與現有 `docs/*.json` 逐鍵相同（遷移計畫 §2.3，golden 契約）。

### D-10 .mtl 序列化

`quick-xml` writer。比對用既有的 Python 正規化 XML 樹腳本，不在 Rust 內重寫比對器。

### D-11 ce-schema 內容

- `docs/converter_schema.json` 凍結一份到 `ce-schema/data/`，`include_str!` + `serde` 解析，`LazyLock` 快取。
- 對外 API：`texture_suffix(key, normal_has_alpha) -> &str`（`_ddna`/`_ddn` 特例）、CE map 型別表、accepted suffixes、genmask/texmod 表查詢。
- Python 端 `tools/converter_schema.py` 保留為 schema 再生成工具；凍結版本不同步時 CI 比對報警（一個 Rust 測試 `include_str! == fs::read(docs/converter_schema.json)` 即可）。

### D-12 ⚖ Fixtures

`rebuild/fixtures/`：car.fbx + 最小重現 FBX + 少量貼圖樣本。**是否進 git（LFS）由業主決定**；未決前 CI golden 比對標記 skip-if-missing。

---

## 2. 留給業主的現場決策

| # | 事項 | 預設立場 |
|---|---|---|
| ~~Q1~~ | ~~像素工作域~~ | 已裁決：per-op linear islands（D-03） |
| Q2 | D-05 dither 預設 off | 依 D-05 執行 |
| Q3 | fixtures 是否進 LFS | 先本機路徑，不進 git |
| Q4 | M0 ufbx 對齊若發現材質順序/id 與 contract 不一致 | 以 ufbx 原始檔案語意為準，差異記入政策層；重大分歧回報業主 |
| Q5 | 錨點 2（DEF-09 修正後 _diff 不等價）的目視驗收 | 業主親自確認 |

---

## 3. 任務包（發派給 Fox）

每包含：讀什麼、做什麼、完成定義（DoD）。順序：M0 →（T 線與 C 線可平行）。
通則：**先讀完引用的規格章節與 Python 原始碼再動手；DoD 是 golden/錨點通過，不是編譯通過。**

### M0 — workspace + ce-schema + ufbx 對齊

**M0a. Workspace 骨架**
- 做：D-01 結構、D-02 依賴、三 crate 空殼可 `cargo build --release`，exe 靜態連結（`dumpbin /dependents` 無 msvcrt 之外依賴）。
- DoD：兩個 exe 在乾淨機器可執行 `--help`。

**M0b. ce-schema**
- 讀：`docs/converter_schema.json`、`output_formats/texture_output_paths.py`、`output_formats/cryengine_mtl_schema.py`、遷移計畫 §2.1 該兩列。
- 做：D-11。單元測試移植自 `test_texture_output_paths`、`test_cryengine_mtl_schema` 的純表格斷言。
- DoD：嵌入 schema 與 `docs/converter_schema.json` 一致性測試通過；suffix 委派鏈測試通過（含 `_em`、`_ddna`/`_ddn` 特例）。

**M0c. ufbx 對齊驗證**（遷移計畫 §4，最大單一風險，先做）
- 做：用 `converter dump` 雛形（或 ufbx example）dump car.fbx：材質名順序、element_id、face_material 分佈、texture filename；與 `blender_material_inspector` 既有輸出比對；產出 `docs/ufbx_alignment_report.json`。
- 重點：id 基底（one-based? element_id vs typed_id）、材質順序、貼圖路徑三來源優先序。
- DoD：報告產出；三個重點各有明確結論。不一致 → 記錄並回報業主（Q4）。

### T 線 — texproc

**T0. 分組邏輯考古**
- 讀：`core/`（batch_processor 的上游）、`suffix_settings.json`。
- 做：把檔名→source type→group 的實際規則（含 arm 偵測、removable_suffixes、stem 提取）寫進本文件 D-06 節。
- DoD：D-06 補完，業主簽核後才進 T1。

**T1. f32 核心 + OP-* 原語**
- 讀：規格 §6、§9 `constants`。
- 做：planar f32 影像型別（D-03）、13 個 OP-* 原語、輸入解碼（8/16-bit + EXR → f32 0–1）、TIFF/LZW 輸出（D-02 注意事項）、量化（D-05）。常數集中一個 module（rgb62 等）。
- DoD：每個 OP-* 有單元測試（含邊界：0、1、clamp）；round-trip 測試 u8→f32→u8 恆等。

**T2. INT-* 管線**
- 讀：規格 §3.1、§4；DEF-03/04/05/06/08 修正方案照規格 §8。
- 做：Stage 1 七條規則，全部在記憶體內（無暫存檔，DEF-02/06 自然消滅）。DEF-08 修正 = 真 lerp(gray62, diffuse, metallic)。DEF-05 修正 = 分支重排使 metallic 路徑可達（順序：albedo 專屬鍵 → diffuse+metallic → diffuse 裸圖）——**注意這是行為變更，實作前跟業主確認分支優先序**。DEF-03 修正 = gloss 先於 reflection 或 reflection 延後讀取。
- DoD：錨點 1 通過（roughness 進 → ddna.a == 255−r 逐像素）；INT-ARM 支援 `--arm-order`；DEF-08 的 linear island 有單元測試（純黑 metallic → 輸出 == gray62；純白 → == diffuse）。

**T3. OUT-* 管線**
- 讀：規格 §5；DEF-09/10/11/12 修正。
- 做：六個 exporter，檔名走 ce-schema（`_em`！），DEF-09 = Multiply（D-04），DEF-12 = 拆 `sss_intensity`/`sss_contrast`。
- DoD：錨點 3–6 通過；錨點 2 產出樣本交業主目視（Q5）；**錨點 7 通過**（直通路徑對舊 Python 版 ±1/255，需舊版可跑以產生對照組——T3 前先確認對照產物已備妥）。

**T4. 編排 + CLI**
- 做：group 掃描（D-06）、rayon 跨 group 平行、D-08 CLI、進度輸出。
- DoD：對照舊 Python 版跑同一批輸入，除 DEF 修正造成的預期差異外輸出檔集合一致（檔名、尺寸、通道數）。

**T5. RC 端到端**
- 做：texproc 產物 → RC.exe → DDS → 引擎內目視。
- DoD：業主目視簽核。

### C 線 — converter

**C1. 讀取層**
- 讀：M0c 報告、遷移計畫 §2.2 對照表。
- 做：ufbx scene → 內部資料模型（材質槽/貼圖引用/polygon 指派/場景樹）；`converter dump` 輸出 evidence JSON。
- DoD：dump car.fbx 與 M0c 報告一致。

**C2. 政策層**
- 讀：`model_processing/rc_material_policy.py`、`material_index_assigner.py`、`material_slot_table.py`、`material_slot_mapping.py` + 對應測試檔。
- 做：遷移計畫 §2.1 前四列；測試移植（§2.4 第一組）。
- DoD：golden 比對 `car_direct_rc_export_material_report.json`、`current_car_user_flow_material_slot_evidence.json`、`phase104_*.json` 逐鍵相等（時間戳/絕對路徑白名單）。

**C3. 序列化**
- 讀：`rc_import_schema.py`、`rc_request_builder.py`、`evidence_coercion.py`。
- 做：serde struct（`deny_unknown_fields`）、request builder（場景樹來自 C1）、.mtl writer（D-10）。
- DoD：golden 比對 schema_gate 系列 + `dev_example/*.mtl` 正規化 XML 樹比對通過。

**C4. CLI 定形**
- 做：D-09 三子命令；Python `test_asset_flow_*` 改接 Rust CLI（subprocess）。
- DoD：asset_flow 端到端測試綠。

**C5. RC 實跑 smoke**
- 做：沿用 `rc_smoke_test` 流程指向 Rust 產物。
- DoD：RC 成功產出 cgf/dds，mtl schema gate 綠。

---

## 4. 審查節點

Fox 每完成一包回報，業主轉交我審查以下重點：

- M0c / C1：id 語意結論是否有證據支撐（不接受「看起來一樣」）。
- T2：DEF-05 分支重排的優先序是否經業主確認。
- T3：linear island 邊界是否精確落在 DEF-08/09 兩點（不多不少），常數 gray62 有無 decode，dither 是否誤套資料圖（D-05）；錨點 7 的直通案例集是否涵蓋每個 OUT-*。
- C2/C3：golden 白名單是否被濫用（只准時間戳與絕對路徑，其他鍵不准進白名單）。
- 全程:新增依賴、新增 config 鍵、任何「順手重構」→ 打回。
