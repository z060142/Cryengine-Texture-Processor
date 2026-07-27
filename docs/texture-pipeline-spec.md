# CryEngine Texture Pipeline — 轉換邏輯規格

> 來源：`z060142/Cryengine-Texture-Processor` @ main
> 涵蓋範圍：`core/batch_processor.py`、`intermediate_formats/*`、`output_formats/{diff,spec,ddna,displ,emissive,sss}_exporter.py`
> 不涵蓋：UI 層、模型匯入（bpy）、mtl/json 匯出、RC.exe 呼叫

## 0. 讀法

每條規則有唯一 ID，可被人與 AI 精確引用：

| 前綴 | 含義 |
|---|---|
| `INT-*` | 中間層生成規則 |
| `OUT-*` | 輸出層匯出規則 |
| `OP-*` | 底層運算原語 |
| `DEF-*` | 已知缺陷或語意不明處 |

第 9 節是同一份規則的機器可讀版本。**若第 9 節與前文衝突，以前文為準**（前文描述現況行為，第 9 節是提煉）。

本文件描述的是**程式碼實際行為**，不是意圖。凡兩者不一致處一律記在第 8 節，並在正文標記 `⚠ DEF-nn`。

---

## 1. 詞彙

### 1.1 輸入型別（source types）

由檔名後綴分類，存於 `TextureGroup.textures`：

```
diffuse  normal  specular  glossiness  roughness  displacement
metallic  ao  alpha  emissive  sss  arm  unknown[]
```

`arm` = 單張貼圖打包 AO(R) / Roughness(G) / Metallic(B)。

### 1.2 中間型別（intermediate types）

存於 `TextureGroup.intermediate`，是輸入與輸出之間的正規化層：

```
albedo  reflection  normal  glossiness  height  ao
```

外加兩個未宣告但實際被寫入的鍵（來自 ARM 拆解）：`roughness`、`metallic`。

### 1.3 輸出型別（CryEngine output）

```
_diff  _spec  _ddna (或 _ddn)  _displ  _emissive  _sss
```

全部輸出為 **8-bit TIFF + LZW 壓縮**，後續交給 RC.exe 壓成 DDS。

### 1.4 兩套 PBR 工作流的對應關係

這是整條管線存在的理由：

```
來源 (Metallic/Roughness)          CryEngine (Specular/Glossiness)
─────────────────────────          ────────────────────────────────
basecolor + metallic        ──►    _diff  (albedo)
basecolor + metallic        ──►    _spec  (reflection)
roughness                   ──►    glossiness = 1 - roughness  ──► _ddna.a
normal                      ──►    _ddna.rgb
height / displacement       ──►    _displ
```

---

## 2. 資料模型

每個 `TextureGroup` 是三層 slot 的狀態機：

```
textures{}      原始輸入，路徑指向使用者檔案（唯讀）
    ↓ 中間層規則 INT-*
intermediate{}  正規化後的中間產物
    ↓ 輸出層規則 OUT-*
output{}        最終檔案路徑
```

### 2.1 貼圖物件（texture object）

一個 dict，欄位不固定，實務上分兩種型態：

**A. 帶影像的**（PIL 路徑產生）
```
{ path, image(PIL), width, height, channels, mode, type, source, *_source }
```

**B. 只帶路徑的**（ImageMagick 路徑產生）
```
{ path, channels, mode, type, source, *_source }   # 刻意不載入 image
```

⚠ **`DEF-01`**：下游的 `find_valid_path()` **只看 `path` 且要求 `os.path.exists()`**。型態 A 的物件如果沒有實際寫檔，其影像運算結果會被靜默丟棄。

### 2.2 來源解析優先序（path resolution）

所有 exporter 共用同一個 helper：

```
find_valid_path(type):
    1. intermediate[type].path   若存在且檔案存在 → 採用
    2. textures[type].path       若存在且檔案存在 → 採用
    3. None
```

