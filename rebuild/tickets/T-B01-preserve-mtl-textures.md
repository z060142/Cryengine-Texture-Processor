# T-B01 (Backlog) — `--preserve-mtl-textures`：以既有 MTL 為貼圖佈局權威

狀態：OPEN（2026-07-25 排程啟動；前置條件已全數滿足——T-005 合成 golden 穩定、主線完工）
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
