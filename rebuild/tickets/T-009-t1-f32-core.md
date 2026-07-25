# T-009 (T1) — texproc f32 核心 + OP-* 原語 + IO

狀態：DONE（2026-07-25 審查通過：gate 全綠 24/24、原語抽查對規格（linear_burn/darker_color/copy_opacity/resize 單向性）、header probe 截斷檔驗證屬實、依賴零變更）
上游文件：`texture-pipeline-spec.md` §6（OP-* 定義）、§9 `constants`；`rust-workspace-design.md` D-02/D-03/D-05/D-06（含 D-06.7 簽核）/D-07
前置：D-06 已簽核，T1 放行。

## 工作內容

1. **核心型別**：planar f32 影像（`w/h` + 每通道 `Vec<f32>`，值域 0–1，encoded domain 照 D-03）。
2. **輸入解碼**（image crate）：png/jpeg/tif/exr；8/16-bit 整數正規化到 0–1；EXR 直接吃 f32。解碼失敗回 error，不猜。
3. **header probe**（D-06.7 / DEF-14、DEF-19 消費）：`probe_header(path) -> {channels, bit_depth, width, height}`，只讀 metadata 不解碼像素。png/tiff/exr/jpeg 四格式。
4. **OP-\* 原語**（規格 §6 全部 13 個）：invert、gray(BT.601)、linearburn、darken、darkercolor、multiply、copyopacity、flipg、resize（Lanczos3、只縮不放、D-07）、autolevel、evalmul、normalfromheight（Sobel）、colorize。
   - sRGB decode/encode helper（D-03 linear island 用，T2/T3 消費；本票只做函式+測試）。
5. **輸出編碼**：`tiff` crate、8-bit、LZW；量化 `(x*255).round()` clamp（D-05）；RGBA/RGB/gray 依通道數。dither 本票不做（T3 再議，預設 off）。
6. **常數 module**：gray62、sss 色、luma 權重等（規格 §9 constants），單一定義點。

## 測試（DoD 核心）

- 每個 OP-* 單元測試含邊界（0、1、clamp、極小圖 1×1）。
- round-trip：u8 → f32 → u8 恆等（全 256 值）。
- 16-bit TIFF 與 EXR 解碼各一測試（fixtures 可用 ImageMagick 生成的探針圖，比照 T-008 手法；生成腳本入 repo，產物不入）。
- header probe：對 png/tif/exr/jpeg 各驗 channels/depth/尺寸，並驗「探測不開像素」（截斷檔案只留 header 仍可 probe）。
- sRGB decode/encode round-trip 誤差 ≤ 1e-6（f32 域）。
- resize 單向性：小圖不放大（規格 §10 錨點 5 的基礎）。

## 明確禁止

- 不做 INT-*/OUT-* 編排（T2/T3）。
- 不新增 D-02 以外依賴。
- 不做 CLI 子命令實作（scan/process 仍 not-implemented；T4 定形）。

## DoD

- `cargo test -p texproc` 全綠；`run_gates.ps1 -SkipRC` 全綠（converter 線無 regression）。
- OP-* 覆蓋清單對照規格 §6 逐一打勾，貼回報。
- clippy/fmt 過。

## 執行結果（2026-07-25）

### 實作

- 新增 `texproc` library target，CLI `main.rs` 保持原本
  `scan/process -> not implemented`，沒有開始 T4。
- `PlanarImage`：
  - public `width` / `height` / `planes: Vec<Vec<f32>>`。
  - 1–4 channel、非零尺寸、每 plane 等長、sample finite 且位於 0–1。
  - u8 / u16 / f32 interleaved 輸入轉 planar；EXR f32 不經整數量化，
    HDR 超出 0–1 的 sample 依核心 invariant clamp。
  - 量化固定 `(x * 255).round()` + clamp。
- `decode_image()`：
  - 只接受由 magic 判定的 PNG/JPEG/TIFF/OpenEXR。
  - u8 除以 255、u16 除以 65535、EXR RGB/RGBA f32 直接進 planar。
  - 解碼失敗回 error；沒有 Python 的像素猜型別 fallback。
