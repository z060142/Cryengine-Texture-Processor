# texproc v2 實作參考目錄（給 Asset Platform / APC）

> 2026-08-13。對象:CryEngine Texture Processor v2（本倉 `v2` 分支,workspace 根 = repo 根）。
> 讀者:Asset Platform（APC）Manager 與 M3「貼圖線原生化」的實作者。
> 目的:逐模組盤點 v2 有什麼值得抄、抄的時候要注意什麼坑。**本文只描述現況,不是規格提案**;
> v3 的形態選項寫在 `apc-v3-integration-options.md`。
> 所有斷言都附 `檔案:行`。凡與既有先行情報衝突處,標 ⚠ **修正**。

---

## 0. 結論先行

1. **最值得直接抄的是「決策紀錄」而不是程式碼**。v2 最大的資產是
   `docs/texture-pipeline-spec.md`（把舊 Python 版逐條逆向成 12 個 DEF 缺陷）與
   `docs/rust-workspace-design.md` D-03/D-06（像素工作域、貼圖類型辨識的完整裁決紀錄）。
   APC M3 若要重寫貼圖線,這兩份是現成的「不要再踩一次」清單。
2. **可以整段搬過去的程式碼有三塊**:`texproc/src/planar.rs` + `ops.rs`（無外部依賴的
   f32 影像核心 + 13 個運算原語)、`texproc/src/io.rs` 的魔數探測（只讀檔頭不解碼像素)、
   `texproc/src/grouping.rs` + `data/suffix_settings.json`（貼圖類型辨識規則表)。
   三塊都是 pure Rust、跨平台、零 C 依賴,符合 APC 的原生化鐵律。
3. **不要抄的是輸出層與色彩管理的現行取捨**。v2 輸出寫死 8-bit（`io.rs:73-96`),
   內部 f32 是 **sRGB encoded** 而非 linear（`docs/rust-workspace-design.md:39-44`),
   `PlanarImage` 硬性 clamp 到 `0..=1`（`texproc/src/planar.rs:35-39`)。
   M3 要求的 16-bit 保留與 HDR/alpha 透傳會直接撞上這三點,見 §2、§6。
4. **貼圖類型辨識是純檔名 + 檔頭,像素猜測已被業主明令移除**
   （`docs/rust-workspace-design.md:248-250` DEF-17 裁決)。這對 glTF 材質映射線是好消息:
   規則表是可完全靜態化的字串表,不需要影像解碼器。

---

## 1. 格式解碼與魔數探測

### 1.1 現況

| 項目 | 內容 | 位置 |
|---|---|---|
| 解碼器 | `image` 0.25,features 限定 `png/jpeg/tiff/exr/hdr/tga/bmp/webp` | `texproc/Cargo.toml:9` |
| 編碼器 | `tiff` 0.11 直接用（`image` 的 TIFF encoder 不暴露壓縮選項） | `texproc/Cargo.toml:12`、`docs/rust-workspace-design.md:35` |
| 接受副檔名 | `png jpg jpeg tif tiff exr hdr tga bmp webp` | `texproc/src/grouping.rs:17-18` |
| 探測入口 | `probe_header(path) -> HeaderInfo{channels, bit_depth, width, height}` | `texproc/src/io.rs:44-51` |
| 解碼入口 | `decode_image(path) -> PlanarImage` | `texproc/src/io.rs:53-71` |

### 1.2 魔數探測的實際做法（⚠ 修正先行情報)

「魔數探測格式」屬實,但**不是純魔數**。`probe_reader` 讀前 12 bytes 後依序比對
（`texproc/src/io.rs:137-174`）:

```
PNG   header[..8] == 137 80 78 71 13 10 26 10        io.rs:147
JPEG  header[..2] == FF D8                            io.rs:150
TIFF  header[..4] ∈ {"II*\0", "MM\0*"}                io.rs:153
EXR   LE u32(header[..4]) == 20000630                 io.rs:156
BMP   header[..2] == "BM"                             io.rs:159
WebP  header[..4]=="RIFF" && header[8..12]=="WEBP"    io.rs:162
TGA   ← 無魔數,靠副檔名 ext_hint 派發                io.rs:167-169
```

**坑 1:TGA 只能靠副檔名。** TGA 的簽章是 optional footer 不是 header,所以
`probe_reader` 收一個 `ext_hint` 參數專門處理它（`io.rs:167`,註解在 `io.rs:165-166`)。
APC 若要做「內容優先、副檔名只是提示」的探測,TGA 是必須破例的那一個。

**坑 2:`.hdr`(Radiance) 根本不走探測。** `classify_path` 在 header probe **之前**
就用副檔名把 `.hdr`/`.exr` 分流走（`texproc/src/grouping.rs:352-355`),註解明說
「Radiance HDR is not a probe-able format here」(`grouping.rs:349`)。所以支援清單裡
的 `hdr` 其實從未被 `probe_reader` 認識過——它是 passthrough,不是解碼格式。

