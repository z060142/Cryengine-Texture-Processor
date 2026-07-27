# T-016 — 來源圖片型式擴充：TGA / BMP / WebP

狀態：DONE（審查通過 2026-07-28；審查者獨立重跑 texproc/GUI 測試 + 閘門全綠）
業主裁決（2026-07-27，修訂）：PSD 取消（原方案需新依賴 `psd` crate 且僅
8-bit）；改為凡 **image crate 現成 feature、零新依賴條目**且合理的來源
格式均納入。「合理」= 美術實際會交付貼圖的格式：**TGA、BMP、WebP**。
明確不收：GIF/ICO/PNM/QOI/farbfeld（非貼圖交付格式）、DDS 輸入（本工具的
輸出格式，解碼支援殘缺）、AVIF（需原生解碼依賴）。

## 前置事實（開票偵察）

- 解碼唯一入口：`texproc/src/io.rs` — `probe_reader` 以 magic bytes 判型
  （`SupportedFormat` enum）→ `decode_image` 映射 `ImageFormat` →
  `dynamic_to_planar`。`probe_header` 供批次記憶體額度估算（w/h/channels）。
- TGA：image `tga` feature。**檔首無 magic**（簽名在檔尾且非必有）——須以
  副檔名分派；header 固定 18 bytes，w/h 在 offset 12/14（LE u16）。
- BMP：image `bmp` feature；magic `BM`。
- WebP：image `webp` feature（純 Rust image-webp，feature 的傳遞依賴，
  與既有 exr feature 同標準，不算新依賴條目）；magic `RIFF….WEBP`。

## 工作內容

1. `texproc/Cargo.toml`：image features 加 `"tga"`、`"bmp"`、`"webp"`。
2. `texproc/src/grouping.rs` `SUPPORTED_EXTENSIONS`：加 `"tga"`、`"bmp"`、
   `"webp"`。
3. `texproc/src/io.rs`：
   - `SupportedFormat` 加 `Tga`/`Bmp`/`WebP`。判型：BMP/WebP 走 magic；
     TGA 以**副檔名**分派（現行 API 若只吃 reader，調整為可帶路徑/副檔名
     提示；其他格式維持 magic 優先）。
   - `probe_header`：三格式各自解 header 出 w/h/channels（記憶體額度用；
     TGA 直讀 18-byte header；BMP 讀 BITMAPINFOHEADER；WebP 讀 VP8/VP8L/
     VP8X chunk 尺寸）。
   - `decode_image`：三者均走 image crate → `dynamic_to_planar`。
4. GUI 檔案選取對話框的副檔名過濾器若有列舉，加入 tga/bmp/webp
   （`texproc-gui/src/file_dialog.rs` 檢查）。

## 驗收錨點

1. 單元：合成 TGA（RLE 與非 RLE 各一）、合成 BMP、合成 WebP（無損）解碼後
   與同內容 PNG 逐像素相等（image crate 可寫 TGA/BMP/WebP-lossless 供
   fixture 生成；有損 WebP 不做位元比對，僅驗可解）。
2. `probe_header` 對三格式回報正確 w/h/channels（額度估算不退化為 0）。
3. 混合輸入（如 `X_basecolor.png` + `X_normal.tga` + `X_ao.bmp` +
   `X_roughness.webp` 同組）scan→process 出完整 TIF 組。
4. `run_gates.ps1` 全綠（既有 golden 零影響）。

## 明確禁止

- 不動 CLI 契約。不新增 `[dependencies]` 條目（image features 除外）。
- 不動 T-015 的 hdr/exr 分流語意（tga/bmp/webp 走**一般 TIF 管線**）。

## DoD

- 錨點全數通過；回報：判型分派實作方式（TGA 副檔名分派的接線點）、
  probe_header 三格式的實作位置、新增測試清單。

## 實作紀錄（2026-07-27）

狀態：DONE。分支 v2，未提交（待審查者驗收後提交）。

### 判型分派：TGA 副檔名接線點

`probe_reader` 原本只吃 reader，改為 `probe_reader(reader, ext_hint: Option<&str>)`
（`texproc/src/io.rs`）。magic 判型順序不變（PNG→JPEG→TIFF→EXR），其後新增
BMP（magic `BM`）與 WebP（magic `RIFF….WEBP`，故 magic 讀取緩衝從 8 bytes
擴為 12 bytes）。所有 magic 都不匹配時，才用 `ext_hint == "tga"`（大小寫不敏感）
分派到 `probe_tga` / `SupportedFormat::Tga`——其他格式維持 magic 優先，TGA 是唯一
靠副檔名的分支。兩個唯一呼叫端 `probe_header` 與 `decode_image` 各自從路徑取
`extension_hint(path)` 傳入；`decode_image` 的 `SupportedFormat`→`ImageFormat`
match 新增 `Tga`/`Bmp`→`ImageFormat::Tga`/`Bmp`、`WebP`→`ImageFormat::WebP`，三者
均走既有 `dynamic_to_planar`，未觸及 T-015 hdr/exr passthrough 分流。

