# T-009 (T1) — texproc f32 核心 + OP-* 原語 + IO

狀態：OPEN
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