**坑 3:探測與解碼是兩次獨立開檔。** `decode_image` 先 `probe_reader` 拿格式,再
`File::open` 第二次交給 `ImageReader::with_format`(`io.rs:55-70`)。好處是格式判定
不受 `image` 內部嗅探影響、壞處是每張圖兩次 syscall。APC 若走 blob/串流來源
（M2a 的 content-addressed 引用),這個「兩次開路徑」的形狀要改成單一 reader。

### 1.3 各格式的自寫檔頭解析器

v2 沒有用第三方 metadata crate,六個格式的檔頭各自手寫,全部是「只讀不解碼」:

| 格式 | 函式 | 位置 | 值得注意 |
|---|---|---|---|
| PNG | `probe_png` | `io.rs:280-306` | IHDR 長度必須 == 13,color_type 3(palette) 一律當 3 通道 |
| JPEG | `probe_jpeg` | `io.rs:308-355` | 走 marker 迴圈找 SOF,遇 SOS/EOI 前沒 SOF 就報錯 |
| TIFF | `probe_tiff` | `io.rs:370-430` | 只讀第一個 IFD 的 tag 256/257/258/277;BigTIFF 明確拒絕(`io.rs:378-381`) |
| EXR | `probe_exr` | `io.rs:481-521` | 走 attribute 鏈找 `channels`/`dataWindow` |
| TGA | `probe_tga` | `io.rs:179-196` | 固定 18-byte header |
| BMP | `probe_bmp` | `io.rs:202-226` | 同時吃 BITMAPCOREHEADER(12) 與 INFOHEADER 系 |
| WebP | `probe_webp` | `io.rs:230-278` | VP8/VP8L/VP8X 三種 chunk 各自解 |

**這批解析器對 APC 有直接價值**:Manager 的 catalog 要記錄 `width/height/channels/depth`
當 asset metadata 時,不需要為此解碼整張圖。全部是 `Read + Seek` 上的純函式,可以整塊搬。

**坑 4:防禦上限是硬編碼的魔術數字。** TIFF IFD entry 上限 4096(`io.rs:387`)、
TIFF metadata value count 上限 1024(`io.rs:439`)、EXR attribute 上限
16 MiB(`io.rs:17`, `io.rs:498`)、EXR header 迴圈上限 1024 圈(`io.rs:490`)、
C-string 上限 255(`io.rs:491`)。這些是 anti-DoS 的合理起點,但如果 APC 要接受
不受信任的上傳素材,建議把它們提成可設定的 policy 而不是常數。

### 1.4 錯誤處理哲學

一句話:**單一字串錯誤型別 + 早失敗 + 分組層降級為診斷**。

- `TexprocError` 只包一個 `String`,沒有錯誤碼、沒有 source chain
  (`texproc/src/error.rs`,全檔 42 行)。所有 `?` 靠 `From<io::Error>`/`From<ImageError>` 轉字串。
- **探測失敗不會炸掉整個掃描**:`classify_path` 把 probe 錯誤轉成
  `Severity::Error` 的 `DEF-20` 診斷,該檔改列 `unknown` 繼續(`grouping.rs:356-368`)。
- **不支援的副檔名也是診斷不是錯誤**(`grouping.rs:335-344`)。
- 但**資料夾展開時靜默跳過無關副檔名**,只有「明確列出的檔案」才產生 DEF-20
  (`grouping.rs:464-471` 的註解與 `has_supported_extension`)。這是實戰調校過的
  UX 決策:匯入整個資料夾不該被 `readme.txt` 洗版。測試錨定在
  `grouping.rs:604-656`。
- **批次層 catch panic**:單一 group 的 `Err` 或 panic 都被
  `catch_unwind` 收成 `FailedGroup`,整批繼續跑(`texproc/src/batch.rs:85-99`)。

> **APC 該抄哪條線**:catalog 的 metadata 萃取抄 §1.3;
> ingest/import 的錯誤呈現抄「診斷降級 + 批次不中斷」這個模式(`batch.rs:85-109`),
> 但**不要抄 `TexprocError` 的字串型別**——APC 的 job 結果需要可路由的錯誤碼。

---

## 2. 分平面 f32 內部表示與色彩管理

### 2.1 資料結構

```rust
pub struct PlanarImage { pub width: u32, pub height: u32, pub planes: Vec<Vec<f32>> }
```
`texproc/src/planar.rs:3-8`。1–4 個 plane,每 plane 長度 == w*h。

建構子 `PlanarImage::new` 有三道**硬性驗證**(`planar.rs:11-47`):

| 檢查 | 行 | 後果 |
|---|---|---|
| 通道數必須 1..=4 | `planar.rs:15-20` | 不支援多層/任意通道數 |
| 任一 sample 非 finite → Err | `planar.rs:30-34` | NaN/Inf 直接失敗 |
| 任一 sample 不在 `0.0..=1.0` → Err | `planar.rs:35-39` | ⚠ **HDR 值不可能存在於此型別中** |

**這是 v2 最重要的單一結構性限制。** 它讓所有 `OP-*` 原語可以省略 clamp、讓
`expect()` 在內部到處合法（例如 `ops.rs:36`、`ops.rs:262`),代價是整條管線
在設計上就無法承載 > 1.0 的資料。