### probe_header 三格式解析位置（均在 `texproc/src/io.rs`）

- `probe_tga`：直讀 18-byte 固定 header，w/h = offset 12/14 LE u16，pixel depth
  = offset 16（8/16/24/32 → channels 1/2/3/4），bit_depth 固定 8。
- `probe_bmp`：14-byte 檔頭（`BM`）後讀 DIB header size；size==12 為
  BITMAPCOREHEADER（u16 w/h），否則 BITMAPINFOHEADER/V4/V5（i32 w/h，取
  `unsigned_abs` 容忍 top-down 負高度）；bit count ≥32 → 4 channels，否則 3。
- `probe_webp`：12-byte RIFF 容器後讀 chunk fourcc；`VP8 `（有損）取 keyframe
  的 14-bit w/h（3 channels）；`VP8L`（無損）取 signature 0x2f 後 4-byte 打包的
  width-1/height-1 與 alpha bit（有 alpha→4，否則 3）；`VP8X`（延伸）取 3-byte
  canvas width-1/height-1 與 flags 的 alpha bit（0x10）。三者 bit_depth 均 8。

記憶體額度只用 w/h/channels（`batch.rs::source_file_bytes`），三格式皆回報非零
正確值，不退化為 0。

### 其他改動

- `texproc/Cargo.toml`：image features 加 `"tga","bmp","webp"`（無新增
  `[dependencies]` 條目；`image-webp`/`quick-error` 為 webp feature 的傳遞依賴，
  已更新 Cargo.lock）。
- `texproc/src/grouping.rs`：`SUPPORTED_EXTENSIONS` 加 `"tga","bmp","webp"`。
- GUI：`texproc-gui/src/main.rs` 的 `IMAGE_FILTER` 與 `texproc-gui/src/lib.rs`
  的 `RELATED_IMAGE_EXTENSIONS`（Add Related 兄弟掃描）各加三副檔名。

### 新增測試清單

`texproc/src/io.rs`：
- `decode_tga_rle_and_uncompressed_match_png`（錨點 1：RLE 用預設編碼、非 RLE
  用 `TgaEncoder::disable_rle()`，皆與同內容 PNG 逐像素相等）
- `decode_bmp_matches_png`（錨點 1）
- `decode_webp_lossless_matches_png_and_lossy_decodes`（錨點 1：無損逐像素比對
  RGB planes；有損用內嵌 4x4 真實 VP8 fixture 僅驗可解）
- `probe_header_reports_dimensions_for_new_formats`（錨點 2：TGA 24-bit→3ch、
  BMP 32-bit→4ch、WebP 無損→3ch，w/h 皆 7x5）

`texproc/src/batch.rs`：
- `mixed_suffix_source_formats_scan_into_one_group_and_process`（錨點 3：
  `Mat_basecolor.png` + `Mat_normal.tga` + `Mat_ao.bmp` + `Mat_roughness.webp`
  掃成 ONE group、四槽齊全，process 出 `Mat_diff.tif` + `Mat_ddna.tif`）

### 驗證

- `cargo test -p texproc --release`：65 passed（含上列 5 個新測試）。
- `cargo test -p texproc-gui --release`：24 passed / 6 ignored（GUI 不在 gates 內，
  自行執行）。
- `.\run_gates.ps1`：ALL GATES PASSED（含真實 RC 的 optional smoke；既有 golden
  零影響）。

## 審查紀錄（2026-07-28，協調者）

- 獨立重跑：texproc 65 測試、texproc-gui 35 測試（閘門不含 GUI，另跑）、
  `run_gates.ps1` 全綠（含 real-RC smoke），既有 golden 零影響。
- 程式碼審：probe 判定順序正確（PNG/JPEG/TIFF/EXR magic 優先 → BM/RIFF-WEBP
  → TGA 副檔名墊底，誤命名 .tga 的 PNG 仍由 magic 正確判型）；VP8/VP8L/VP8X
  尺寸解析對照格式規格無誤；BMP CORE/INFO 雙 header 變體均有處理。
- 偏差接受：lossy WebP 測試用內嵌真 VP8 fixture（image-webp 只能編 lossless，
  合理）；`RELATED_IMAGE_EXTENSIONS` 順帶收編三格式（其註解本就要求鏡射
  texproc 支援集，一致性修正）。
- 記錄在案（不擋票）：`RELATED_IMAGE_EXTENSIONS` 含 exr 但不含 hdr（exr 為
  既有條目）；T-015 後兩者同為 passthrough，Add-Related 對 hdr 兄弟檔不拉取
  ——行為不一致但影響極小，遇實際需求再補。