**OP-RESOLVE**：中間層優先於原始層；不存在的檔案等同不存在的鍵。

### 2.3 暫存目錄

```
<repo>/.texproc_temp/<pid>/
```

由 `BatchProcessor._process_thread` 建立，`finally` 區塊 `rmtree` 清除。
`arm_processor`、`glossiness_processor`、`reflection_processor` 在 **module import 時**就計算此路徑。

⚠ **`DEF-02`**：隱性耦合。不經 `BatchProcessor` 直接呼叫這三個 processor 時，目錄不存在，寫檔失敗。

---

## 3. 執行順序

```
Stage 1 — 全部 group 跑完中間層     (progress 0.0 → 0.5)
Stage 2 — 全部 group 跑完輸出層     (progress 0.5 → 1.0)
```

兩階段之間沒有交叉；group 之間互相獨立（**可平行化，目前為序列**）。

### 3.1 Stage 1 內部順序（有依賴，不可任意重排）

```
1. INT-ARM        拆 ARM → intermediate{ao, roughness, metallic}
2. INT-ALBEDO
3. INT-NORMAL
4. INT-REFLECTION
5. INT-GLOSS      ← 消費 step 1 的 intermediate.roughness
6. INT-HEIGHT
7. INT-AO         ← 只在 step 1 沒產生 ao 時執行
```

⚠ **`DEF-03`**：`INT-REFLECTION`（step 4）在 `process_from_specular` 分支讀取 `intermediate["glossiness"]`，但 glossiness 要到 step 5 才生成，此時**必為 None**。

### 3.2 Stage 2 內部順序

無依賴，執行順序即 `diff → spec → ddna → displ → emissive → sss`。**完全可平行化。**

---

## 4. 中間層規則

### `INT-ARM` — ARM 拆解

**觸發**：`textures["arm"]` 存在
**引擎**：ImageMagick

對 R / G / B 各執行一次：

```
magick <arm> -channel {R|G|B} -separate +channel -depth 8 \
       -define tiff:compression=lzw  <temp>/{stem}_{type}_temp.tif
```

| 通道 | → 中間鍵 |
|---|---|
| R | `intermediate["ao"]` |
| G | `intermediate["roughness"]` |
| B | `intermediate["metallic"]` |

⚠ **`DEF-04`**：通道順序寫死為 ARM。ORM 恰好同序，但 MRAO、RMA 等排列無法設定。

---

### `INT-ALBEDO` — 反照率

**引擎**：PIL / numpy
分支互斥，**由上而下第一個命中者勝出**：

| # | 條件 | 行為 | `source` 標記 |
|---|---|---|---|
| 1 | `has(diffuse)` | 直接別名，**不套用 AO** | `from_diffuse` |
| 2 | `has(albedo)` | 直接別名 | `from_basecolor` |
| 3 | `has(diffuse) && has(metallic) && process_metallic` | `OP-LINEARBURN` | `generated_from_diffuse_metallic` |

⚠ **`DEF-05`（死碼）**：分支 3 的條件是分支 1 的**嚴格子集**，由 `if/elif` 鏈保證永遠不會到達。`process_from_diffuse_and_metallic()` 從未被執行過。

⚠ **`DEF-06`**：分支 1、2 只是 `dict(texture)` 加標籤，`path` 仍指向原始檔。配合 `OP-RESOLVE`，等同於**中間層對 albedo 完全沒有作用**。

**`OP-LINEARBURN`**（分支 3 的運算，即使目前無法到達）：
```
metallic → 灰階 → 反相 → m'
result = max(0, diffuse + m' - 1)
```
代數化簡後為 **`result = max(0, diffuse - metallic)`**，即「金屬處把 albedo 減黑」。

---

### `INT-NORMAL` — 法線

**引擎**：PIL