### 2.2 位深轉換點

**入口(全部正規化到 0..1)** `planar.rs:57-92`:

```
u8  → f32 / 255.0                      planar.rs:63-66
u16 → f32 / 65535.0                    planar.rs:68-77
f32 → clamp(0.0, 1.0)  ⚠ HDR 被裁掉    planar.rs:79-92
```

`dynamic_to_planar` 把 `image` 的 10 種 DynamicImage 變體全部映射進來,
含 Luma16/LumaA16/Rgb16/Rgba16/Rgb32F/Rgba32F(`io.rs:98-135`)。
**所以 16-bit 輸入是真的被完整保留在 f32 domain 的**,不是先降到 8-bit。

**出口(唯一,寫死 8-bit)** `planar.rs:94-107`:

```rust
pub fn quantize_u8(value: f32) -> u8 { (value.clamp(0.0,1.0) * 255.0).round() as u8 }
```

`write_tiff_lzw` 只接受 1/3/4 通道,並且只呼叫 `Gray8/RGB8/RGBA8`
(`io.rs:73-96`,match 在 `io.rs:89-94`)。**沒有 16-bit 輸出路徑,一行都沒有。**

> ⚠ **修正先行情報**:「輸出僅 8-bit」正確,但要補一句——**輸入端的 16-bit 精度
> 是保留的,整條 INT/OUT 管線都在 f32 上跑**。M3 要 16-bit 輸出**不需要動核心**,
> 只需要在 `planar.rs` 加 `to_interleaved_u16` 並在 `io.rs:89-94` 加
> `Gray16/RGB16/RGBA16` 分支。這是 v2 給 M3 最省力的一個交接點。

### 2.3 色彩管理:encoded f32 + per-op linear islands

這是業主親自裁決的架構(`docs/rust-workspace-design.md:37-46`,決策編號 D-03):

> 內部表示 = planar f32、值域 0–1、**預設保持 sRGB 編碼值**。
> **僅兩個修正點內部做 linear 往返**(decode → 運算 → encode)。

兩個 island:

| Island | 運算 | 位置 |
|---|---|---|
| DEF-08 修正 | `lerp(gray62, diffuse, M_eff)` 在 linear 域 | `texproc/src/pipeline.rs:457-493`(decode 在 `472`、`486`,encode 在 `487`) |
| DEF-09 修正 | `OUT-DIFF` 的 AO Multiply 在 linear 域 | `texproc/src/output.rs:467-487`(第 483 行單行完成 decode→乘→encode) |

其餘所有路徑(resize、invert、copy-opacity、colorize、gray、fallback…)**完全不碰
transfer function**(`docs/rust-workspace-design.md:44`)。

`srgb_decode`/`srgb_encode` 是標準 IEC 分段函式,寫在 `texproc/src/ops.rs:9-25`,
round-trip 誤差測試在 `ops.rs:484-489`。

**坑 5:灰階用 BT.601 權重,且是在 encoded 域算的。** `LUMA_WEIGHTS = [0.299, 0.587, 0.114]`
(`texproc/src/constants.rs:11`),`luma_at` 直接對 encoded 值加權(`ops.rs:318-326`)。
只有 metal gate 的 `linear_luma` 例外,先 decode 再加權(`pipeline.rs:538-546`)。
同一個「亮度」在管線裡因此有兩種定義。APC 若統一走 linear 工作域,這個不一致會自動消失,
但**輸出將與 v2 不等價**。

**坑 6:規格書自己承認 linear 才是對的。** `docs/texture-pipeline-spec.md:539-541`:
```yaml
working_space: linear_f32_planar   # 建議值,非現況
current_space: srgb_u8_interleaved # 現況
```
以及 `texture-pipeline-spec.md:530` 的重寫建議。業主最終選了折衷方案(D-03),
理由是「差異範圍 = 缺陷範圍」錨點 7:直通路徑必須與舊 Python 版逐像素差 ≤ ±1/255
(`docs/rust-workspace-design.md:46`)。**APC 沒有這個相容性包袱,可以直接走 linear。**

> **APC 該抄哪條線**:M3 的影像核心。`planar.rs` + `ops.rs` 兩檔約 660 行,
> 零外部依賴(只用 `image::imageops::resize`),可以整塊移植。
> **抄的時候要改三件事**:(a) 放寬 `0..=1` 的 clamp 成可選 policy 以承載 HDR;
> (b) 加 u16 出口;(c) 決定是否把工作域改成 linear(改了就與 v2 輸出不等價,要另設驗收)。

---

## 3. 貼圖類型辨識與 CE preset 映射（材質映射裁定的參照來源）

> 這一節是 `gltf_line_design.md` 裡「參照 texproc v2 的貼圖類型辨識方案」所指的東西。
> 完整規則表如下。

### 3.1 三層架構

