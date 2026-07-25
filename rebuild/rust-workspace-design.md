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

### D-06 輸入分組（T0 Python 實際行為考古）

本節凍結的是 2026-07-25 的 Python **實際行為**，不是理想設計。現行主程式是
PySide6 入口（`main.py:4-7,31,70-83`）；檔案選取與模型抽出的貼圖最後都進
`TextureImportPanel.import_textures()`，再逐檔呼叫 `TextureManager.add_texture()`
（`ui_pyside/texture_import.py:89-123`、`ui_pyside/model_import.py:668-669,921-933`）。
真正有權威性的分組實作只有 `core/name_parser.py` +
`core/texture_manager.py`；`utils/` 沒有另一套分組器。

舊 Tkinter 的 `TextureImportPanel.classify_textures()` / `group_textures()`
（`ui/texture_import.py:377-503`）在 repo 內沒有呼叫者，且演算法不同，**不得移植**。

#### D-06.1 設定載入與後綴匹配

1. `TextureManager` 建立時先建 `TextureNameParser`，再固定讀 repo 根
   `suffix_settings.json` 並呼叫 `load_patterns()`；檔案不存在或解析失敗才保留
   parser 的內建預設（`core/texture_manager.py:149-189`）。
2. JSON 的每個一般 suffix 先 `strip()`、`re.escape()`，再編成
   `_{suffix}(?:_?\d+k)?$`；全部 regex 使用 `re.IGNORECASE`
   （`core/name_parser.py:130-137,139-180`）。因此：
   - 不是把整個檔名按 `_` token 化後查表，而是要求「一個自動補上的 `_` +
     suffix」位於 stem 結尾；suffix 後只准選配解析度 `4k` / `_4k`
     （實際上 `\d+k` 接受任意位數）。
   - 大小寫不影響**型別匹配**；`Normal` 與 `normal` 重複但語意相同。
   - 設定值若自己帶 `_`，底線會被 escape、外面再補一個 `_`。所以根設定的
     `_n/_s/_g/_r/_h/_m/_e` 實際要求 `__n/__s/...`，普通 `foo_n` 不會命中
     這一層（`suffix_settings.json:12-76`）。
   - 根設定的 `a`、`d` 不是任意子字串，而是結尾 `_a`、`_d`；兩者都屬
     `diffuse`，且 `alpha` 沒有單字母 `a`（`suffix_settings.json:2-10,62-66`）。
3. JSON regex 前另有一層不可覆蓋的 CryEngine 表：
   `_diff/_ddna/_displ/_spec/_em/_emissive/_sss`，依
   diffuse → normal → displacement → specular → emissive → sss 順序先查
   （`core/name_parser.py:220-249`）。
4. 一命中就立即 return。優先序是：
   **硬編碼 CE 表順序 → JSON key 的檔案插入順序 → 該 key 內 suffix 陣列順序**。
   所有 regex 都錨定結尾，所以 `wall_normal_diff` 只會以最後的 `_diff`
   判 diffuse；若自訂 JSON 把同一 terminal suffix 配給多型別，先出現的 key
   勝出（`core/name_parser.py:230-249`）。
5. 前兩層都沒命中才開影像做 `TextureAnalyzer` fallback；analyzer 先以不具
   token 邊界的子字串表判斷，再看像素統計。confidence ≥ 0.5 才採用，否則
   `unknown`（`core/name_parser.py:251-263`、
   `core/texture_analyzer.py:29-79,81-126,182-241`）。所以 fallback 結果會受
   檔案是否能解碼、像素內容與 Pillow build 影響，不是純檔名函式。

#### D-06.2 stem 清理、base name 與 group

1. `os.path.splitext(os.path.basename(path))[0]` 只去最後一段副檔名；沒有副檔名
   白名單或存在性檢查（`core/name_parser.py:204-218`）。
2. 分類前 `_clean_filename()` 只按 `_` 切段，將與
   `removable_suffixes` **完全相等且不分大小寫**的段全部移除，再用 `_` 接回；
   位置不限結尾、`-dx` 不算 token（`core/name_parser.py:182-202`）。
   active 根設定只列 `dx/gl`（`suffix_settings.json:77-80`），因此 parser
   建構時的 `2k/4k/8k/directx/opengl` 預設會被覆寫掉
   （`core/name_parser.py:23-26,152-155`）。
3. regex 命中後先切掉整個「型別 suffix + 其後解析度」，再跑
   `_extract_base_name()`。後者若仍找不到 terminal pattern，會按 `_` 切段，
   移除**任何位置**與該型別 identifier 相等的段，不只末段
   （`core/name_parser.py:233-249,265-328`）。
4. group key 就是原樣保留大小寫的 `base_name`；用 Python 字串 `==` 查找，
   沒有 `casefold()` 或路徑/資料夾 namespace
   （`core/texture_manager.py:229-269`）。因此 `Wall` 與 `wall` 是兩組；
   不同資料夾但同 base name 會合為一組。
5. 去重只比較 `os.path.abspath()` 的字串 set，沒有 Windows case 正規化
   （`core/texture_manager.py:153-155,205-220,246-247`）。