| # | 條件 | 行為 |
|---|---|---|
| 1 | `has(normal)` | 由檔名判定 DX/GL；GL 則翻轉 G 通道 |
| 2 | `has(displacement) \|\| has(height)` | `OP-NORMALFROMHEIGHT(strength)` |

**格式判定（`OP-NORMALFMT`）**，兩層：

```
第一層 — 檔名正則（is_directx_normal）
    _normal[-_]?directx | _normal[-_]?dx
    _directx[-_]?normal | _dx[-_]?normal    → DirectX
    對應的 opengl/gl 樣式                    → OpenGL
    皆不符                                   → DirectX（預設）

第二層 — 影像統計（determine_format，僅在別處呼叫時使用）
    子字串比對 "opengl"/"gl"/"directx"/"dx"
    再退回 G 通道均值：mean < 120 → OpenGL，否則 DirectX
```

⚠ **`DEF-07`**：第二層的子字串比對用 `"gl" in filename`，會誤判 `glass_normal`、`single_nrm`、`shingle_n` 等。且兩層邏輯不一致（第一層要求 `_` 邊界，第二層不要求）。

輸出恆為 DirectX 慣例（G 向上）。

---

### `INT-REFLECTION` — 反射

**引擎**：ImageMagick（metallic 路徑）／PIL（specular 路徑）

| # | 條件 | 行為 |
|---|---|---|
| 1 | `has(specular)` | 直接別名（附 `gloss_source`，見 `DEF-03`） |
| 2 | `has(metallic) && has(diffuse) && process_metallic` | `OP-METALREFL` |
| 3 | `intermediate[metallic]` 存在 `&& has(diffuse)` | 同 `OP-METALREFL`，metallic 取自 ARM |

**`OP-METALREFL`** — 尺寸取自 metallic（`magick identify`），失敗則 1024×1024：

```
magick -size WxH xc:rgb(62,62,62) \
       \( <diffuse>  -resize WxH! \) \
       \( <metallic> -resize WxH! -colorspace gray -depth 8 \) \
       -compose Over -composite -depth 8 ...
```

⚠ **`DEF-08`（行為與意圖不符）**：註解宣稱 `Reflection = lerp(DefaultGray, Diffuse, Metallic)`，但 `-composite` 只消費**兩張**影像，且 `Over` 不是遮罩混合。實際結果是 diffuse 直接蓋掉灰底，**metallic 完全沒有參與運算**。正確寫法應為：

```
magick <gray> <diffuse> <metallic-as-mask> -compose Over -composite
```
（三運算元形式，第三張才會被當作 mask），或使用 `-compose Blend` / `%[fx:]`。

**常數**：非金屬預設反射 = `rgb(62,62,62)`。此魔術數字在 `reflection_processor` 與 `spec_exporter` 各出現一次，未集中定義。

---

### `INT-GLOSS` — 光澤度（唯一有完整正規化的中間層）

**引擎**：ImageMagick
**函式**：`ensure_intermediate_glossiness(group, settings)`

**來源優先序**，第一個命中者勝出：

| # | 來源 | 需反相 |
|---|---|---|
| 1 | `textures["glossiness"]` | 否 |
| 2 | `intermediate["glossiness"]` | 否 |
| 3 | `intermediate["roughness"]`（通常來自 ARM） | **是** |
| 4 | `textures["roughness"]` | **是** |
| — | 皆無 → 回傳 None，並刪除既有的 `intermediate["glossiness"]` | |

```
magick <source> \
  [-resize {N}x{N}>]          # 僅當 output_resolution != "original"
  -colorspace gray -depth 8 \
  [-negate]                   # 僅當來源為 roughness
  -define tiff:compression=lzw  <temp>/{base}_gloss_intermediate_temp.tif
```

**`OP-INVERT`**：`glossiness = 255 - roughness`（8-bit 整數域）。

> 這是整條管線中唯一**確實寫出中間檔、且被下游正確消費**的中間層。其他中間層的行為請對照 `DEF-06`。

---

### `INT-HEIGHT` — 高度