```
檔名 stem
  ↓ ① peel_qualifiers   剝掉結尾的 removable/解析度 token   grouping.rs:480-498
  ↓ ② 類型判定(五段優先序,見 3.3)                          grouping.rs:371-436
  ↓ ③ base_name → group key = base_name.to_lowercase()      grouping.rs:230
```

`parse_base_name` 是同一套規則的「純字串、不開檔」版本(`grouping.rs:285-313`),
專供 GUI 的 Add-Related 掃描用(效能紅線,註解在 `grouping.rs:277-284`)。
**兩條路徑的 base-name 推導必須保持一致**,測試錨在 `grouping.rs:688-711`。

### 3.2 剝除規則(qualifier peeling)

`peel_qualifiers`(`grouping.rs:480-498`)從 stem **結尾**反覆剝 token,
以 `_` 或 `-` 分隔,命中就繼續、不命中就停:

- 解析度 token:`\d+k`(任意位數 + `k`),`grouping.rs:488-490`
- removable 集合預設 = `{dx, gl, directx, opengl, 2k, 4k, 8k}`,`grouping.rs:73-76`
- JSON 可用 `removable_suffixes` 追加(不可移除內建),`grouping.rs:79-83`

實測語意(`grouping.rs:672-686`):`stone_normal_dx` → `stone_normal`;
`dx_stone_normal` → 不變(只剝結尾)。

### 3.3 類型判定的五段優先序（**這就是規則表本體**）

`classify_path` 的順序不可換(`grouping.rs:371-436`):

| # | 層 | 內容 | 位置 |
|---:|---|---|---|
| 1 | **ARM alias** | 長名優先的固定清單,見 3.4 | `grouping.rs:371-393`、`500-517` |
| 2 | **CE 凍結後綴** | `diff→diffuse`, `ddna→normal`, `ddn→normal`, `displ→displacement`, `spec→specular`, `em→emissive`, `emissive→emissive`, `sss→sss` | `grouping.rs:33-42`、`395-399` |
| 3 | **歧義單字母 `a`/`d`** | 由 **header 通道數**消歧,見 3.5 | `grouping.rs:400-419` |
| 4 | **設定表後綴** | `suffix_settings.json`,見 3.6(`a`/`d` 在此層被跳過) | `grouping.rs:420-427` |
| 5 | **落空** | `DEF-17` warning + 列 `unknown`,**不做像素猜測** | `grouping.rs:429-436` |

第 2 層是**不可覆蓋**的:載入自訂 suffix 表時,若某後綴與 CE 凍結表衝突且指向
不同型別,直接拒絕載入(`grouping.rs:105-114`)。同一後綴指給兩個型別也拒絕
(`grouping.rs:97-104`)。

後綴匹配一律要求 **terminal + 分隔符邊界**:`strip_terminal` 要求後綴前一字元是
`_` 或 `-`,或整個 stem 就等於後綴(`grouping.rs:519-530`)。這是 DEF-15/DEF-22 的修正,
避免 `single_nrm`/`shingle_n` 之類誤判。

### 3.4 ARM 打包貼圖的 alias → 通道序對照

`match_arm_alias`(`grouping.rs:500-517`),**清單順序 = 匹配優先序,長名在前**:

| alias | 判定通道序 | 診斷 | 位置 |
|---|---|---|---|
| `occlusion-roughness-metallic` / `occlusion_roughness_metallic` | ARM | — | `grouping.rs:374-377` |
| `ao-rough-metal` / `ao_rough_metal` | ARM | — | 同上 |
| `arm` | ARM | — | 同上 |
| `orm` | ORM | — | `grouping.rs:378` |
| `rma` | RMA | — | `grouping.rs:379` |
| `rm` / `ra` | **`configured`**(用設定值) | `DEF-16` warning | `grouping.rs:380`、`383-391` |

通道拆解在 `pipeline.rs:212-223`:ARM 與 ORM **同序**(R=ao, G=roughness, B=metallic),
RMA 是 (R=roughness, G=metallic, B=ao)。
執行期還會再讀一次檔名覆寫設定值(`pipeline.rs:227-250`),與掃描期規則平行存在
——**兩處必須同步,是一個結構性風險**。

### 3.5 歧義單字母 `_a` / `_d` 的 header 消歧（業主方案,DEF-14）

`grouping.rs:400-419`,裁決紀錄在 `docs/rust-workspace-design.md:240-247`:

| 後綴 | header 通道數 3 或 4 | 通道數 1 或 2 | header 讀不到 |
|---|---|---|---|
| `_a` | `diffuse` | `alpha` | `unknown` + `DEF-14` error |
| `_d` | `diffuse` | `displacement` | `unknown` + `DEF-14` error |

**這是整套辨識裡唯一的「內容啟發式」,而且只讀檔頭 metadata,不解碼像素。**
其餘一律純檔名。像素猜測在 DEF-17 被業主明令移除
(`docs/rust-workspace-design.md:248-250`)。

### 3.6 設定表(`texproc/data/suffix_settings.json`,共 12 個 source type)

