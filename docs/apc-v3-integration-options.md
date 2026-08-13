# texproc v3 構想:APC 完成後如何完整支援 Asset Platform 工作流

> 2026-08-13。**這是前瞻筆記,不是規格。** 沒有任何一項已被裁決。
> 上游:本倉 `docs/apc-texproc-reference.md`(v2 實作盤點);
> APC 側 `E:\coding1\assetplatformce\docs\notes\m2a_remote_compute_design.md`(遠端算力協議)、
> `docs\notes\gltf_line_design.md`(glTF 線)、`docs\00_design.md`、`docs\03_conversion_spec.md`。
> APC 引用一律標成 `m2a:行` / `03_conv:行` / `00_design:行` / `image.rs:行`。

---

## 0. 結論先行

1. **texproc 與 M3 不是同一段管線,先把這件事釐清再談形態。**
   M3「貼圖線原生化」的目標是把 **tif/hdr → dds** 那一段脫離 `rc.exe`
   (`00_design:112` D7、`03_conv:110-111`)。
   texproc 做的是 **任意來源 → 符合 CE 慣例的 tif 組**,而且中間夾了一段
   PBR(metallic/roughness)→ CE(specular/glossiness)的語意轉換。
   **這一段目前 APC 完全沒有,rc 也沒有,ImageMagick 更沒有。**
   ImageMagick 現在只做 1:1 的格式轉檔(`image.rs:213-218` 只傳兩個路徑,零選項)。
   所以 texproc 不是來搶 M3 的工作,是來補 M3 上游那個空缺。

2. **傾向形態:(c) 抽共用 crate,但要拆成兩個消費點,而不是一個。**
   - **分組(scan)** 是 N:M 的、要看 sibling 檔案的操作,必須在**組 job 之前**發生
     → Manager 側以 library 呼叫(它正好餵養 APC 的 path-aware input manifest)。
   - **轉換(process)** 是純函數、吃一組輸入吐一組輸出
     → worker 側以 library 呼叫,包在 `native/texture` 能力家族的一個特性旗標裡。
   - texproc CLI/GUI 繼續存在,作為離線批次與美術端工具,共用同一個 crate。
   理由見 §3.3。

3. **形態 (a)「texproc 當獨立行程 worker、註冊 `native/texture`」與 APC 既有設計直接牴觸。**
   m2a 已經寫明 `native/texture` 是 **daemon 的進程內 Rust 能力**:
   > 「M3 貼圖原生化落地後,`native/texture` 成為 daemon 的第二個能力家族(**進程內 Rust,不經 rc**),
   > 能力路由自動把貼圖負載導向它」(`m2a:48`)
   再開一個外部行程等於多一份 toolchain identity、多一次 blob 往返,換不到隔離價值
   (rc 需要行程隔離是因為它會崩且有全域狀態,`m2a:43-48`;純 Rust 影像核心沒有這個問題)。

4. **形態 (b)「保持獨立、透過 asset.import 匯入產物」是可用的過渡橋,但不是終局。**
   它能立刻運作、零協定工作,代價是 **PBR 轉換整段落在 build graph 之外**:
   APC 只認得產出的 tif 是一個 source,不知道它從哪張 basecolor+metallic 來、
   用什麼 settings 轉的,因此無法重現、無法快取、來源改動時無法重跑。詳見 §3.2。

5. **三個必須先解掉的硬衝突**(與形態無關,任何一種都要面對):
   - v2 輸出寫死 8-bit,而 APC 已裁定「保留 alpha 與位深」(`image.rs:31-37`)。
   - v2 支援 10 種輸入副檔名,ImageMagick 白名單有 36 種(`image.rs:67-71`,含 psd/svg)。
   - v2 的 converter **自己隨機發 GUID** 寫 `.mtl.cryasset`(`converter/src/cryasset.rs:42,147-149`),
     而 APC 裁定 Manager 是唯一 GUID 權威、rc 自寫隨機 GUID 是已知汙染源(`00_design:68,120`)。
   詳見 §4。

---

## 1. v2 目前的角色邊界

**一句話:一個對引擎與專案完全無知的離線工具。讀磁碟、寫磁碟,結束。**