6. 一組內已知型別各只有一格；同 stem、同型別再次加入時直接覆蓋舊值，
   所以不同副檔名或 `_2k/_4k` 合併後由**輸入順序最後一張**勝出，沒有解析度、
   尺寸、mtime 或格式優先序。只有 `unknown` 是 append list
   （`core/texture_manager.py:31-46,75-87`）。

#### D-06.3 ARM

`arm` 不在根 JSON；`load_patterns()` 每次在缺少 `arm` key 時硬加
（`core/name_parser.py:169-177`）。實際 regex 接受：

| terminal spelling | 是否命中 `arm` | 來源 |
|---|---:|---|
| `_arm` | 是 | `_arm` / `_a?rm` |
| `_rm` | 是 | `_a?rm` |
| `_ra` | 是 | `_rm?a` |
| `_rma` | 是 | `_rm?a` |
| `_occlusion-roughness-metallic`、底線變體 | 是 | 長名 regex |
| `_ao-rough-metal`、底線變體 | 是 | 短長名 regex |
| `_orm` | **否** | 無對應 regex |

來源：`core/name_parser.py:117-124,169-177`。`TextureAnalyzer` fallback 也只認
子字串 `_arm`（`core/texture_analyzer.py:120-125`），所以 ORM 沒有固定的
檔名語意，會落到像素猜測。`--arm-order` 仍按 DEF-04 設定通道排列，預設
`ARM`；檔名 alias 本身不攜帶 channel-order metadata。

#### D-06.4 unknown 的去向

- 未知檔仍建立/加入其 base-name group，放進 `textures["unknown"]` list
  （`core/texture_manager.py:31-46,75-87,239-244`）。
- PySide group panel顯示 unknown 數量與檔名，允許人工指定型別；指定時從 list
  移出並直接寫入該型別單格（已有同型別會被覆蓋）
  （`ui_pyside/texture_group_panel.py:83-105,116-131,154-170`）。
- batch 不拒絕含 unknown 或 unknown-only 的 group；所有 group 都走兩階段，
  但中間層只查已知型別，沒有任何 processor 讀 `unknown`
  （`core/batch_processor.py:143-193,251-386`）。結果通常是該 unknown 不產出
  任何貼圖，也沒有「尚未分類」的 hard gate。

#### D-06.5 輸入格式的實際入口

PySide file dialog 顯示
`jpg/jpeg/png/tga/tif/tiff/bmp/hdr/exr`，同時提供 `All files (*.*)`
（`ui_pyside/texture_import.py:89-101`）。迴圈不再檢查 extension、bit depth、
檔案存在或可解碼，直接呼叫 manager（`ui_pyside/texture_import.py:103-123`）；
manager/name parser 也不做這些 admission checks。因此這不是白名單：

- 上述九種格式會出現在 picker filter，但任意 extension 的 programmatic path
  或經 All files 選入的檔都能進 group。
- 16-bit TIFF 與 EXR **確實能進分組層**。T0 以 ImageMagick 建立兩張 2×2、
  depth=16 的 `probe_normal.tif/.exr` 實跑，兩者皆得到
  `type=normal, base_name=probe`。
- 這不保證後續 processor 能解碼；檔名在前兩層命中時根本不會開檔，未命中時
  才由 Pillow analyzer 嘗試解碼，失敗仍以 `unknown` 加入。T1 必須另行凍結
  真正 decoder whitelist，不能把 file-dialog filter 當契約。

#### D-06.6 可複核判例

前五列取自 `Z:\enchanted\KB3DTextures\4k` 的真實檔名；其餘用同一張可解碼
PNG 複製改名後直接呼叫 active `TextureNameParser` / `TextureManager`。DEF-07
三個名稱在 source-type 分組都判 normal；DEF-07 的錯誤發生在其後的
normal DX/GL 判定，不應混成分組缺陷。