| source type | 後綴清單 | 行 |
|---|---|---|
| `diffuse` | `diff, diffuse, albedo, basecolor, color, col, a, d` | 2-11 |
| `normal` | `normal, nrm, norm, _n, nm, ddn, ddna, nor, nor_dx, nor_gl, Normal, nor` | 12-25 |
| `specular` | `spec, specular, _s` | 26-30 |
| `glossiness` | `gloss, glossiness, smoothness, _g, Glossy` | 31-37 |
| `roughness` | `rough, roughness, _r` | 38-42 |
| `displacement` | `disp, displacement, height, bump, _h, displ` | 43-50 |
| `metallic` | `metal, metallic, metalness, _m` | 51-56 |
| `ao` | `ao, ambient, occlusion` | 57-61 |
| `alpha` | `alpha, opacity, transparency` | 62-66 |
| `emissive` | `emissive, emission, glow, _e` | 67-72 |
| `sss` | `sss, subsurface` | 73-76 |
| `removable_suffixes` | `dx, gl` | 77-80 |

載入時 `normalize_suffix` 會 trim、剝掉開頭的 `_`/`-`、轉小寫(`grouping.rs:532-534`),
所以 JSON 裡的 `_n` 與 `n` 等價(這是 DEF-13 的修正——舊 Python 版會編成 `__n` 而失效,
見 `docs/rust-workspace-design.md:82-84`)。`arm` 不在 JSON 裡,它是硬編碼層。

### 3.7 source type → CE 輸出 → .mtl 槽位（完整三段映射）

**第一段:source type → CE 輸出鍵**(`pipeline.rs` INT-* 規則 + `output.rs` OUT-* 規則)

```
diffuse/albedo + metallic  →  albedo    →  _diff
diffuse + metallic         →  reflection→  _spec        (無 specular 時)
specular                   →  reflection→  _spec
normal                     →  normal    →  _ddna.rgb
roughness/glossiness/arm.G →  glossiness→  _ddna.a  (glossiness = 1 − roughness)
displacement/height        →  height    →  _displ  (RGBA 四通道同值)
emissive                   →            →  _em
sss                        →            →  _sss
ao                         →  ao        →  只在 diff_format=diffuse_ao 時併入 _diff
alpha                      →            →  併入 _diff 的 alpha 通道
```
規則出處:`texproc/src/pipeline.rs:147-184`(Stage 1 順序)、
`texproc/src/output.rs:176-212`(Stage 2 順序)。

**第二段:輸出鍵 → 檔名後綴**,唯一事實來源是 `ce-schema`
(`ce-schema/src/lib.rs:57-84`,`texproc` 透過 `output.rs:536-552` 的 `named_output` 呼叫):

| output_key | 後綴 | 特例 |
|---|---|---|
| `diff` | `_diff` | |
| `spec` | `_spec` | |
| `ddna` | `_ddna` / `_ddn` | **有 gloss 來源 → `_ddna`,無 → `_ddn`**(`ce-schema/src/lib.rs:58-60`、`output.rs:363-375`) |
| `displ` | `_displ` | |
| `emissive` | **`_em`** | 不是 `_emissive`(`ce-schema/src/lib.rs:79`) |
| `sss` | `_sss` | |
| `opacity` | `_opacity` | 只有 converter 用 |
| `roughness` | `_roughness` | 只有 converter 用 |

**第三段:CE `.mtl` Texture Map 槽位**,凍結在
`ce-schema/data/converter_schema.json` 的 `mtl.texture_maps.entries`
(查詢 API 在 `ce-schema/src/lib.rs:87-94`)。完整表:

| texture_type | CE map | 匯出 | 後綴 | accepted |
|---|---|:--:|---|---|
| `diffuse` | `Diffuse` | ✓ | `_diff` | `_diff` |
| `normal` / `bumpmap` | `Bumpmap` | ✓ | `_ddn` | `_ddn`, `_ddna` |
| `specular` | `Specular` | ✓ | `_spec` | `_spec` |
| `smoothness` | `Smoothness` | ✓ | `_ddna` | `_ddna` |
| `displacement` / `height` / `heightmap` | `Heightmap` | ✓ | `_displ` | `_displ` |
| `emissive` / `emittance` | `Emittance` | ✓ | `_em` | `_em`, `_emissive` |
| `alpha` / `opacity` / `mask` / `transparency` | `Opacity` | ✓ | （無） | — |
| `subsurface` | `SubSurface` | ✓ | `_sss` | `_sss` |
| `translucency` | `Translucency` | ✓ | `_trans` | `_trans` |
| `environment` | `Environment` | ✓ | `_cm` | `_cm` |
| `detail` | `Detail` | ✓ | `_detail` | `_detail` |
| `decal` / `custom` | `Decal` / `Custom` | ✓ | （無） | — |
| **`ao`** | （無） | **✗** | — | `known_internal_non_mtl_channel` |
| **`glossiness`** | （無） | **✗** | — | `known_internal_non_mtl_channel` |

該表的 `source_evidence` 欄位聲明來源是
`Code/CryEngine/Cry3DEngine/MaterialHelpers.cpp`,規則是
「只有具備 CE material Texture Map 名稱的型別才寫成 `.mtl <Texture>` 節點」。