| 面向 | 現況 | 位置 |
|---|---|---|
| 輸入 | 檔案或目錄路徑(遞迴)。無 project root、無 asset root 概念 | `texproc/src/grouping.rs:439-472` |
| 輸出 | `--out DIR` 下的 `{base}_{suffix}.tif`;`.hdr` passthrough 同目錄 | `texproc/src/output.rs:214-227`、`passthrough.rs:35-63` |
| 身分 | **無**。不發 GUID、不寫 `.cryasset`、不算 digest、不記錄來源 | texproc 全 crate 零命中 |
| 與 rc 的銜接 | **只有 GUI 會呼叫**:`RC.exe <tif> /refresh /userdialog=0`,cwd = 輸出目錄,DDS 落在 tif 旁邊,可選刪 tif | `texproc-gui/src/worker.rs:479-495`、`412-417` |
| rc 設定 | **不傳**。無 `/savesettings`、無 CryTif chunk,rc 只能吃它自己的 auto-preset | 全倉零命中 |
| 併發 | 程式內 rayon 跨 group;RC 是 GUI 層的自適應多行程池 | `batch.rs:57-121`、`worker.rs:335-468` |
| 契約面 | CLI 已凍結(退出碼 0/1/2/3);settings JSON 嚴格鍵;scan JSON 可序列化往返 | `texproc/src/main.rs:14`、`settings.rs:112`、`grouping.rs:186-191` |
| 已經是 library | 是。CLI 與 GUI 都只是 lib 的兩個 front-end | `texproc/src/lib.rs`;T-B03 明列「GUI 直接依賴 texproc(lib)做 in-process 呼叫」 |

**最後一列是所有 v3 討論的基礎**:v2 早就不是「CLI 加一層 lib」,而是
「lib 加兩個 front-end」。第三個 front-end(APC)在架構上不是新事。

**銜接 rc 的方式有個結構性落差要注意**:v2 是「先全部寫成 tif,再逐檔丟給 rc」。
APC 的 M2a 正在修的效能債恰好是同一個形狀——file monitor 逐檔觸發、有效寬度 1,
99 張 4K 要 17 分鐘,而 R9 批次通道是 1.7 秒/張(`m2a:60`)。
v2 的 `run_dds_pool`(`worker.rs:335-468`)已經是這個問題的一個實作解;
**它不是 v3 才要做的東西,是 v2 現在就有、APC 現在缺的東西。**

---

## 2. 接點的具體形狀(先把協定講清楚,再談形態)

### 2.1 能力宣告

APC 的能力是三元組(`m2a:20-28`):**家族名 + 工具鏈指紋 + 特性旗標**,路由做子集匹配。
既有家族名:`rc/image`、`rc/cgf`、`rc/character`、`rc/abc`、`native/texture`(M3 後)、
`assimp/scene`(cece 線後)。前綴表明實作載體。

texproc 的核心不應該自成家族。建議形狀:

```
family:  native/texture
flags:   [ "dds-pc" ,            // M3 本體:tif|hdr -> dds (CTSquish/astcenc)
           "prep-pbr" ,          // texproc 核心:來源組 -> CE tif 組(MR->SG 轉換)
           "prep-passthrough" ,  // 1:1 任意來源 -> tif(取代 ImageMagick 的角色)
           "group-aware" ]       // 接受多輸入單 action 的貼圖組語意
toolchain: <合成 digest>         // 與 action key 的 toolchain 分量同源同格式
```

理由:`m2a:26` 明說特性旗標就是「家族內可選能力(如 `rc/image` 是否帶 PVRTexLib)」。
把 texproc 核心做成旗標而不是新家族,好處是 M3 的 daemon 可以只宣告 `dds-pc`
先上線,`prep-*` 之後補;Linux 節點在只有 `prep-*` 沒有 `dds-pc` 時仍然能接到活。

**版本紅線**:`m2a:28` 禁止「悄悄改派且不改 key」。texproc 的
`TextureSettings` 預設值(尤其六個 `generate_*` 旗標與 metal gate 的四個閾值,
`texproc/src/output.rs:84-110`、`pipeline.rs:92-102`)一旦改動就改變輸出位元,
**必須進 toolchain identity 或 recipe,不能當隱含預設**。

### 2.2 job 訊息

M2a 的作業層草案(`m2a:13-18`)是 `job.offer` / `job.accept` / `job.reject` /
`job.progress` / `job.complete` / `job.failed` / `job.cancel`。
(注意:目前 `src/protocol/src/messages/worker.rs` 實作的是
`worker.register/claim/heartbeat/result`,`job.*` 還是草案。)