**引擎**：PIL
`has(displacement) || has(height)` → 轉灰階，別名為 `intermediate["height"]`。
（`normalize` / `invert` / `levels` 三個方法存在但未被 pipeline 呼叫。）

⚠ 同 `DEF-06`：純別名，path 指向原始檔。

---

### `INT-AO` — 環境遮蔽

**引擎**：PIL
僅在 `intermediate["ao"]` 尚未由 `INT-ARM` 填入時執行，將 `textures["ao"]` 轉灰階。

⚠ 同 `DEF-06`。

---

## 5. 輸出層規則

所有輸出共通：

```
[-resize {N}x{N}>]              # output_resolution != "original"，僅縮不放
-depth 8
-define tiff:compression=lzw
→ {output_dir}/{base_name}_{suffix}.tif
```

**`OP-RESIZE`**：ImageMagick 的 `>` 修飾符 = 「只在超過目標時縮小，保持長寬比」。副圖（AO / alpha / gloss）必須套用**相同**的 resize 才能對齊。

---

### `OUT-DIFF` → `{base}_diff.tif`

```
底圖   = resolve(albedo) → 失敗則 resolve(diffuse)      # 必要，缺則放棄
AO     = resolve(ao)                                    # 選用
Alpha  = resolve(alpha)                                 # 選用
```

```
magick <albedo> [-resize N>] \
  # 僅當 diff_format == "diffuse_ao" 且 AO 存在：
  \( <ao> [-resize N>] -colorspace gray -depth 8 \) -compose Darken -composite \
  # 僅當 alpha 存在：
  \( <alpha> [-resize N>] -colorspace gray -depth 8 \) \
  -alpha off -compose CopyOpacity -composite \
  -depth 8 ...
```

**`diff_format`** 取值：`albedo`（預設，不套 AO）／ `diffuse_ao`（套 AO）。

⚠ **`DEF-09`（三種語意不同的 AO 混合並存）**：
- 主路徑用 **`Darken`** — 逐通道取 `min(base, ao)`
- 死掉的 PIL fallback `_darker_color_blend` 用 **Darker Color** — 依 `0.299R+0.587G+0.114B` 亮度整組挑選 RGB
- PBR 慣例是 **Multiply** — `base * ao`

三者結果不同。`Darken` 對淺色 AO 幾乎無作用（`min(0.9, 0.95)` ≈ 無變化），而 Multiply 會正確衰減。**這是視覺輸出最可能出錯的地方。**

---

### `OUT-SPEC` → `{base}_spec.tif`

```
輸入 = resolve(reflection) → 失敗則 resolve(specular)
```
純轉檔（resize + depth 8），保留彩色。

**Fallback**（`generate_missing_spec`，預設 **true**）：
生成純色 `rgb(62,62,62)`，尺寸取自 albedo → diffuse → `1024×1024`。
此 fallback 走 PIL，且對 `output_resolution` 自行做等比計算（與 `OP-RESIZE` 語意相同但為獨立實作）。

---

### `OUT-DDNA` → `{base}_ddna.tif` 或 `{base}_ddn.tif`

CryEngine 的核心格式：**RGB = 法線，A = 光澤度**。

```
法線 = resolve(normal)                        # 必要，缺則放棄整個匯出
Alpha = intermediate["glossiness"] 的 path     # 注意：不走 resolve()，只認中間層
```

```
magick <normal> [-resize N>] \
  -depth 8 -type TrueColor \
  [-channel G -negate +channel] \              # normal_flip_green
  \( <gloss_intermediate> [-resize N>] -colorspace gray -depth 8 \) \
  -alpha off -compose CopyOpacity -composite \
  -define tiff:compression=lzw ...
```

**檔名決策**：
```
gloss 中間檔存在 → _ddna.tif
否則             → _ddn.tif（無 alpha）
```

