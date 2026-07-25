# T-012 (T4) — texproc 分組引擎 + rayon 平行 + CLI 定形

狀態：OPEN
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