一個貼圖組 job 大概長這樣:

```jsonc
// job.offer
{
  "action_key": "<blake3>",
  "capability": { "family": "native/texture", "flags": ["prep-pbr", "group-aware"] },
  "inputs": [                                  // = path-aware input manifest
    { "logical_path": "KB3D_ENC_AtlasA_basecolor.png", "blob": {"hash":"...","size":...},
      "hint_path": "D:/proj/Assets/tex/KB3D_ENC_AtlasA_basecolor.png" },
    { "logical_path": "KB3D_ENC_AtlasA_normal.png",    "blob": {...}, "hint_path": "..." },
    { "logical_path": "KB3D_ENC_AtlasA_roughness.png", "blob": {...}, "hint_path": "..." },
    { "logical_path": "KB3D_ENC_AtlasA_ao.png",        "blob": {...}, "hint_path": "..." }
  ],
  "recipe": { /* = texproc 的 settings JSON,原樣 */ }
}
// job.complete
{ "outputs": [ {"logical_path":"KB3D_ENC_AtlasA_diff.tif", "blob":{...}},
               {"logical_path":"KB3D_ENC_AtlasA_spec.tif", "blob":{...}},
               {"logical_path":"KB3D_ENC_AtlasA_ddna.tif", "blob":{...}} ],
  "metrics": { "elapsed_seconds": 1.23, "groups": 1 } }
```

三個對得非常好的地方:

1. **`recipe` 直接就是 texproc 的 settings JSON。**
   APC 側 recipe 是 opaque JSON(`03_conv §2`);texproc 側
   `texture_settings_from_value` / `texture_settings_to_value` 已經是嚴格鍵、
   可往返、有測試的形狀(`texproc/src/settings.rs:42-162`、`217-230`)。
   零轉換成本,而且嚴格鍵檢查正好防住 recipe 打錯字靜默生效。

2. **path-aware input manifest 天生就是為貼圖組設計的。**
   `03_conv:16` 的理由原文是「只用 digest 集不足以定義身分——RC 輸出受檔名
   (`_ddn` 類後綴)、相對路徑與 sibling 檔影響」。
   texproc 的分組**整個**就建立在這三件事上:後綴決定型別
   (`grouping.rs:371-436`)、base name 決定分組(`grouping.rs:230`)、
   同組 sibling 決定產出哪幾張(`output.rs:176-212`)。
   **同一個 action key 定義同時滿足 rc 與 texproc,不需要為 texproc 另設身分模型。**

3. **blob 的 hint path 讓本機路徑不消失。**
   `m2a §4`:worker 先查 Manager 附帶的 hint 路徑、驗雜湊後直用,驗不過才拉取;
   hint 是優化不是契約。所以 texproc 核心可以繼續是「吃路徑」的函式,
   只要在 worker 側套一層解析器,**核心程式碼不必改成吃 byte stream**。

### 2.3 產物落地與租約

- **worker 對資產樹零寫入權**(`m2a §4`):產物寫進 worker 自己的暫存區、
  以 blob 引用上報,落位一律由 Manager 做。
  → **`write_stage2_outputs` / `process_and_write_stage2`(`output.rs:214-263`)
  在 worker 形態下必須換成「寫暫存 + 回報引用」**。這是 v2 唯一一處真正的
  「對外部世界寫入」,改動範圍很小(兩個函式)。
- **租約**:一 job 至多一個活租約、續期綁心跳、逾時單方回收、重派帶單調遞增
  attempt、過期 attempt 的遲到 complete 一律丟棄(`m2a §3`)。
  texproc 的取消旗標(`&AtomicBool`,`batch.rs:57-121` 全程檢查)已經有正確的形狀,
  接 `job.cancel` 只是換觸發源。
- **冪等性由 action key 承擔,作業層 at-least-once 就夠**(`m2a §3`)。
  texproc 是純函數(Stage 1/2 全在記憶體,`pipeline.rs:909-931` 有
  「不寫暫存目錄」的測試),重跑無副作用,天然滿足。

### 2.4 四態控制面的關係

四態(`CompilerService.h:26-37`):`Native` / `Delegated` / `Draining` / `ReadOnly`。
texproc 若成為 worker 的一個能力,它只影響 **Delegated 的供給面**
(`m2a §6`:「有可用 worker＝Delegated 的供給面成立」),**不新增狀態**。
若 texproc 保持獨立(形態 b),它根本不在這個狀態機裡——這正是形態 b 的
本質特徵:**它是 build graph 外的前處理器**。