**`OP-COPYOPACITY`**：把第二張圖的灰階強度寫入第一張圖的 alpha 通道。**不做反相** — 反相已在 `INT-GLOSS` 完成。此處若再反相會造成雙重反轉。

⚠ **`DEF-10`**：`INT-GLOSS` 已套過一次 resize，此處第二次套用。因 `>` 只縮不放故為 no-op，但多一次解碼／編碼 IO。

---

### `OUT-DISPL` → `{base}_displ.tif`

```
輸入優先序：intermediate[height] → textures[displacement] → textures[height]
```

```
magick <input> [-resize N>] \
  [-auto-level] \                  # normalize_height，預設 false
  -colorspace gray -depth 8 \
  -alpha copy \                    # 灰階強度複製到 alpha
  -channel RGB +channel \
  -define tiff:compression=lzw ...
```

輸出為 **RGBA，四通道同值**。

⚠ **`DEF-11`**：`-channel RGB` 緊接 `+channel`（重置為全通道），中間沒有任何運算，這兩個參數是 no-op。可直接刪除。

---

### `OUT-EMISSIVE` → `{base}_emissive.tif`

```
輸入 = textures["emissive"] 的 path     # 只認原始層，不查中間層
```

```
magick <input> [-resize N>] \
  [-evaluate multiply {brightness}] \   # emissive_brightness，clamp 到 [0.1, 5.0]
  -depth 8 ...
```

**Fallback**（`generate_missing_emissive`，預設 **false**）：純黑 RGB。

---

### `OUT-SSS` → `{base}_sss.tif`

```
輸入 = textures["sss"] 的 path
```

```
magick <input> [-resize N>] \
  [-evaluate multiply {intensity}] \    # sss_intensity，clamp 到 [0.1, 3.0]
  -depth 8 ...
```

**Fallback A**（`generate_sss_from_diffuse`，預設 false），PIL：
```
albedo/diffuse → 灰階
→ colorize(black=(0,0,0), white=(255,240,240))     # 偏紅膚色調
→ ImageEnhance.Contrast(intensity)                  # 此處 intensity 預設 0.8
```

**Fallback B**（`generate_missing_sss`，預設 false）：純色 `rgb(40,25,25)`。

⚠ **`DEF-12`**：`sss_intensity` 一鍵兩義 —— 主路徑當作**亮度乘數**（clamp 0.1–3.0，預設 1.0），Fallback A 當作 **PIL 對比度係數**（預設 0.8）。應拆成兩個設定鍵。

---

## 6. 運算原語

重寫時只需實作這幾個，其餘都是編排：

| ID | 運算 | 定義（正規化到 0–1 的浮點域） |
|---|---|---|
| `OP-INVERT` | 反相 | `1 - x` |
| `OP-GRAY` | 灰階 | ITU-R BT.601：`0.299R + 0.587G + 0.114B` |
| `OP-LINEARBURN` | 線性加深 | `max(0, a + b - 1)` |
| `OP-DARKEN` | 逐通道取暗 | `min(a, b)` per channel |
| `OP-DARKERCOLOR` | 依亮度取暗 | `luma(a) <= luma(b) ? a : b`（整組 RGB） |
| `OP-MULTIPLY` | 相乘 | `a * b`（**目前未使用，但 `DEF-09` 建議改用**） |
| `OP-COPYOPACITY` | 灰階寫入 alpha | `dst.a = luma(src)` |
| `OP-FLIPG` | 綠通道反相 | `g' = 1 - g` |
| `OP-RESIZE` | 等比縮小 | Lanczos；`max(w,h) > N` 時才縮 |
| `OP-AUTOLEVEL` | 自動色階 | 將 `[min, max]` 線性拉伸到 `[0, 1]` |
| `OP-EVALMUL` | 亮度乘數 | `clamp(x * k, 0, 1)` |
| `OP-NORMALFROMHEIGHT` | 高度轉法線 | Sobel 梯度 × strength，正規化後映射到 `[0,1]` |
| `OP-COLORIZE` | 雙色映射 | `lerp(black, white, gray)` |

