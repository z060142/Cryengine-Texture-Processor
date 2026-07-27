# T-014 — Metal Gate（金屬轉換終止線）

狀態：OPEN
上游文件：`rebuild/metal-gate-design.md`（全文為權威規格，§4 為 PBR 定錨閾值）

## 工作內容

1. **texproc INT 層**：per-pixel `M_eff` 遮罩（design §2 判定式），替換
   INT-ALBEDO 變黑因子與 INT-REFLECTION lerp 因子（design §3）；gloss 不動。
   C3 的 s* 在 linear 域算 luma（沿用 DEF-08 island 的 decode）。
2. **設定鍵**：`metal_gate`（預設 on）、`metal_gate_metallic_cut`（0.5）、
   `metal_gate_spec_min`（180/255）、`metal_gate_gloss_cut`（0.0=off）、
   `metal_gate_transition`（0.05；0=硬切）。settings JSON + GUI Advanced
   區塊各加對應控件（GUI 僅曝露，不做新面板）。
3. **swatch atlas 生成器**：`texproc swatch --out DIR`？不——CLI 契約凍結。
   做成 `tools/generate_metal_swatch.py`（stdlib+可用 uv 環境的 Pillow？
   不，避免依賴問題：直接用 Rust `#[ignore]` 測試或 texproc-gui 附帶的
   dev 功能皆嫌重——**用最小 Rust example**：`texproc/examples/metal_swatch.rs`
   （cargo example 不進 CLI 契約），生成 basecolor/metallic/roughness 三張
   輸入 PNG（橫軸 metallic 0→1、縱軸 roughness 1→0、四行 basecolor：
   白 240/鐵灰 196/金 (255,219,145)/鏽橘 (137,72,42)），跑管線出
   _diff/_spec/_ddna，存到指定目錄供業主進引擎。
4. **驗收錨點**（design §5 全部）：死區掃描測試、鏽案例逐像素等於介電質
   路徑、`metal_gate=off` 位元相容（現行 golden/錨點不受影響的機制保證）。

## 明確禁止

- 不動 CLI 子命令/旗標（example 不算）。不新增依賴。
- gate 預設 on，但**錨點 7 直通比對與既有 golden 跑的設定必須顯式
  `metal_gate=off`**……不對——直通案例 `process_metallic=false` 本就不走
  金屬路徑，不受影響；受影響的是 metallic 路徑的既有測試（DEF-05/08 測試）：
  這些測試改為顯式 `metal_gate=off` 驗原始行為，另加 gate=on 的新測試組。

## DoD

- 上述測試全綠；`run_gates.ps1 -SkipRC` 全綠（golden 零影響）。
- swatch atlas 產物路徑貼回報，交業主引擎目測（G_cut 是否啟用據此裁決）。
- 回報：M_eff 實作位置、各測試對照 design §5 清單。
