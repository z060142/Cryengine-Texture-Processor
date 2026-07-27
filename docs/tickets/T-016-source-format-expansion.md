# T-016 — 來源圖片型式擴充：TGA / BMP / WebP

狀態：OPEN（排隊中：T-015 觸及相同檔案，須等 T-015 驗收後派發）
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