---

## 3. 三種形態的得失

### 3.1 (a) texproc 成為獨立行程 worker,註冊 `native/texture`

**做法**:texproc 加一個 `texproc serve --manager <addr>` 子命令,實作
hello/能力宣告/心跳 + `job.*`,以獨立 exe 跑在節點上。

| 得 | 失 |
|---|---|
| 行程隔離:texproc 崩了不拖累 daemon | **與 `m2a:48` 的既定設計直接牴觸**——那裡寫明 `native/texture` 是 daemon 的進程內 Rust 能力 |
| texproc 可以獨立發版 | 多一份 toolchain identity 要合成、要與 daemon 版本協調;`m2a:28` 的版本策略要處理兩個獨立軸 |
| 現有 CLI 幾乎不動 | 協定實作要在 texproc 倉再寫一遍(hello/心跳/租約/blob/續傳),與 daemon 重複 |
| — | blob 要跨行程搬,而它本來只是一次 library call |
| — | 隔離換不到價值:v2 是純 Rust、無全域狀態、已經 `catch_unwind`(`batch.rs:85-99`) |

**判斷**:除非哪天 texproc 引入會崩的 C 依賴(例如為了 psd/jp2 綁 OpenImageIO),
否則獨立行程的成本大於收益。

**v2 程式碼存活率**:最高(~95% 原樣),但**新增的協定層是純負債**。

### 3.2 (b) texproc 保持獨立正規化工具,透過 `asset.import` 匯入產物

**做法**:美術照舊跑 texproc CLI/GUI 產出 tif 到某個 staging 目錄,
再對該目錄下 `asset.import {source_paths[], dest_dir, recipe?}`
(`src/protocol/src/messages/asset.rs:9-45`)。
Manager 走 copy → identify → record → dispatch → land → publish
(`src/manager/src/convert/import.rs:1-37`),tif 拿到 GUID/digest/action key,
之後由 `rc/image` 或 M3 的 `native/texture` 壓成 dds。

| 得 | 失 |
|---|---|
| **今天就能做,零協定工作**,兩邊都不用改一行 | **PBR 轉換整段在 build graph 之外**:APC 只知道那張 `_diff.tif` 是一個 source |
| 產物確實取得完整身分(GUID / digest / action key) | 來源(basecolor/metallic/roughness)不在 input manifest 裡 → **來源改了 APC 不知道要重跑** |
| 職責邊界乾淨,兩邊各自演進 | **不可重現**:同一批 tif 沒有記錄用什麼 settings、什麼版本的 texproc 轉出來的 |
| 適合「一次性素材包導入」這種真實用例 | 快取只在 tif→dds 那段生效;改一個 metal gate 閾值要人工重跑全部 |
| — | tif 與原始 png 的關係只存在於檔名慣例裡,沒有任何機器可讀的連結 |

**判斷**:**當過渡橋很好,當終局不行。** 它讓 texproc 立刻對 APC 有用,
但把「PBR 轉換」永久排除在增量建置之外——而那正是最耗時、最需要快取的一段。

**v2 程式碼存活率**:100%,一行不改。

### 3.3 (c) 混合:抽共用 crate,批次正規化留 CLI,轉換核心同時服務 Manager 與 worker

**做法**:把 texproc lib 拆成兩塊給 APC 連結:

```
texproc-core (新 crate 名,內容 = 現行 texproc lib)
├── grouping / io::probe_header          ← Manager 連結:形成 job、算 input manifest
│     scan_inputs() -> ScanResult                (grouping.rs:208-276)
│     probe_header() -> HeaderInfo               (io.rs:44-51)
└── pipeline / output / ops / planar     ← worker daemon 連結:執行 job
      process_stage1 + process_stage2           (pipeline.rs:147, output.rs:176)

texproc  (CLI)  ─┐
texproc-gui     ─┼─→ 都繼續用 texproc-core,契約不變
APC manager     ─┤
APC worker daemon┘
```

