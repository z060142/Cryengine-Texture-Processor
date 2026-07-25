# T-B01 (Backlog) — `--preserve-mtl-textures`：以既有 MTL 為貼圖佈局權威

狀態：DONE（2026-07-25 審查通過：完整 gate 獨立實跑全綠；T-B01 native smoke 17/17 preserved 零差異、合成 golden 維持無旗標（保鮮條款機器化成立）、--help 契約同步、未復用 overrides 的 source_mtl 欄位）
出處：T-005 審查退回的 `source_mtl` authoritative 通道——想法收貨、時機退回。實作可自 T-005 首版撿回：`git show 74eab90^:rebuild/converter/src/mtl.rs` 的 native MTL parser 與貼圖覆蓋段。

## 補充約束（排程時追加）

- CLI 契約已凍結（T-006）：新增 `--preserve-mtl-textures <ref.mtl>` 旗標屬契約變更，本票即為其開票程序；回報時把更新後的 convert 契約列表附上，`--help` 同步。
- 完成後 `run_gates.ps1` 追加一段 smoke：帶旗標對 car + `fixtures/car/car-reference.mtl`（native），貼圖段逐值相等；**合成 golden 段維持不帶旗標**（保鮮條款的機器化）。
- 診斷欄位 `texture_source: synthesized | preserved_from_ref` 進 convert 的材質診斷輸出。

## 動機

- native/手調 MTL 的貼圖決策（共享 normal、刻意省略 map、手工路徑）無法從 FBX 推導。
- 迭代重匯場景：美術改模重跑 converter，不應丟失 Sandbox 手調過的貼圖配置。

## 形狀

- `converter convert ... --preserve-mtl-textures <ref.mtl>`：顯式旗標，預設不啟用。
  不復用 overrides JSON 的 `source_mtl` 欄位——那是 provenance 記錄，不是行為開關。
- 語意：ref.mtl 中**按材質名**匹配到的子材質，其 `<Textures>` 整段為權威；
  未匹配的材質走正常合成。匹配不到的 ref 材質列入診斷（warning，不失敗）。
- 診斷輸出記錄每個材質的貼圖來源（`synthesized` / `preserved_from_ref`）。

## 驗收

- 專屬測試：合成 golden（car-generated-reference.mtl）**不使用**本旗標且維持綠——
  保鮮條款：本功能永不參與行為等價 golden。
- 帶旗標對 car + native reference：貼圖段與 native 逐值相等（= T-005 首版已證明的能力）。
- 名稱不匹配、ref 缺 Textures 段等邊界各一測試。

## 完成紀錄（2026-07-25）

- `converter convert` 新契約：
  `converter convert <INPUT> [--manifest <MANIFEST>] [--overrides <OVERRIDES>] [--texture-dir <TEXTURE_DIR>] [--preserve-mtl-textures <REF_MTL>] --out-dir <OUT_DIR>`。
  `--help` 已同步，reference MTL 不存在時沿用 CLI 輸入錯誤 exit code `2`。
- 本功能只由顯式 `--preserve-mtl-textures` 啟用；未復用 overrides JSON 的 `source_mtl`。
- ref 子材質按名稱精確匹配：
  - 有 `<Textures>`（包含顯式空段）時整段採用 reference，診斷為 `preserved_from_ref`。
  - output 未匹配時維持正常合成，診斷為 `synthesized`。
  - ref 未匹配 output 時輸出 warning；已匹配但缺 `<Textures>` 時安全回退合成並輸出 warning。
- convert JSON stdout 新增 `material_diagnostics`，每個 output 材質都有
  `texture_source: synthesized | preserved_from_ref`；ref-only warning 的 `texture_source` 為 `null`。
- `run_gates.ps1` 保留原 T-005 合成 golden 的無旗標路徑，另加 T-B01 native car smoke。
  `tools/compare_mtl_textures.py` 依材質名比較 `<Textures>`：
  `17/17` preserved、`17` 段逐值相等、`0` mismatch、`0` warning。
- 專屬邊界測試涵蓋共享 normal/TexMod、顯式空 `<Textures>`、缺 `<Textures>` 回退、
  output/ref 名稱不匹配與 ref-only warning。

## 驗證證據

- `cargo fmt --all -- --check`：PASS。
- `cargo clippy -p converter --all-targets --release --locked -- -D warnings`：PASS。
- `run_gates.ps1 -SkipRC`：PASS。
- `run_gates.ps1`：PASS。
  - Rust：`ce_schema 5`、`converter 39`、converter CLI `7`、`texproc 46`、
    fixture comparison `2`、texproc CLI `4`。
  - Python：asset flow `28 passed, 2 skipped`；RC policy `6 passed`。
  - converter RC：return code `0`、CGF exists、material alignment `16/16`、
    placeholder/schema gate PASS。
  - texproc RC/DDS：TIFF→DDS `8/8`、DDNA alpha `2/2`。
