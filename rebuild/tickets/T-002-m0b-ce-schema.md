# T-002 (M0b) — ce-schema crate

狀態：DONE（2026-07-25 審查通過：5 測試綠、凍結檔位元相同、suffix 委派鏈與 Python 逐 key 等價。已接受差異：未知 key 回 "" 而非 Python 的 _{key}。備註：票面 DoD 的七 key 清單漏了 opacity/roughness，Fox 依 Python 源碼補齊，正確）
上游文件：`rebuild/rust-workspace-design.md`（D-11）、`fbx-converter-migration.md` §2.1

## 前置閱讀（動手前必讀）

1. `docs/converter_schema.json` — 要嵌入的資料本體。
2. `output_formats/texture_output_paths.py` — 後綴解析委派鏈、`_ddna`/`_ddn` 特例、`OUTPUT_TEXTURE_TYPE_BY_KEY`。
3. `output_formats/cryengine_mtl_schema.py` — CE map 型別表、accepted suffixes、texmod/genmask、`resolve_ce_texture_map`。
4. `tests/` 內 `test_texture_output_paths*`、`test_cryengine_mtl_schema*` — 要移植的斷言。

## 工作內容

1. 凍結 `docs/converter_schema.json` 一份到 `ce-schema/data/converter_schema.json`（原樣複製，不重排鍵）。
2. `include_str!` + serde 解析，`std::sync::LazyLock` 快取為型別化結構。schema 結構用 serde struct 建模；**未用到的區塊可以先用 `serde_json::Value` 佔位**，不要為了完整建模而膨脹——這個 crate 只服務兩個 binary 實際會查的表。
3. 對外 API（最小集）：
   - `texture_suffix(output_key: &str, normal_has_alpha: bool) -> &'static str` — 委派鏈 + `_ddna`/`_ddn` 特例；emissive 必須回 `_em`。
   - CE texture map 型別查詢（texture_type → ce_map_type / exported / expected_suffix / accepted_suffixes）。
   - 支援的 RC 來源副檔名清單。
   - genmask / texmod 表的唯讀存取（形狀先照 JSON，夠 converter 查即可）。
4. 移除 T-001 的 `Placeholder`。
5. 測試：
   - 一致性測試：`include_str!` 的內容 == 讀取 `../docs/converter_schema.json`（路徑用相對於 workspace 的 `../docs/...`；若 CI 環境拿不到 repo 根則 `#[ignore]` 併註明）。
   - 從 Python 測試移植純表格斷言（suffix 委派鏈、`_em`、`_ddna`/`_ddn`、accepted suffixes）。挑「斷言資料表內容」的部分移植；斷言 Python 函式行為細節（dict 形狀之類）的不移植。

## 明確禁止

- 不新增依賴。
- 不做 schema 版本協商、不做多版本支援、不做 builder——查表 crate 就是查表。
- 不順手實作 texproc/converter 側的任何邏輯。

## DoD

- `cargo test -p ce-schema` 全綠。
- 一致性測試存在且通過。
- `texture_suffix` 對規格中每個 output key 都有測試覆蓋（diff/spec/ddna/ddn/displ/em/sss）。
- 回報：API 清單（pub fn 簽名）、移植了哪些 Python 測試斷言、放棄了哪些並說明原因。
