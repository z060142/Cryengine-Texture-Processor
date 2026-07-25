# T-B01 (Backlog) — `--preserve-mtl-textures`：以既有 MTL 為貼圖佈局權威

狀態：BACKLOG（排 C5 之後；前置條件 = T-005 重開完成，貼圖合成邏輯有自己的 golden）
出處：T-005 審查退回的 `source_mtl` authoritative 通道——想法收貨、時機退回。實作可自 T-005 首版（commit `74eab90` 前的 mtl.rs）撿回。

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
