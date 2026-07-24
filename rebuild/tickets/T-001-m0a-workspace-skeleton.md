# T-001 (M0a) — Rust workspace 骨架

狀態：DONE（2026-07-25 審查通過：build/test 綠、CLI 骨架正確、exe 僅依賴系統 DLL 無 vcruntime、ufbx vendored C 於 MSVC 編譯成功）
上游文件：`rebuild/rust-workspace-design.md`（D-01、D-02）

## 目標

在 `rebuild/` 建立可編譯、可執行的三 crate workspace 空殼。不寫任何業務邏輯。

## 工作內容

1. `rebuild/Cargo.toml`：workspace，members = `ce-schema`, `texproc`, `converter`。
2. `rebuild/.cargo/config.toml`：
   ```toml
   [target.x86_64-pc-windows-msvc]
   rustflags = ["-C", "target-feature=+crt-static"]
   ```
3. `ce-schema/`：lib crate，依賴 `serde`（derive）、`serde_json`。內容只放一個 placeholder 型別 + 一個測試。
4. `texproc/`：bin crate，依賴 `image`（features: png, jpeg, tiff, exr）、`tiff`、`rayon`、`clap`（derive）、`serde`、`serde_json`、`ce-schema`（path）。main 只做 clap 骨架：`scan` / `process` 兩個子命令，執行時印 "not implemented" 退出碼 2。
5. `converter/`：bin crate，依賴 `ufbx`（crates.io）、`quick-xml`、`clap`（derive）、`serde`、`serde_json`、`ce-schema`（path）。main 做 `dump` / `convert` / `validate` 三個子命令骨架，同樣 not implemented。
6. `rebuild/fixtures/` 目錄 + `.gitignore`（先忽略 `*.fbx` 與貼圖，等 Q3 裁決）。
7. Edition 2021。版本號全部 0.1.0。依賴版本用當下最新 stable，寫死 minor（如 `image = "0.25"`）。

## 明確禁止

- 不新增設計文件 D-02 清單以外的任何依賴。
- 不建業務 module、不放 trait、不放 config 檔。空殼就是空殼。

## DoD

- `cargo build --release` 全綠；`cargo test` 全綠。
- `texproc --help`、`converter --help` 正常輸出子命令列表。
- 兩個 release exe 用 `dumpbin /dependents` 檢查：除 Windows 系統 DLL（kernel32 等）外無其他依賴（特別是無 vcruntime/msvcp）。把 dumpbin 輸出貼在回報裡。
- `converter` 能成功編譯 ufbx 的 vendored C（這是本票真正要驗的東西——build.rs 在 MSVC 環境下能不能過）。

## 回報格式

- 指令輸出：build / test / dumpbin。
- 若 ufbx crate 編譯失敗，停下回報錯誤全文，不要自行換 crate 或改用動態連結。