**為什麼要拆成兩個消費點,而不是整塊塞進 worker**:
分組是 N:M 的,而且**必須在 job 形成之前發生**——job 的 input manifest 就是
「這一組有哪幾個檔」。若把分組放進 worker,Manager 就無法在派工前知道
一個 job 該包含哪些輸入,action key 也無從計算。
`ScanResult` 已經是 `Serialize + Deserialize`(`grouping.rs:177-191`),
天生就是這個介面。

| 得 | 失 |
|---|---|
| 與 `m2a:48` 的既定設計一致(進程內 Rust,不經 rc) | 要動 crate 佈局(改名/拆分),影響現有兩個 front-end 的 import 路徑 |
| PBR 轉換進入 build graph:有 action key、可快取、可增量 | texproc 的發版節奏被 APC 的 toolchain identity 綁住 |
| 分組直接餵養 path-aware input manifest,身分模型零新增 | `write_stage2_outputs` 要改成「寫暫存 + 回引用」(範圍小,`output.rs:214-263`) |
| CLI/GUI 繼續存在,美術離線流程不被破壞 | 兩個消費點意味著兩處要同步(分組規則變更會同時影響 key 與執行) |
| Linux/Mac worker 立刻可用(核心零平台依賴) | — |

**判斷:傾向這一種。** 理由是它同時滿足三件事——不與 APC 既定設計打架、
把最耗時的一段納入快取、且不犧牲美術端的離線工具。

**v2 程式碼存活率**:核心 ~90% 存活。

---

## 4. 每種形態下的程式碼盤點

### 4.1 直接存活(三種形態皆同)

| 模組 | 行數量級 | 為什麼能原樣活 |
|---|---|---|
| `texproc/src/planar.rs` | 168 | 純資料結構,零依賴 |
| `texproc/src/ops.rs` | 490 | 13 個純函式,只用 `image::imageops::resize` |
| `texproc/src/pipeline.rs` | 1071 | Stage 1 全記憶體,含 metal gate;無 IO |
| `texproc/src/grouping.rs` | 731 | 純檔名 + 檔頭;`ScanResult` 已可序列化 |
| `texproc/src/settings.rs` | 231 | 直接當 recipe 的 parser |
| `texproc/src/io.rs` 的探測半邊 | ~450 | 六個檔頭解析器,`Read + Seek` 上的純函式 |
| `ce-schema` 全 crate | 198 + JSON | CE 後綴/槽位表,唯一事實來源 |

### 4.2 必改:16-bit 保留與 alpha 透傳(M3 既定要求)

APC 的裁定原文(`image.rs:31-37`,同義重複於 `03_conv:60`、`m0_gaps.md:17`):

> `-type TrueColor` is deliberately not passed. …it forces 8-bit RGB, so a png
> with alpha loses its alpha and a 16-bit png loses half its precision, for every
> import, to protect one preset. **The ruling for this platform is to keep alpha
> and bit depth; a preset that cannot cope with an alpha channel is a preset problem.**

v2 現況與這條裁定的三個衝突點,以及最小改法:

| 衝突 | v2 位置 | 最小改法 |
|---|---|---|
| 輸出只有 `Gray8/RGB8/RGBA8` | `io.rs:89-94` | 加 `Gray16/RGB16/RGBA16` 分支 + `planar.rs` 加 `to_interleaved_u16`;**核心不動,因為 f32 早已保留 16-bit 精度**(`planar.rs:68-77`) |
| `PlanarImage` 硬 clamp 到 `0..=1` | `planar.rs:35-39` | 放寬成建構時的 policy 參數;HDR 路徑目前是繞過整個型別(`passthrough.rs:1-8` 的註解已承認這件事) |
| 沒有「1:1 不做 PBR 轉換」的模式 | 無 | 新增 `prep-passthrough` recipe:解碼 → 原位深原通道寫 tif。這是取代 ImageMagick 的最小面 |

> **注意順序**:第一項是三者中最便宜的(v2 給 M3 最省力的交接點),第三項才是
> 取代 ImageMagick 的關鍵。第二項只有在真的要處理 HDR 貼圖(非 env map)時才需要。

### 4.3 必改:格式覆蓋率的缺口

| | 支援數 | 清單 |
|---|---:|---|
| ImageMagick(現況) | **36** | `image.rs:67-71`,含 psd / svg / ico / jp2 等 |
| texproc v2 | **10** | png jpg jpeg tif tiff exr hdr tga bmp webp(`grouping.rs:17-18`) |