---

## 7. 設定鍵

| 鍵 | 型別 | 預設 | 影響 |
|---|---|---|---|
| `output_resolution` | `"original"` \| `"512"`… | `"original"` | 全部 `OUT-*` 與 `INT-GLOSS` |
| `diff_format` | `albedo` \| `diffuse_ao` | `albedo` | `OUT-DIFF` |
| `normal_flip_green` | bool | `false` | `OUT-DDNA` |
| `normalize_height` | bool | `false` | `OUT-DISPL` |
| `process_metallic` | bool | `true` | `INT-ALBEDO`、`INT-REFLECTION` |
| `normal_from_height_strength` | float | `10.0` | `INT-NORMAL` |
| `generate_missing_spec` | bool | `true` | `OUT-SPEC` fallback |
| `generate_missing_emissive` | bool | `false` | `OUT-EMISSIVE` fallback |
| `generate_missing_sss` | bool | `false` | `OUT-SSS` fallback B |
| `generate_sss_from_diffuse` | bool | `false` | `OUT-SSS` fallback A |
| `emissive_brightness` | float | `1.0` | clamp `[0.1, 5.0]` |
| `sss_intensity` | float | `1.0` / `0.8` | 見 `DEF-12` |
| `texture_types{}` | dict\<str, bool\> | 全 `true` | 各 `OUT-*` 開關 |

---

## 8. 缺陷清單

按重寫時的處理優先序排列。

| ID | 嚴重度 | 位置 | 摘要 |
|---|---|---|---|
| `DEF-08` | **高** | `INT-REFLECTION` | `-composite` 只吃兩張圖，metallic 未參與運算，反射圖等於 diffuse |
| `DEF-09` | **高** | `OUT-DIFF` | AO 用 `Darken` 而非 `Multiply`，淺色 AO 近乎無效 |
| `DEF-05` | **高** | `INT-ALBEDO` | 分支 3 為 `if/elif` 死碼，metallic→albedo 從未執行 |
| `DEF-06` | **高** | `INT-ALBEDO/HEIGHT/AO` | 中間層只做 dict 別名不寫檔，運算結果被 `OP-RESOLVE` 丟棄 |
| `DEF-03` | 中 | Stage 1 順序 | reflection 先於 glossiness 生成，讀到必為 None |
| `DEF-12` | 中 | `OUT-SSS` | `sss_intensity` 一鍵兩義 |
| `DEF-07` | 中 | `OP-NORMALFMT` | `"gl" in filename` 子字串誤判 |
| `DEF-04` | 中 | `INT-ARM` | 通道順序寫死，不支援 MRAO/RMA |
| `DEF-01` | 中 | 資料模型 | texture object 兩種型態並存，契約不明確 |
| `DEF-02` | 低 | 暫存目錄 | module import 期算路徑，與 BatchProcessor 隱性耦合 |
| `DEF-10` | 低 | `OUT-DDNA` | glossiness 重複 resize，多一次 IO |
| `DEF-11` | 低 | `OUT-DISPL` | `-channel RGB +channel` 為 no-op |

### 8.1 架構層級的觀察

**引擎混用**是所有缺陷的共同根源。同一條管線裡：

```
PIL/numpy 路徑：INT-ALBEDO、INT-NORMAL、INT-HEIGHT、INT-AO、所有 fallback
ImageMagick 路徑：INT-ARM、INT-GLOSS、INT-REFLECTION、所有 OUT-*
```

兩者的**混合模式語意不同**（`DEF-09`）、**資料交換靠寫暫存檔**（`DEF-01`、`DEF-02`）、**同一個運算有兩套實作**（resize 在 `OUT-SPEC` fallback 就有第二份）。