**坑 7:`roughness` 在 converter 端被別名成 `Opacity`。**
`converter/src/texture_resolver.rs:116-120` 的 `OUTPUT_RULES` 把 `roughness`
的 `ce_map_alias` 寫成 `"Opacity"`,測試 `roughness_uses_observed_opacity_alias`
(`texture_resolver.rs:372-385`)註明這是**觀察到的實際 CE 行為**而非設計。
APC 做 glTF 材質映射時遇到 roughness 槽,要知道 v2 這裡是個歷史包袱,不要盲抄。

### 3.8 converter 端的第二份後綴表（重複實作警告）

`converter/src/texture_resolver.rs:5-59` 的 `KNOWN_TEXTURE_SUFFIXES` 是**另一份
52 條的後綴清單**,用途不同(從 FBX 材質的貼圖檔名反推 base name,
`texture_resolver.rs:129-153`),但與 `suffix_settings.json` 有大量重疊且**不共用**。

> **APC 該抄哪條線**:glTF/FBX 材質映射線。
> 抄 §3.3 的五段優先序骨架 + §3.5 的 header 消歧 + §3.7 的三段映射表。
> **不要抄** §3.8 的第二份表(重複)、§3.4 執行期與掃描期各判一次 ARM(重複)、
> §3.7 坑 7 的 roughness→Opacity(歷史包袱)。
> 若照 `gltf_line_design.md` 的「只做最低限度不強求慣例」,建議的最小子集是:
> **CE 凍結後綴表(8 條)+ diffuse/normal/roughness/metallic/ao/emissive 六個
> source type 的主要 alias**,其餘(sss/translucency/detail/decal/custom)先不做。

---

## 4. 正規化決策:v2 做到哪裡為止

**答案:做到 8-bit TIF/LZW 為止,DDS 交給 RC.exe,而且 v2 自己不呼叫 RC——是 GUI 呼叫。**

| 決策 | v2 做法 | 位置 |
|---|---|---|
| **resize** | 有,但只縮不放。Lanczos3,`max(w,h) > N` 才縮,保持長寬比 | `ops.rs:98-123`;設定鍵 `output_resolution`(`original` 或數字) `output.rs:22-27` |
| **副圖對齊** | T-017:副圖(AO/alpha/gloss/metallic)強制 `resize_to` 主圖尺寸,**允許放大與非等比拉伸** | `ops.rs:131-150`,呼叫點 `output.rs:316`、`321`、`366`、`pipeline.rs:306`、`444` |
| **mipmap** | **完全不做**。RC 的事 | 全倉無 mip 相關程式碼 |
| **壓縮參數** | **完全不做**。RC 的事 | — |
| **輸出格式** | 寫死 8-bit TIFF + LZW | `io.rs:87`(`Compression::Lzw`)、`io.rs:89-94` |
| **dither** | 設定鍵存在但**是 no-op stub** | `output.rs:80`/`106`,測試 `output.rs:947-980` 斷言開關前後輸出相同 |
| **CryTif chunk** | **完全沒有** | `write_tiff_lzw`(`io.rs:73-96`)只寫標準 colortype,無任何自訂 TIFF tag |
| **HDR passthrough** | `.hdr` 逐 byte 複製;`.exr` 解碼後轉 Radiance `.hdr`,**繞過 `PlanarImage` 以保留 >1.0** | `texproc/src/passthrough.rs:35-82`,註解在 `passthrough.rs:1-8` |
| **RC 呼叫** | 只在 GUI 層。`RC.exe <tif> /refresh /userdialog=0`,cwd = 輸出目錄 | `texproc-gui/src/worker.rs:479-495` |

**坑 8:`/savesettings` 從未被使用。** 全倉沒有任何 `savesettings` 字串。
v2 完全不寫 CryTif 的 per-texture 設定 chunk,RC 只能吃預設 preset。
先行情報說「無 CryTif chunk 寫入」——**證實,而且比想像的更徹底:連 RC 的
settings 旗標都沒用**。

**坑 9:六個 fallback 開關的預設值是驗收錨點的一部分。**
`generate_missing_spec = true`,其餘四個 `generate_missing_*`/`generate_sss_from_diffuse`
= false,`dither = false`(`output.rs:99-106`)。
規格 §10 錨點 6 明列這組預設不得漂移(`docs/texture-pipeline-spec.md:725`),
測試在 `output.rs:848-865`。空 group 只會產出一張純色 `_spec`。

**坑 10:metal gate(T-014)是 v2 獨有的正規化決策,舊 Python 版沒有。**
per-pixel 有效金屬度 `M_eff = T(C1)·T(C2)·T(C3)`,
把不規範素材強制二值化回 PBR(`pipeline.rs:511-576`,設計文件
`docs/metal-gate-design.md`)。預設開啟,`metallic_cut = 0.5`、
`spec_min = 180/255`、`gloss_cut = 0`(關閉)、`transition = 0.05`
(`pipeline.rs:92-102`)。關掉時輸出與 pre-gate 位元相同(`pipeline.rs:521-523`)。
**這是「鏽面被標 metallic=1」問題的解**,設計論證在 `metal-gate-design.md:44-46`。
APC 若要做 PBR→CE 轉換,這條規則值得整段抄,而且它是純數學,沒有依賴。