**建議照 glTF 線的既有格局處理長尾**:`gltf_line_design.md` 已裁定
`fbx=ufbx`、`gltf=cgltf`、`collada=stock`、**長尾(obj/stl/ply/舊 dae)=assimp**。
貼圖線套同一個形狀最省事:

```
主線(png/jpg/tif/tga/bmp/webp/exr/hdr)  = native Rust(texproc core)
長尾(psd/svg/ico/jp2/…)                = 保留 ImageMagick 當 fallback converter
```

這樣既不回歸格式覆蓋率,又讓 Linux worker 在主線上就有產值——正是
`m2a:48` 說的「Linux 節點開始有產值的時刻」。反過來說,**若不做這個 fallback,
用 texproc 取代 ImageMagick 就是一次功能回歸,會擋住 M3 的對等閘**
(`03_conv:110`:「功能對等閘＝`rc_inventory/03_image.md` 逐項打勾」)。

### 4.4 CryTif chunk 與 `/savesettings`:APC 接手後還需要嗎

**先確認 v2 現況**:一個都沒有。texproc 不寫 CryTif chunk、不傳 `/savesettings`,
rc 只能吃自己的 auto-preset(§1 表)。所以這不是「要不要拿掉」,是「要不要新增」。

答案取決於誰是 preset 的權威:

| 情境 | 還需要 CryTif chunk 嗎 |
|---|---|
| APC 驅動的編譯(job 的 recipe 帶 preset) | **不需要**。preset 進 recipe → 進 action key,是更強的保證:改 preset 會讓 key 失效並自動重編 |
| 美術在 Sandbox 裡開該 tif 的貼圖對話框 | **需要**。stock 的 UI 從 chunk 讀 per-texture 設定;沒有 chunk 就退回 auto-preset |
| rc 在 APC 之外被呼叫(舊流程、手動) | **需要**,否則設定遺失 |

而且有一條 M3 紅線與此直接相關(`03_conv:111`):

> auto-preset 規則必須從 `ImageCompiler.cpp:457-548` 移植(不在 rc.ini)

auto-preset 是**由檔名後綴推導**的(`_ddn` 之類)——這正好是 texproc 後綴表的定義域
(`docs/apc-texproc-reference.md` §3.7)。也就是說:
**texproc 的後綴表與 M3 的 auto-preset 表必須是同一張表,否則會出現
「texproc 命名成 `_ddna`、M3 的 auto-preset 卻認不出來」的斷鏈。**
建議把 `ce-schema` 的後綴/槽位表升格為兩邊共用的凍結表。

**建議**:v3 加一個 `--write-crytif-settings` 的選配(預設 off),
只在「產物要進 stock Sandbox 給人手動調」時才寫。
APC 驅動的路徑一律走 recipe,不依賴 chunk。

### 4.5 必改:GUID 自發放

`converter/src/cryasset.rs:42` 呼叫 `new_guid()`(`cryasset.rs:147-149`,
自製 random GUID)寫進 `.mtl.cryasset` 的 `guid` 屬性(`cryasset.rs:82-83`)。

APC 的裁定(`00_design:68,120`):**Manager 是唯一 GUID 發放/收養權威**,
「rc 自寫隨機 GUID 是已知汙染源,由落位檢查與 reconcile 修正」。

→ 任何形態下,converter 的 cryasset writer 進 APC 時都必須改成
**接受 Manager 預派的 GUID**,不可自產。形態 (b) 下這條也成立
(Manager 的 import 流程會在 land 階段改寫 sidecar GUID,
見 `src/manager/src/convert/import.rs` 的 `land` 步驟——也就是說形態 (b) 下
texproc 產生的 GUID 會被 Manager 覆寫,不會汙染,但也等於白做)。

### 4.6 各形態的改動總表

| 項目 | (a) 獨立 worker | (b) asset.import | (c) 共用 crate |
|---|---|---|---|
| `planar` / `ops` / `pipeline` | 原樣 | 原樣 | 原樣 |
| `grouping` | 原樣 | 原樣 | **Manager 側連結**,回傳 `ScanResult` 供組 job |
| `settings` | 原樣 | 原樣 | 當 recipe parser |
| `output::write_stage2_outputs` | 改成寫暫存 + 回 blob 引用 | 原樣 | 改成寫暫存 + 回 blob 引用 |
| 16-bit 出口 | 要做 | 要做 | 要做 |
| passthrough(1:1)模式 | 要做 | 選做 | 要做 |
| 長尾格式 fallback | 要做 | 不需要(ImageMagick 仍在) | 要做 |
| 協定層(hello/心跳/租約/blob) | **要在 texproc 倉重寫一遍** | 不需要 | 由 daemon 提供,texproc 零負擔 |
| CLI / GUI | 保留 | 保留 | 保留 |
| GUID 自發放 | 要移除 | 會被 Manager 覆寫(等於白做) | 要移除 |
| CryTif chunk | 選配 | 選配 | 選配 |

