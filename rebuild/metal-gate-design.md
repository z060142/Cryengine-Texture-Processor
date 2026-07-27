# 研究案：金屬轉換終止線（Metal Gate）

> 2026-07-27。動機：業主目測 CE Illum 在 **diffuse 亮度 > 20、specular 亮度 < 220、
> gloss < 0.9 任一成立**時完全失去金屬視覺。metallic→spec/gloss 轉換若把像素
> 送進這個「死區」，結果比不轉換更糟。素材端病因：金屬度用中間值、鏽面標金屬。

## 1. 問題的幾何形狀

轉換路徑是連續的：metallic 0→1 時，diffuse 從原色**連續變黑**、spec 從 gray62
**連續變亮**。死區恰好橫在路徑中段——**任何連續過渡都必然穿過死區**。這是本案
最重要的結構性事實，決定了設計只能二選一：

- **硬切（per-pixel 二值化）**：每個像素判定「能不能到達金屬視覺區」，能就
  轉好轉滿（metallic 視為 1），不能就完全不轉（視為 0）。死區零暴露；代價是
  metallic 漸層處出現空間硬邊。
- **窄過渡帶**：條件邊界附近留一條很窄的 smoothstep 帶。死區暴露被壓縮成
  細線（視覺上讀作邊緣磨損/交界，通常可接受）；代價是帶內像素仍在死區。

建議：**預設窄過渡帶（寬度可調，設 0 即硬切）**，兩者都是同一實作的參數。

## 2. 終止線的三個條件（gate 判定式）

對每個像素，在 INT-ALBEDO / INT-REFLECTION 之前先算 **有效金屬度 M_eff**：

```
m  = metallic 取樣            (0–1)
g  = INT-GLOSS 輸出的 gloss    (0–1)          ← 預測「轉換後」的 gloss
s* = luma(basecolor)（linear 域）              ← 預測「轉換後」的 spec 亮度
                                                （metallic=1 時 spec = basecolor）

gate 條件（全部成立才金屬化）：
  C1  m  ≥ M_cut                預設 0.5     金屬度太低者不轉
  C2  g  ≥ G_cut                預設 0.90⚖   gloss 不足 → 轉了也是死區
  C3  s* ≥ S_min                預設 220/255⚖ 預測 spec 太暗 → 轉了也是死區

M_eff = m × T(C1) × T(C2) × T(C3)
  T(Ci) = smoothstep(cut−w, cut+w, value)；w = 過渡半寬，預設 0.05，0 = 硬切
```

**C3 就是鏽的解**：鏽面即使被標 metallic=1，其 basecolor 暗（橘褐 ~0.3），
預測 spec 亮度遠低於 S_min → 自動不金屬化 → 保留原 albedo 走介電質——
正是「鐵鏽不該是金屬」的期望行為，不需要任何人工標注。

**diffuse < 20 不是輸入條件而是驗證目標**：通過 gate 的像素做**全量**變黑
（M_eff≈1 → diffuse→0，必然 < 20）；不通過的完全不變黑（保持原色）。
「變黑到一半」只存在於過渡帶，帶寬即死區暴露上限——這回答了
「diffuse 在哪個情況停止變黑」：**答案是二值化，不是找一個變黑程度的中點**。

## 3. 三條規則的消費點

| 管線點 | 現行（DEF-05/08 修正後） | 加 gate 後 |
|---|---|---|
| INT-ALBEDO 金屬變黑 | `max(0, albedo − metallic_gray)` | metallic_gray 換成 **M_eff** |
| INT-REFLECTION | `lerp(gray62, basecolor, metallic)`（linear） | lerp 因子換成 **M_eff** |
| gloss | 不動 | 不動（gate 只讀 gloss 不改；「gloss 不足就補高」屬造假資料，不做） |

實作全在 INT 層記憶體內 f32，逐像素乘加，成本可忽略；設定鍵：
`metal_gate`（bool，預設 on）、`metal_gate_metallic_cut`、`metal_gate_gloss_cut`、
`metal_gate_spec_min`、`metal_gate_transition`（0=硬切）。

## 4. 需要業主校準的兩個數字 ⚖

你的目測值我照單全收為預設，但有兩處與物理 F0 有張力，建議實測校準：

1. **S_min = 220**：真實金屬的 F0 亮度——鐵 ≈195、金 ≈204、鋁 ≈245（8-bit
   sRGB 概算）。S_min=220 會把鐵、金都判成「到不了金屬區」而不轉。
   若你的 220 來自特定測試材質，可能偏嚴；建議校準看 180–220 區間。
2. **G_cut = 0.90**：等效 roughness ≤ 0.1——拉絲金屬、磨損金屬（roughness
   0.3–0.6）將全部不金屬化。如果這正是你要的（CE Illum 反正撐不起粗金屬），
   維持 0.9；否則看 0.7–0.9。

**校準方法（建議做，半小時）**：產一張 swatch atlas——橫軸 metallic 0→1、
縱軸 gloss 0→1、多行不同 basecolor（白/鐵灰/金/鏽橘），經管線轉換出
_diff/_spec/_ddna，進引擎球體上目測，你圈出「金屬感存活區」的邊界，
數字就定案了。這張圖同時就是日後的迴歸驗收樣本。

## 5. 驗收錨點（進票時用）

- 合成掃描測試:任意輸入組合，輸出像素不得落在死區（diffuse>20 且被變暗、
  或 62<spec<S_min 的中間態），過渡帶像素占比 ≤ 帶寬理論值。
- 鏽案例：暗 basecolor + metallic=1 → 輸出 == 純介電質路徑（albedo 不動、
  spec=gray62），逐像素相等。
- gate off 時輸出與現行管線位元相同（預設相容開關）。
- swatch atlas 進引擎目測（業主簽核）。

## 6. 結論

可行，且結構簡單：一個 per-pixel 的 M_eff 遮罩替換兩處消費點的 metallic
因子。核心設計決定是「二值化 + 窄過渡」而非「找部分轉換的中點」——因為
死區在路徑中間，中點必死。三個閾值做成設定，預設用業主目測值，
S_min/G_cut 建議經 swatch 校準後定案。