---

## 5. CLI / 批次工作流與錯誤呈現

### 5.1 CLI 契約(已凍結)

```
texproc scan    [--suffixes s.json] [--out groups.json] INPUTS...
texproc process [--settings cfg.json] [--suffixes s.json] [--groups groups.json]
                [--allow-unknown] --out DIR [INPUTS...]
```
`texproc/src/main.rs:27-67`;凍結紀錄在 `docs/tickets/T-012-t4-cli-orchestration.md`。

**退出碼契約**(`main.rs:14`,寫進 `--help`):

| code | 意義 |
|---:|---|
| 0 | 成功 |
| 1 | runtime / I/O failure |
| 2 | CLI / configuration error |
| 3 | **grouping gate failure** |

### 5.2 經過實戰的 UX 決策(值得 APC 抄)

1. **scan / process 分離,中間可人工複核。** `scan --out groups.json` 產出可讀可改的
   分組 JSON,`process --groups groups.json` 吃回來(`main.rs:120-134`)。
   GUI 的 unknown 人工指派就是走這個介面。
   → **APC 的 asset.import 應該有同構的 dry-run**。

2. **「未分類」是硬性閘門而非警告。** 只有 `unknown` 沒有任何已知 slot 的 group
   會讓 `process` 直接 exit 3,必須顯式 `--allow-unknown` 才放行
   (`main.rs:136-146`)。裁決紀錄 DEF-21(`docs/rust-workspace-design.md:225`)。
   → 這條是「不要靜默產出垃圾」的實戰教訓。

3. **passthrough 不得觸發閘門。** `.hdr`/`.exr` 天生無型別後綴,若照 2. 會全部卡住,
   所以 `unknown_only_groups` 特別把 passthrough 排除
   (`grouping.rs:194-206`,註解在 `196-198`)。
   → 新增「非典型資產類別」時必須同步檢查既有閘門。

4. **設定 JSON 嚴格鍵檢查。** 未知鍵 = configuration error 而非忽略
   (`texproc/src/settings.rs:112`)。
   → typo 不會靜默生效。

5. **`--groups` 與 `--suffixes` 互斥。** 分組已定案後不允許再換規則表
   (`main.rs:57-58`)。

6. **進度走 stderr,結果走 stdout。** `scan` 的 JSON 在 stdout,每 group 一行進度
   在 stderr(`main.rs:85-95`、`154-175`)。管線友善。

7. **批次不中斷。** 單 group 失敗(含 panic)記錄後繼續,最後統一報告
   (`batch.rs:85-109`、`main.rs:162-179`)。

8. **記憶體 admission control。** 掃描期的 header 就足以估算解碼後 working set
   (`w×h×ch×4 × 3`),據此把 group 切成 wave,每個 wave 總量 ≤ 預算
   (預設 = 實體 RAM 的 50%,`TEXPROC_MEM_BUDGET_MB` 可覆寫)
   (`batch.rs:193-279`)。超過整個預算的單一 group 獨佔一個 wave(`batch.rs:191-192` 註解)。
   → **這條對 APC 的 worker 併發控制直接可用**:不需要真的解碼就能排程。

9. **依 texture_types 開關做「來源剪枝」。** 使用者關掉 `_ddna` 輸出時,
   normal/gloss/roughness 根本不會被解碼(`batch.rs:344-363`)。
   → job 的資源估算要吃這層剪枝,否則預算永遠高估。

10. **RC 併發是自適應的。** `N` 從 `clamp(cores/6, 1, 4)` 起跳,每完成一檔且距上次
    調整 ≥1s 才依即時 CPU 與可用 RAM 決定 grow/shrink;CPU > 92% 或
    可用 RAM < 4 GiB 就退讓,反之 CPU < 70% 且 RAM 足夠再加一個
    (`texproc-gui/src/worker.rs:281-304`;pool 本體 `worker.rs:335-468`)。
    取消時**主動 kill 所有 in-flight child**,不留孤兒(`worker.rs:376-382`)。
    → APC 的 worker 若要 spawn 外部工具(RC、DCC),這套回饋控制是現成的。

### 5.3 錯誤呈現

- 診斷有結構:`{severity, code, message, path?, group?}`(`grouping.rs:136-145`),
  code 直接沿用 DEF 編號,可回溯到 `rust-workspace-design.md` 的裁決紀錄。
- GUI 把診斷收進狀態列的可點擊 chip + popover,而不是 modal
  (`texproc-gui/src/main.rs:1459-1598`)。
- **診斷碼與設計文件的 DEF 編號同名**,是 v2 最好的一個小決策:
  使用者看到 `DEF-19`,開發者查文件就知道是「同 slot 衝突,面積大者勝」。

---

## 6. 已知缺口確認

