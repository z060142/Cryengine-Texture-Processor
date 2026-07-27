# T-012 (T4) — texproc 分組引擎 + rayon 平行 + CLI 定形

狀態：DONE（2026-07-25 審查通過：gate 全綠含新 smoke 段；審查者獨立 scan KB3D 全目錄——132 groups、unknown 恰為 5 個 refraction 檔且全數歸因 DEF-17，無不可歸因差異；rayon 4 執行緒 3.2× 證據合理。備註：scan 接受目錄輸入，繞過 Windows 命令列長度限制）
上游文件：`rust-workspace-design.md` D-06（含 D-06.7 全部簽核裁決）、D-08；T-B02 的接口預留
前置：T-011。

## 工作內容

1. **分組引擎**（D-06 凍結行為 + D-06.7 裁決修正）：
   - 後綴表：預設嵌入 + `--suffixes` 覆蓋（JSON 形狀相容）；載入時正規化 separator（DEF-13 修）；單字母 `a/d` 為歧義後綴走 header probe 消歧（DEF-14 裁決）；CE 硬編碼層優先序明文化，自訂表衝突報錯（DEF-23 修）。
   - stem 清理：removable suffix 只從 terminal qualifier 區 peel（DEF-15 修）；base 提取只移除已命中 terminal span（DEF-22 修）。
   - group key：Windows-aware casefold + 保留首見拼寫（DEF-18 修）。
   - 衝突：warning + 面積大者勝（header probe），同面積後者勝（DEF-19 裁決）。
   - arm alias → channel order 對照 + 歧義 alias 診斷（DEF-16 裁決）；無像素猜測（DEF-17 裁決）。
   - 副檔名白名單 = decoder 實際能力（png/jpg/jpeg/tif/tiff/exr），其餘列 unknown + 診斷（DEF-20 修）。
2. **CLI**（D-08 + T-B02 接口）：
   - `scan [--suffixes s.json] [--out groups.json] INPUTS...`：輸出分組 JSON（含 unknown、診斷、header probe 結果）。
   - `process [--settings cfg.json] [--suffixes s.json] [--groups groups.json] --out DIR INPUTS...`：`--groups` 存在時吃預先確認的分組（T-B02 消費）；否則內部 scan。unknown-only group 預設 gate fail，`--allow-unknown` 放行（DEF-21 裁決）。
   - settings JSON 鍵 = 規格 §7 + `arm_order`/`sss_contrast`/`dither`；退出碼契約沿用 converter 的 0/1/2/3（3 = 分組 gate fail）。
3. **rayon**：跨 group 平行（規格 §9 parallelism：across_groups safe）；group 內 Stage 2 可平行但不強求。進度輸出到 stderr（每 group 一行）。
4. **批次對照**：對 `Z:\enchanted\KB3DTextures\4k` 全目錄跑 scan，分組結果與 Python 版（driver 腳本沿用 T-011 手法）對照——**分組差異只准來自 DEF-13..23 的簽核修正**，每筆差異標注對應 DEF 編號，其他差異即 bug。
5. CLI 契約表寫入本票（凍結基準，同 T-006 慣例）；`run_gates.ps1` 加 texproc scan/process smoke 段。

## 明確禁止

- 不做 GUI（T-B02）。不做 dither 實作。不新增依賴（rayon 已在 D-02 清單）。
- 分組對照差異不准用「修正」以外的理由豁免。

## DoD

- `cargo test -p texproc` 全綠；`run_gates.ps1 -SkipRC` 全綠（含新 smoke 段）。
- KB3D 全目錄 scan 對照報告：每筆差異 × DEF 編號表。
- CLI 契約表 + 退出碼入 `--help`；契約凍結。
- rayon 平行實測：全目錄 process 的 wall-clock 與單執行緒比一次，數字貼回報（不設門檻，只留證據）。

## CLI 契約（T-012 凍結）

| 子命令 | 語法 | stdout | stderr | 成功條件 |
|---|---|---|---|---|
| `scan` | `texproc scan [--suffixes s.json] [--out groups.json] INPUTS...` | 未指定 `--out` 時為完整分組 JSON | 無正常進度 | 所有輸入完成 deterministic scan；unknown 留在 JSON，不單獨令 scan 失敗 |
| `process`（內部 scan） | `texproc process [--settings cfg.json] [--suffixes s.json] [--allow-unknown] --out DIR INPUTS...` | 無 | 每 group 一行進度 + rayon 摘要 | 無 unknown-only group，或已顯式給 `--allow-unknown` |
| `process`（已確認分組） | `texproc process [--settings cfg.json] --groups groups.json [--allow-unknown] --out DIR` | 無 | 每 group 一行進度 + rayon 摘要 | groups JSON 可解析且通過同一 unknown-only gate |

`--groups` 與 `--suffixes` 互斥；使用 `--groups` 時不得再給位置輸入。settings
採嚴格鍵檢查，接受規格 §7 鍵與 `arm_order`、`sss_contrast`、`dither`，未知鍵
是 configuration error。退出碼已寫入頂層 `--help` 並由整合測試凍結：

| code | 契約 |
|---:|---|
| `0` | 成功 |
| `1` | runtime / I/O failure |
| `2` | CLI / configuration error |
| `3` | grouping gate failure |

## KB3D 全目錄對照（2026-07-25）

命令由 `tools/run_t012_grouping_comparison.py` 驅動 active Python
`TextureManager.classify_texture()` 與 release Rust `scan`，輸入為
`Z:\enchanted\KB3DTextures\4k`。共掃描 793 檔、Rust 產生 132 groups；
Rust scan wall-clock 6.065 秒。差異 5、非預期差異 0：

| 檔名 | Python | Rust | 簽核差異 |
|---|---|---|---|
| `KB3D_ENC_GlassClean_refraction.png` | glossiness | unknown | DEF-17：移除像素猜測 |
| `KB3D_ENC_GlassDirty_refraction.png` | glossiness | unknown | DEF-17：移除像素猜測 |
| `KB3D_ENC_StainedGlassGreen_refraction.png` | specular | unknown | DEF-17：移除像素猜測 |
| `KB3D_ENC_StainedGlassMulti_refraction.png` | specular | unknown | DEF-17：移除像素猜測 |
| `KB3D_ENC_Water_refraction.png` | roughness | unknown | DEF-17：移除像素猜測 |

## Rayon 實測（2026-07-25）

相同 release binary、相同 132-group JSON、相同 DDNA-only 64px settings
（`texproc/tests/t012-benchmark-settings.json`），只改
`RAYON_NUM_THREADS`。兩次各產生 127 個 TIFF，檔名集合差異為 0。

| 模式 | wall-clock | 輸出 | 相對單執行緒 |
|---|---:|---:|---:|
| `RAYON_NUM_THREADS=1` | 281.783 秒 | 127 | 1.000× |
| `RAYON_NUM_THREADS=4` | 88.097 秒 | 127 | 3.199× |

## 驗證紀錄

- `cargo test -p texproc --release --locked`：46 unit + 2 T-011 fixture +
  4 T-012 CLI integration，全部通過。
- `cargo clippy -p texproc --all-targets --release --locked -- -D warnings`：通過。
- `run_gates.ps1 -SkipRC`：`ALL GATES PASSED`，包含 T-012 生成 PNG、
  `scan --out`、`process --groups` 與四個 CE TIFF 輸出檢查。