| # | 輸入檔名 | 實際 source type | 實際 base name | 判定重點 |
|---:|---|---|---|---|
| 1 | `KB3D_ENC_AtlasA_basecolor.png` | diffuse | `KB3D_ENC_AtlasA` | JSON terminal suffix |
| 2 | `KB3D_ENC_AtlasFruitsB_emissive.png` | emissive | `KB3D_ENC_AtlasFruitsB` | CE `_emissive` 先命中 |
| 3 | `KB3D_ENC_AtlasA_opacity.png` | alpha | `KB3D_ENC_AtlasA` | JSON terminal suffix |
| 4 | `KB3D_ENC_AtlasA_normal.png` | normal | `KB3D_ENC_AtlasA` | JSON terminal suffix |
| 5 | `KB3D_ENC_AtlasA_ao.png` | ao | `KB3D_ENC_AtlasA` | JSON terminal suffix |
| 6 | `glass_normal.png` | normal | `glass` | DEF-07 名；分組本身正常 |
| 7 | `single_nrm.png` | normal | `single` | DEF-07 名；分組本身正常 |
| 8 | `shingle_n.png` | normal | `shingle` | DEF-07 名；`_n` 設定失效後由 analyzer 子字串 fallback |
| 9 | `plaza_a.png` | diffuse | `plaza` | `a` 屬 diffuse，不是 alpha |
| 10 | `facade_d.png` | diffuse | `facade` | 單字母 `d` |
| 11 | `packed_arm.png` | arm | `packed` | hardcoded ARM |
| 12 | `packed_rm.png` | arm | `packed` | `_a?rm` 也接受 `rm` |
| 13 | `packed_rma.png` | arm | `packed` | `_rm?a` |
| 14 | `packed_orm.png` | diffuse（本次像素） | `packed_orm` | 無 ORM pattern；落到像素 fallback，結果不穩定 |
| 15 | `stone_normal_dx.png` | normal | `stone` | 先移除任意位置的 `dx` token |
| 16 | `stone_gl_normal.png` | normal | `stone` | 先移除任意位置的 `gl` token |
| 17 | `stone_normal_4k.png` | normal | `stone` | type 後解析度併入 regex 一起切除 |
| 18 | `stone_4k_normal.png` | normal | `stone_4k` | type 前 `4k` 不再是 removable |
| 19 | `Wall_normal.png` + `wall_roughness.png` | normal + roughness | `Wall` + `wall` | 大小寫分成兩組 |
| 20 | `same_normal.tif` 後加入 `same_normal.exr` | normal | `same` | 同格合併，EXR 靜默覆蓋 TIFF |
| 21 | `normal_wall_normal.png` | normal | `wall` | base extractor 連 stem 內部 `normal` token 也移除 |

判例 1–18 的分類/取 stem 規則來源為
`core/name_parser.py:182-263,265-328`；19–20 的合併結果來源為
`core/texture_manager.py:75-87,216-269`。

#### D-06.7 新發現缺陷與建議裁決（⚖ 均待業主簽核）

建議只代表 T1/T4 的預設提案；未簽核前不得把「建議修」視為已授權行為變更。

| 缺陷 | 實際問題 | Fox 建議 |
|---|---|---|
| `DEF-13` | 設定值自帶 `_` 被編成雙底線，根表七組短 suffix 失效。 | **修**：載入時正規化成恰好一個 separator，並測 `_n/_s/_g/_r/_h/_m/_e`。 |
| `DEF-14` | `_a` 被 diffuse 先吃掉；`a/d` 單字母語意高度含糊。 | **修**：預設移除單字母 alias；若要保留，要求自訂表明確 opt-in。 |
| `DEF-15` | `dx/gl` 按 `_` token 在任意位置全刪，可能破壞合法 stem；active 表又意外丟掉 2k/4k/8k defaults。 | **修**：只從 terminal qualifier 區逐段 peel，解析度位置語法明文化。 |
| `DEF-16` | ARM 接受含糊的 `rm/ra`，接受 `rma` 卻不接受常見 `orm`，且 alias 不表達 channel order。 | **修**：只留明確 token，至少定義 `arm/orm/rma` 到 channel order 的對照；歧義 alias 報 diagnostic。 |
| `DEF-17` | regex 未命中後改以 Pillow/像素猜型別，結果依內容與 decoder 環境而變；ORM 可被猜成 diffuse。 | **修**：`scan` 保持 filename-only deterministic；不明者列 unknown，不偷偷猜。 |
| `DEF-18` | base/group 與 absolute-path 去重都大小寫敏感，不符 Windows 檔名直覺。 | **修**：group/去重 key 使用 Windows-aware casefold/canonical form，另保留首個 display spelling。 |
| `DEF-19` | 同 group 同型別是 silent last-write-wins；解析度/格式衝突由輸入順序決定。 | **修**：衝突必出 diagnostic；由業主另選 reject、顯式 precedence 或保留全部 variants。 |
| `DEF-20` | picker filter 被誤當白名單；任意 extension、甚至不可解碼/不存在 path 都可入組。 | **修**：T1 依真 decoder features 凍結 extension + decode preflight；16-bit/EXR 各有測試。 |
| `DEF-21` | unknown-only group 仍走完整 batch，通常零輸出且無 hard failure。 | **修**：`scan` 明列；`process` 預設 gate fail（或需顯式 `--allow-unknown`）。 |
| `DEF-22` | base extractor 會刪除 stem 中間所有型別 identifier，不只 terminal suffix。 | **修**：只移除已命中的 terminal span，不再二次全 stem 過濾。 |
| `DEF-23` | priority 同時受不可覆蓋 CE 表與 JSON key order 控制；自訂表無法真正覆蓋 CE suffix。 | **修**：凍結明示 priority，ambiguity 報錯；`--suffixes` 的 override/extend 語意分開。 |
| `DEF-24` | 舊 Tk panel 還留著未使用且不同的分類/分組演算法，容易被誤移植。 | **修**：Rust 規格只以本節 active call chain 為準；舊函式標 deprecated/後續另票移除。 |

`texproc` 預設 suffix 表仍預定以 `include_str!` 嵌入，`--suffixes <json>`
接受現有 JSON 形狀；但 DEF-13–24 中所有建議修正均須業主先裁決，T1 才能把
「相容」精確定義為保留資料格式，而非照抄上述缺陷。

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