| 先行情報 | 證實? | 證據與補充 |
|---|:--:|---|
| `image` + `tiff` crate | ✓ | `texproc/Cargo.toml:9,12`。`image` 只解碼,`tiff` 專責 LZW 編碼(`rust-workspace-design.md:35`) |
| 分平面 f32 處理 | ✓ | `planar.rs:3-8`。⚠ 補充:是 **encoded sRGB** f32,不是 linear(`rust-workspace-design.md:39-44`) |
| 魔數探測格式 | ✓（有例外） | `io.rs:137-174`。⚠ TGA 靠副檔名(`io.rs:167`)、`.hdr` 根本不探測(`grouping.rs:352-355`) |
| 缺 psd / svg / jp2 | ✓ | 支援清單 `grouping.rs:17-18` 無此三者;`Cargo.toml:9` 的 image features 亦無 |
| 無 CryTif chunk 寫入 | ✓ | `io.rs:73-96` 只寫標準 colortype。⚠ 補充:連 RC 的 `/savesettings` 都沒用,全倉零命中 |
| 輸出僅 8-bit | ✓（需補充） | `io.rs:89-94` + `planar.rs:94-107`。⚠ **輸入 16-bit 精度是保留的**,整條管線在 f32 上跑,只有最後量化是 8-bit |

### 6.1 v2 自己文件裡承認的限制

- **`dither` 是未實作的 stub**:設定鍵存在、GUI 有 checkbox、但不改變輸出
  (`output.rs:947-980`)。D-05 把它降級為 opt-in 並註明「若引擎內目視出現 banding
  再翻預設」(`docs/rust-workspace-design.md:52-56`)。實際上連實作都沒做。
- **色彩工作域是折衷不是最佳**:`texture-pipeline-spec.md:539-541` 與 `:530` 明白
  建議 linear,D-03 因相容性錨點選了 encoded + islands。
- **`_ddna` 的 gloss 來源不走一般解析鏈**:只認 intermediate 層
  (`output.rs:363-368`),這是舊行為的延續(`texture-pipeline-spec.md:372`)。
- **ARM 通道序在掃描期與執行期各判一次**(`grouping.rs:371-393` vs `pipeline.rs:227-250`),
  文件未承認,是本次盤點新發現。
- **converter 有第二份後綴表**(`texture_resolver.rs:5-59`),文件未承認,本次新發現。
- **fixtures 未進 git**:`docs/rust-workspace-design.md:299`(Q3「先本機路徑,不進 git」)。
  KB3D 語料在 `Z:\`、RC 在 `S:\`,多數端到端測試標 `#[ignore]`
  (`texproc-gui/src/worker.rs:1017`、`1188`、`1458` 等)。**APC 要拿 v2 當參照時,
  跑不動它的驗收套件,只能讀規格與單元測試。**

---

## 7. 一頁式「該抄什麼」對照

| APC 的線 | 抄 v2 的什麼 | 位置 | 抄的時候要改 |
|---|---|---|---|
| M3 影像核心 | `PlanarImage` + 13 個 `OP-*` | `planar.rs`、`ops.rs` | 放寬 0..1 clamp;加 u16 出口;決定 linear vs encoded |
| M3 編碼/解碼 | 魔數探測 + 六個檔頭解析器 | `io.rs:137-586` | TGA 副檔名例外要保留;上限常數提成 policy |
| M3 PBR 轉換 | metal gate `M_eff` | `pipeline.rs:511-576` | 純數學,可直接抄 |
| M3 CE 輸出 | 三段映射表 + `_ddna`/`_ddn` 特例 | `ce-schema/src/lib.rs:57-94` + schema JSON | 保留 `_em` 不是 `_emissive` 這個特例 |
| glTF 材質映射線 | 五段優先序 + header 消歧 + CE 槽位表 | `grouping.rs:371-436`、`suffix_settings.json` | 只做最低限度子集(見 §3.8 末段建議) |
| catalog metadata | `probe_header` | `io.rs:44-51` | 改成單一 reader(支援 blob) |
| job 排程 | header-based memory admission + wave | `batch.rs:193-279` | 直接可用 |
| worker 併發 | 自適應 RC pool + 取消時 kill child | `worker.rs:281-495` | 直接可用 |
| import UX | scan/process 分離 + unknown 硬閘門 + 嚴格鍵檢查 | `main.rs:14,120-146`;`settings.rs:112` | 錯誤型別要換成可路由的碼 |
| 錯誤呈現 | 結構化診斷 + 碼與設計文件同名 | `grouping.rs:136-145` | 直接可用 |
| **不要抄** | `TexprocError` 字串錯誤型別 | `error.rs` | 全檔 42 行,無錯誤碼無 source chain |
| **不要抄** | converter 的第二份後綴表 | `texture_resolver.rs:5-59` | 與 `suffix_settings.json` 重複 |
| **不要抄** | roughness → `Opacity` 別名 | `texture_resolver.rs:116-120` | 歷史包袱 |
| **不要抄** | `dither` 設定鍵 | `output.rs:80` | 是 stub,沒有實作 |