重寫時的單一最重要決定：**統一成單一 in-process 影像核心，中間層全部改為記憶體內的 planar f32 buffer，只在最終輸出時量化為 8-bit。** 這一步同時消滅 `DEF-01`、`DEF-02`、`DEF-06`、`DEF-09`、`DEF-10`。

---

## 9. 機器可讀規則表

```yaml
version: 1
source_commit: main
color_model:
  working_space: linear_f32_planar   # 建議值，非現況
  current_space: srgb_u8_interleaved # 現況
  output_depth: 8
  output_format: tiff
  output_compression: lzw

constants:
  default_nonmetal_reflection: [62, 62, 62]
  default_sss_color: [40, 25, 25]
  sss_colorize_white: [255, 240, 240]
  default_texture_size: [1024, 1024]
  luma_weights: [0.299, 0.587, 0.114]

types:
  source: [diffuse, normal, specular, glossiness, roughness, displacement,
           metallic, ao, alpha, emissive, sss, arm]
  intermediate: [albedo, reflection, normal, glossiness, height, ao,
                 roughness, metallic]   # 後兩者未在初始化中宣告
  output: [diff, spec, ddna, ddn, displ, emissive, sss]

resolution_order:
  rule: OP-RESOLVE
  steps: [intermediate, textures]
  requires_file_exists: true

intermediate_rules:
  - id: INT-ARM
    engine: imagemagick
    when: "textures.arm"
    channel_map: { R: ao, G: roughness, B: metallic }
    writes: [intermediate.ao, intermediate.roughness, intermediate.metallic]
    defects: [DEF-04]

  - id: INT-ALBEDO
    engine: pil
    branches:
      - when: "textures.diffuse"
        op: alias
        note: "AO 不在此處套用"
      - when: "textures.albedo"
        op: alias
      - when: "textures.diffuse && textures.metallic && cfg.process_metallic"
        op: OP-LINEARBURN
        formula: "max(0, diffuse - metallic)"
        reachable: false
    defects: [DEF-05, DEF-06]

  - id: INT-NORMAL
    engine: pil
    branches:
      - when: "textures.normal"
        op: OP-NORMALFMT
        action: "opengl 時套用 OP-FLIPG"
      - when: "textures.displacement || textures.height"
        op: OP-NORMALFROMHEIGHT
        param: cfg.normal_from_height_strength
    output_convention: directx
    defects: [DEF-07]

  - id: INT-REFLECTION
    engine: [pil, imagemagick]
    branches:
      - when: "textures.specular"
        op: alias
      - when: "textures.metallic && textures.diffuse && cfg.process_metallic"
        op: OP-METALREFL
      - when: "intermediate.metallic && textures.diffuse && cfg.process_metallic"
        op: OP-METALREFL
    intended_formula: "lerp(gray62, diffuse, metallic)"
    actual_behaviour: "diffuse over gray62; metallic 未被消費"
    defects: [DEF-08, DEF-03]

  - id: INT-GLOSS
    engine: imagemagick
    source_priority:
      - { from: textures.glossiness,     invert: false }
      - { from: intermediate.glossiness, invert: false }
      - { from: intermediate.roughness,  invert: true  }
      - { from: textures.roughness,      invert: true  }
    ops: [OP-RESIZE, OP-GRAY, OP-INVERT]
    writes_file: true
    on_failure: "刪除 intermediate.glossiness"
    status: canonical   # 唯一行為完整正確的中間層

  - id: INT-HEIGHT
    engine: pil
    when: "textures.displacement || textures.height"
    op: OP-GRAY
    defects: [DEF-06]

  - id: INT-AO
    engine: pil
    when: "!intermediate.ao && textures.ao"
    op: OP-GRAY
    defects: [DEF-06]

output_rules:
  - id: OUT-DIFF
    suffix: _diff
    base: { resolve: [albedo, diffuse], required: true }
    layers:
      - { input: ao,    when: "cfg.diff_format == 'diffuse_ao'",
          op: OP-DARKEN, recommended_op: OP-MULTIPLY }
      - { input: alpha, when: "resolved", op: OP-COPYOPACITY }
    defects: [DEF-09]

  - id: OUT-SPEC
    suffix: _spec
    base: { resolve: [reflection, specular], required: false }
    preserves_color: true
    fallback:
      when: cfg.generate_missing_spec
      default: true
      produces: "flat rgb(62,62,62)"

  - id: OUT-DDNA
    suffix: { with_alpha: _ddna, without_alpha: _ddn }
    base: { resolve: [normal], required: true }
    base_ops: [ "-type TrueColor", "OP-FLIPG when cfg.normal_flip_green" ]
    alpha:
      source: intermediate.glossiness   # 不走 OP-RESOLVE
      op: OP-COPYOPACITY
      invert_here: false                # 反相已於 INT-GLOSS 完成
    defects: [DEF-10]

  - id: OUT-DISPL
    suffix: _displ
    base:
      priority: [intermediate.height, textures.displacement, textures.height]
      required: true
    ops: [ "OP-AUTOLEVEL when cfg.normalize_height", OP-GRAY, "alpha copy" ]
    output_channels: RGBA
    channel_values: identical
    defects: [DEF-11]

  - id: OUT-EMISSIVE
    suffix: _emissive
    base: { source: textures.emissive, required: false }
    ops: [ { op: OP-EVALMUL, param: cfg.emissive_brightness, clamp: [0.1, 5.0] } ]
    fallback: { when: cfg.generate_missing_emissive, default: false,
                produces: "flat black" }

  - id: OUT-SSS
    suffix: _sss
    base: { source: textures.sss, required: false }
    ops: [ { op: OP-EVALMUL, param: cfg.sss_intensity, clamp: [0.1, 3.0] } ]
    fallbacks:
      - { when: cfg.generate_sss_from_diffuse, default: false,
          chain: [OP-GRAY, OP-COLORIZE, contrast] }
      - { when: cfg.generate_missing_sss, default: false,
          produces: "flat rgb(40,25,25)" }
    defects: [DEF-12]

execution:
  stages:
    - { id: 1, name: intermediates, progress: [0.0, 0.5],
        order: [INT-ARM, INT-ALBEDO, INT-NORMAL, INT-REFLECTION,
                INT-GLOSS, INT-HEIGHT, INT-AO],
        order_is_significant: true }
    - { id: 2, name: outputs, progress: [0.5, 1.0],
        order: [OUT-DIFF, OUT-SPEC, OUT-DDNA, OUT-DISPL, OUT-EMISSIVE, OUT-SSS],
        order_is_significant: false }
  parallelism:
    across_groups: safe
    within_stage_2: safe
    current_implementation: serial

temp_dir:
  path: "<repo>/.texproc_temp/<pid>"
  created_by: BatchProcessor._process_thread
  cleaned_by: "finally: shutil.rmtree"
  defects: [DEF-02]
```

---

## 10. 重寫時的驗證錨點

移植後要證明「行為等價」，比對這幾點即可覆蓋大部分風險：

1. **`_ddna` 的 alpha 通道** — 給定一張 roughness，輸出 alpha 必須等於 `255 - roughness`（逐像素精確比對）。這是最容易雙重反轉的地方。
2. **`_diff` 的 AO 混合** — 若刻意修正 `DEF-09` 改用 Multiply，**輸出將不等價**，需人工確認新結果才是正確的。這是唯一應該刻意打破等價性的地方。
3. **`_displ` 的四通道一致性** — R == G == B == A。
4. **檔名決策** — 有 gloss 來源時必須是 `_ddna`，無則 `_ddn`。RC.exe 對兩者處理不同。
5. **resize 的單向性** — 小於目標解析度的貼圖不得被放大。
6. **缺失來源時的 fallback 開關** — 六個 `generate_*` 旗標的預設值必須保持（尤其 `generate_missing_spec` 預設為 true，其餘為 false）。
