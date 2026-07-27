# CryEngine Texture Processor（v2）

[English](README.md)

將 PBR 貼圖組與 FBX 模型轉換為 CryEngine 可用資產。v2 為原 Python 工具的
Rust 全面重寫（原版凍結於 [`legacy/`](legacy/)）。

## 組成

| Crate | 功能 |
|---|---|
| `texproc` | CLI：掃描/分組貼圖，將 PBR（metallic/roughness）貼圖組轉換為 CryEngine `_diff` / `_spec` / `_ddna` / `_displ` TIF 輸出，並驅動 RC.exe 產出 DDS |
| `texproc-gui` | 工作台 GUI：貼圖分組審閱、批次轉換、FBX 導入、模型導出（`.mtl` + `.mtl.cryasset` + RC 轉換請求 JSON） |
| `converter` | CLI：FBX（ufbx）→ CryEngine `.mtl` + RC 導入請求 JSON、材質診斷 |
| `ce-schema` | 共用 CryEngine schema/policy 表（內嵌快照） |

所有執行檔皆為靜態連結（`+crt-static`，見 `.cargo/config.toml`），
產物位於 `target/release/`。

## 建置

```powershell
cargo build --release
```

需要 stable Rust（2021 edition），Windows（x86_64-pc-windows-msvc）。

## 驗收閘門

```powershell
.\run_gates.ps1          # 完整執行（找不到 RC.exe 時自動略過 RC smoke）
.\run_gates.ps1 -SkipRC  # 略過可選的 RC.exe smoke 測試
```

**只能在 PowerShell 執行** — Git Bash（MSYS）會改寫 `/` 開頭的引數
（JSON pointer、RC 旗標）導致閘門失效。需要 `cargo` 與 `uv`；閘門的
Python 端（golden 比對、E2E harness）位於 `legacy/`，經
`uv run --project legacy` 執行。

可選 RC smoke：設定 `CE_RC_EXE` 指向你的 `rc.exe`，或將 CRYENGINE 5.7 LTS
安裝於預設位置。