---

## 5. 若走 (c),一條可分階段的路（僅供討論）

> 每一階可獨立驗收,任一階停下來都不會留下半成品。

**S0 — 不改 texproc,先當形態 (b) 用。**
美術跑現有 CLI/GUI 產 tif,對 staging 目錄 `asset.import`。
驗收:tif 進 catalog、拿到 GUID/digest、由 `rc/image` 壓成 dds。
價值:立刻可用,而且**驗證了 v2 的產物確實能通過 APC 的落位檢查**——
在動任何架構之前先確認這件事。

**S1 — 16-bit 出口 + passthrough recipe。**
`io.rs:89-94` 加三個 colortype、`planar.rs` 加 `to_interleaved_u16`、
新增不做 PBR 轉換的 1:1 路徑。
驗收:同一張 16-bit alpha png,texproc passthrough 與 ImageMagick 的
tif 產物在位深/通道上等價(位元不必等,ImageMagick 有自己的 codec)。
價值:滿足「保留 alpha 與位深」裁定,取得取代 ImageMagick 主線的資格。

**S2 — crate 拆分 + Manager 連結分組。**
`texproc-core` 成形,Manager 用 `scan_inputs` 形成貼圖組 job 的
path-aware input manifest。此時**還沒有 worker**,job 由 Manager 就地執行。
驗收:同一批素材,APC 走 texproc 路徑產出的 tif 與 CLI 產物 SHA-256 相等
(T-B03 已有這個驗收手法的前例:GUI 與 CLI 抽三組比 hash)。

**S3 — worker daemon 連結轉換核心,宣告 `native/texture` 的 `prep-*` 旗標。**
`write_stage2_outputs` 換成暫存 + blob 引用,產物落位交 Manager。
驗收:一台 Linux 節點在沒有 rc 的情況下,接到並完成貼圖組 job。
這是 `m2a:48` 所說的「能力模型的第一次異構路由」。

**S4 — 長尾 fallback + CryTif 選配。**
非主線格式路由回 ImageMagick;`--write-crytif-settings` 供 stock 相容路徑。

---

## 6. 待決問題（提給業主,不自行裁決）

1. **能力家族的切法**:texproc 核心是 `native/texture` 的特性旗標(本文建議),
   還是獨立家族(例如 `native/texture-prep`)?
   影響路由的粒度與 M3 上線的分階可能性。

2. **PBR 轉換要不要進 build graph**——這是 (b) 與 (c) 的真正分水嶺。
   進了就能快取與增量,代價是 texproc 的發版被 toolchain identity 綁住。

3. **色彩工作域**:v2 是 encoded f32 + 兩個 linear island(D-03,為了與舊 Python
   版 ±1/255 相容)。**APC 沒有這個相容性包袱**,可以直接走 linear。
   要不要在 v3 改?改了輸出就與 v2 不等價,需要新的驗收基準
   (參照 `04_risk_review.md:30` 的「新舊產物 byte-diff 報告」手法)。

4. **metal gate 預設是否進 recipe**:它會改變輸出位元,且四個閾值目前是
   程式碼常數(`pipeline.rs:92-102`)。若不進 recipe/toolchain,
   就違反 `m2a:28` 的「不得悄悄改派」。傾向進 recipe。

5. **分組結果要不要持久化成 catalog 的一級概念**。
   目前 `ScanResult` 是暫態的。若貼圖組是常態的建置單位,
   catalog 可能需要「貼圖組」這個實體(而不是每次重掃)。
   這牽涉 `asset_products` 的綁定形狀(`00_design:124`),不是小改。

6. **converter(FBX/.mtl 線)怎麼辦**。本文只談 texproc。
   converter 與 APC 的 `assimp/scene`、glTF 線、以及 D8 材質縫有明顯重疊,
   應該另開一份筆記,不要混進貼圖線的討論。
