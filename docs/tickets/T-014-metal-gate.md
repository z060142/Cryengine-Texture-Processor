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

## 實作紀錄（2026-07-27）

狀態：DONE（待業主 swatch 目測裁決 G_cut）。

### M_eff 實作位置
- `texproc/src/pipeline.rs`
  - `MetalGate`（新型別，含 `enabled/metallic_cut/spec_min/gloss_cut/transition`；
    `Default` = on / 0.5 / 180-255 / 0(off) / 0.05）；掛進 `IntermediateSettings.metal_gate`。
  - `metal_gate_factor()`：`M_eff = T(C1)·T(C2)·T(C3)`（見下 erratum），`gate_step()`
    為 smoothstep（半寬 0；硬切走 `value ≥ cut`）。C2 於 `gloss_cut ≤ 0` 整條略過。
  - `linear_luma()`：C3 的 s\* = basecolor 於 **linear 域**算 luma（沿用 DEF-08
    的 `srgb_decode` + `LUMA_WEIGHTS`）。
  - `effective_metallic()`：逐像素產生單通道 M_eff 遮罩；`enabled=false` 直接回
    `gray(metallic)`（位元相容錨點）。
  - 兩個消費點：`process_albedo()`（INT-ALBEDO 變黑，`invert(mask)`→`linear_burn`）
    與 `metal_reflection()`（INT-REFLECTION lerp 因子）。gloss 只讀不改；albedo
    在 gloss step 之前，故 `gate_gloss()` 於需要時（`gloss_cut>0`）就地 `process_gloss`。
- `texproc/src/output.rs`：`TextureSettings` 增 5 個扁平鍵 + `Default` +
  `intermediate_settings()` 組成 `MetalGate`。
- `texproc/src/settings.rs`：strict-key 解析/序列化各加 5 鍵。
- `texproc-gui/src/main.rs`：Advanced 區塊加「Metal Gate」勾選 + 4 個 DragValue
  （enabled 關閉時數值列 disabled）。英文標籤。

### 測試對照 design §5
- **gate off 位元相容**：DEF-05（`def05_albedo_priority…`）、DEF-08
  （`def08_reflection_…`）改用 `run_with(…, &gate_off())`，逐位元通過；
  t011 `produce_rust_metallic_sample` 顯式 `metal_gate:false` 保留 DEF-05 錨點原義。
- **§5(c) M_eff 純函數**：`metal_gate_factor_cuts_transitions_and_toggles`
  — C1/C3 切點、smoothstep 中點、C2 預設停用/啟用、硬切 w=0、disabled 回原值。
- **§5 鏽案例**：`metal_gate_rust_basecolor_stays_dielectric`
  — basecolor (137,72,42)+metallic=1、gate 預設 on → albedo 不動、spec=gray62（逐像素）。
- **§5(a) 死區掃描**：`metal_gate_sweep_confines_dead_zone_to_transition_band`
  — metallic∈{0,1}（PBR 正規化二值，見下 deviation）×gloss×basecolor 掃描，
    重演兩消費點；斷言死區像素必落在過渡帶（近 M_cut 或 S_min ±w），帶占比 ≤ 理論界。

### swatch atlas 產物（gitignored `rebuild/fixtures/metal-swatch/`）
`cargo run -p texproc --release --example metal_swatch`（從 `rebuild/` 執行；
argv[1] 可指定輸出目錄）。512×2048 atlas：X=metallic 0→1（8 格）、Y=roughness 1→0
（8 列）、四行 basecolor（白240/鐵灰196/金255,219,145/鏽137,72,42）。gate on/off 各三張：
- `metal_swatch_on_diff.tif/.png`、`metal_swatch_on_spec.tif/.png`、`metal_swatch_on_ddna.tif/.png`
- `metal_swatch_off_diff.tif/.png`、`metal_swatch_off_spec.tif/.png`、`metal_swatch_off_ddna.tif/.png`
（diff/spec on≠off；ddna on==off——gate 不碰 normal/gloss，符合預期。）

### erratum（2026-07-27，公式修正）
- 初版依 design §2 舊式 `M_eff = m × ∏T` 實作，並旗標「中間值 metallic 留半轉換殘影」
  為疑點。經協調者確認**該 m 前導因子是 reviewer 的 bug**：design §2 已更正（已提交）為
  `M_eff = T(C1) × T(C2) × T(C3)`，metallic **只**經 C1 的 smoothstep 進入 → 真二值化：
  通過像素 M_eff≈1（全量轉換）、不通過 0；m=0.7 這類中間值現在**全轉**而非 70%。
- 已據此更新 `metal_gate_factor()`（去掉前導 m）；`enabled=false` 路徑不變（仍回
  `gray(metallic)`，位元相容）。純函數測試期望值同步（cut 中點 0.5、硬切通過→1.0）；
  死區掃描改為**連續 metallic**掃描（0..1 64 級 + cut±w 邊值，涵蓋核心 m=0.5±0.3），
  斷言 snap 語意下非過渡帶像素必落全金屬/全介電、死區僅限過渡帶。swatch atlas gate-on
  組已重生成。

### 其他
- debug target 樹曾有一個 locked/損壞的 `quote` build-script 目錄（疑似先前中斷的建置 +
  殘留 texproc-gui 行程）；已 kill 行程並清 `target/debug/build/quote-*`，release 全綠。