- `probe_header()` 是獨立 metadata parser，不呼叫 image decode：
  - PNG：signature + IHDR。
  - JPEG：掃 marker 到 SOF。
  - classic TIFF：byte order + IFD 的 Width/Length/BitsPerSample/
    SamplesPerPixel tags。
  - OpenEXR：magic + `channels` chlist + `dataWindow`。
  - 四格式都以「只有完整 metadata header、沒有 pixel payload」的截斷檔測過。
- `write_tiff_lzw()`：
  - `tiff` crate 直接指定 `Compression::Lzw`。
  - gray/RGB/RGBA 依 1/3/4 channel 寫 8-bit；2-channel 明確回 error，
    不偷偷改 channel layout。
- `constants` 單點定義規格 §9 的 gray62、default SSS、
  SSS colorize white、1024×1024、BT.601 luma weights。
- sRGB decode/encode helper 使用標準 piecewise transfer function；本票沒有把
  transfer function 套到任何一般 OP，也沒有實作 dither。

沒有新增 D-02 以外依賴；`Cargo.toml` / `Cargo.lock` 均未改。

### OP-* 覆蓋清單

| 規格原語 | Rust API | 邊界/1×1 測試 |
|---|---|---:|
| ✅ `OP-INVERT` | `invert` | ✅ |
| ✅ `OP-GRAY` | `gray`（BT.601） | ✅ |
| ✅ `OP-LINEARBURN` | `linear_burn` | ✅ |
| ✅ `OP-DARKEN` | `darken` | ✅ |
| ✅ `OP-DARKERCOLOR` | `darker_color` | ✅ |
| ✅ `OP-MULTIPLY` | `multiply` | ✅ |
| ✅ `OP-COPYOPACITY` | `copy_opacity` | ✅ |
| ✅ `OP-FLIPG` | `flip_green` | ✅ |
| ✅ `OP-RESIZE` | `resize`（Lanczos3、只縮不放） | ✅ |
| ✅ `OP-AUTOLEVEL` | `auto_level` | ✅ |
| ✅ `OP-EVALMUL` | `eval_mul` | ✅ |
| ✅ `OP-NORMALFROMHEIGHT` | `normal_from_height`（Sobel） | ✅ |
| ✅ `OP-COLORIZE` | `colorize` | ✅ |

二元逐通道 OP 允許單 channel map broadcast 到 RGB/RGBA，尺寸不同或非
single-channel 的 channel mismatch 回 error。`COPYOPACITY` 對 RGB/gray
增加 alpha plane，對 RGBA/GA 替換既有 alpha plane。

### IO probes

repo 內新增生成腳本，產物只寫到呼叫者指定目錄、不入版控：

```powershell
.\texproc\tests\generate_io_probes.ps1 `
  -OutputDirectory (Join-Path $env:TEMP 't009-texproc-io-probes-final')
```

本機 ImageMagick 7.1.1-8 Q16-HDRI 實跑：

```text
probe_gray16.tif  width=2 height=2 depth=16 channels=gray  1.0
probe_rgba16.exr width=2 height=2 depth=16 channels=rgba 4.0
```

Rust tests另直接生成/解碼 16-bit TIFF 與 RGB32F EXR，驗證 u16 正規化、
f32 不經 integer quantization，並驗 PNG/JPEG u8 decode。

### 驗證

```text
cargo test -p texproc --release --locked
  24 passed, 0 failed

cargo clippy -p texproc --all-targets --release --locked -- -D warnings
  PASS

cargo fmt --all -- --check
  PASS

.\run_gates.ps1 -SkipRC
  ce-schema:       5/5
  converter:      38/38
  CLI contract:    5/5
  texproc:        24/24
  asset_flow:     28 passed / 2 skipped
  RC policy:       3/3
  T-003/T-004/T-005 goldens: PASS
  ALL GATES PASSED
```

補充：不帶 `--release` 的本機 debug build 在建立/複製既有 dependency
`quote` 的 `build-script-build.exe` 時被 Windows 拒絕
（`os error 5` / `LNK1104`）；repo target 與獨立 TEMP target 都同樣發生，
且無殘留 cargo/rustc process。這發生在 texproc 編譯前。相同程式碼的 release
test、release clippy 與統一 gate 均能重新編譯並全綠，因此未修改程式或 target
目錄去掩蓋環境層 executable lock。
