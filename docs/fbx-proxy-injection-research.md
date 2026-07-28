# 研究案：碰撞代理網格以最小侵入方式注入 FBX 並導出

> 2026-07-29。前期研究，暫不進程式。業主自研碰撞代理網格演算法，需要一條
> 「對原始 FBX 影響最小」的路：把算出的碰撞網格作為額外 node 合併進去、
> 掛 proxy 子材質、導出新 FBX。json 請求規則之後再訂（業主裁示），本文
> 聚焦 FBX 導出本身。

## 1. 結論（TL;DR）

**建議：以「非語意 raw tree 編輯」實作——解析 FBX binary 的節點樹但不解讀
內容，未觸碰的子樹逐位元組原樣複製，只追加 proxy 所需的最小節點集與
連線，重算偏移後寫出。** 這是唯一能保證「原始內容零損失」的路線；任何
經過語意化 importer 的往返（FBX SDK、Assimp、Blender）都有正規化/丟失
未知資料的風險。Rust 生態有現成低階件（`fbxcel`），也可自寫（格式簡單，
約數百行，僅需 flate2 解壓即可全免——未觸碰的壓縮陣列**連解壓都不必**，
原始位元組直接搬運）。

注入一個 proxy mesh node 的最小 delta 僅四類：`Objects` 下 3 個新節點
（Geometry/Model/Material）、`Connections` 下 3 條連線、`Definitions`
計數 +1（advisory）、全檔偏移重算。其餘內容（動畫、自訂屬性、
嵌入貼圖、未知 chunk）完全不動。

## 2. FBX binary 格式要點（7.4 / 7.5）

- Header：21 bytes magic `"Kaydara FBX Binary  \x00"` + `1A 00` + u32 版本
  （7400 / 7500）。
- 節點記錄（7400）：`EndOffset:u32, NumProperties:u32, PropertyListLen:u32,
  NameLen:u8, Name` → 屬性串 → 子節點串 → 13-byte 空記錄結尾。
  **7500 起（含 7700）改為 u64×3 + 25-byte 空記錄**——讀寫必須按版本
  分派。實測手邊 fixture：car.fbx = 7400（u32 世代）、KB3D = 7700
  （u64 世代），兩代都必須支援、也都有現成測材。
- 屬性記錄：型別碼 `Y C I F D L`（純量）、`f d l i b`（陣列：
  `ArrayLength:u32, Encoding:u32(0=raw,1=zlib), CompressedLength:u32, data`）、
  `S R`（長度前綴）。**陣列可 zlib 壓縮——pass-through 時不解壓、
  原樣複製即可**；只有我們新寫入的陣列需要編碼（用 raw encoding=0
  最省事，FBX SDK/ufbx 都接受）。
- 尾部：頂層以空記錄結束後接 footer——16-byte footer id（讀取端不驗證，
  Blender 的純 Python 匯出器寫固定常數即通行）+ 對齊補零 + 版本重複 +
  120 零 + 固定 magic。照 Blender 的寫法即可。
- `EndOffset` 是**絕對檔案偏移** → 任何插入都需重算所有祖先與後續節點
  的偏移。這正是「raw tree 全量重寫」而非「就地 patch」的原因；但重寫
  時每個未觸碰節點的名稱、屬性 payload、子樹皆可位元組級原樣搬運，
  語意零風險。

## 3. 注入 proxy node 的最小 delta（7.x Objects/Connections 模型）

以既有檔案為底，追加：

1. `Objects/Geometry`（id=新唯一 int64）：
   - `Vertices`（d 陣列，xyz 平鋪）
   - `PolygonVertexIndex`（i 陣列，每面最後一索引取 `^-1`；碰撞網格
     建議全三角）
   - `LayerElementMaterial`：`MappingInformationType="AllSame"`、
     `ReferenceInformationType="IndexToDirect"`、`Materials=[0]`
   - `Layer 0` 綁定元素。Normal 層可省（RC 物理化不需要；FBX SDK
     容忍無 normal）。
2. `Objects/Model`（"Mesh" 子型別）：節點名採 **RC 保留前綴**（見 §5）；
   頂點若以父節點區域座標編寫，`Properties70` 的 Lcl T/R/S 可全省
   （預設 identity）。
3. `Objects/Material`：proxy 子材質，最小 Lambert `Properties70`
   （DiffuseColor 隨意）。若之後改走 json `physicalize: "proxy_only"`
   路線，這顆材質就是請求裡點名的對象。
4. `Connections`：`C "OO" <modelId> <parentModelId>`（proxy 掛在被代理
   的 render node 之下，見 §5）、`C "OO" <geoId> <modelId>`、
   `C "OO" <matId> <modelId>`。
5. `Definitions`：`ObjectType Model/Geometry/Material` 的 `Count` +1。
   計數是 advisory（FBX SDK / ufbx / Blender 實測都不因不符拒讀），
   但既然改動廉價就同步。
6. ID 配置：掃描既有全部 int64 id，取不衝突值（max+N 即可）。

## 4. 寫出途徑盤點

| 途徑 | 保真 | 依賴/授權 | 評估 |
|---|---|---|---|
| **A. 自寫 raw tree 讀寫器（建議）** | 未觸碰子樹位元組級原樣 | 零新依賴（新陣列用 raw encoding 連 zlib 都免） | 格式簡單（§2），估數百行 Rust；風險集中在 7.4/7.5 分派與 footer，皆有 Blender 純 Python 實作可對照 |
| B. `fbxcel` crate | tree 級（陣列會解碼重編，語意等價、位元組未必相同） | MIT/Apache，新依賴 | 現成 7400 tokenizer+writer；若不想自寫可用，屬「語意保真」級 |
| C. FBX SDK 小工具（C++ 旁路） | SDK 語意保真；會全檔正規化 | Autodesk 專有授權、C++ 建置負擔 | RC/Sandbox 同源，讀回相容性最穩；但違反「最小侵入」——SDK 重寫全檔且可能重排/重算資料，也違反本專案零外部執行檔哲學 |
| D. 轉 ASCII FBX 再改寫 | 全檔換容器格式 | — | 侵入最大，否決 |
| E. ufbx | — | — | **只讀不寫**，無此選項（現有 converter 的載入端不變） |

補充：ufbx 作為**驗證端**非常有用——注入後用現有 converter `dump` 讀回，
與注入前 dump 比對「除新增節點外零差異」，即為最小侵入的機器可驗證
定義（我們已有 dump 黃金比對的全部工具鏈）。

## 5. CE/RC 端 proxy 慣例（注入節點怎麼寫才會被吃對）

源碼證據（`Code\Tools\RC\ResourceCompilerPC\FBX\FbxConverter.cpp`、
`CGFContent.h`）：

1. **節點名路線（免 json 規則，建議先走這條）**：`IsProxyFromName`
   （FbxConverter.cpp:1994）對節點名做**前綴**匹配（大小寫不敏感），
   保留名：`PhysicsProxy` / `$collision` / `$physics_proxy`
   （CGFContent.h:17-19）。命中即 `bPhysicsProxy=true`
   （FbxConverter.cpp:2141）。
2. **父子與變換**：proxy 節點應作為**被代理 render node 的子節點**；
   RC 對 proxy 套用「in place of parents LOD0」規則——
   `ni.world = m_nodes[ni.parentNode].world`（proxy 自身的 local
   transform 被忽略，直接用父節點世界變換）→ **代理網格頂點必須以
   父節點區域座標編寫**，Model 的 Lcl T/R/S 寫 identity 即可。
3. proxy 節點的 UDP/properties 會被丟棄（`ni.pProperties = nullptr`，
   FbxConverter.cpp:1012-1015）——別把資訊藏在 proxy 節點屬性裡。
4. **材質路線（之後配 json 用）**：請求 `physicalize: "proxy_only"` →
   `PHYS_GEOM_TYPE_DEFAULT_PROXY`（ImportRequest.cpp:72-75）→ 該子材質
   除渲染、留物理（FbxConverter.cpp:133-150：`m_renderMatIds[i]=-1`）。
   與名字路線疊加無害；proxy 子材質同時是 Sandbox 裡人類可讀的標記。
5. CGF 物理化本身按材質 `nPhysicalizeType` 落到 mesh subset
   （FbxConverter.cpp:484）——所以就算走名字路線，proxy node 掛一顆
   獨立子材質仍是乾淨做法（subset 邊界清楚，之後 json 點名也方便）。

## 6. 建議的下一步（進票時的驗收設計）

1. 原型：手寫 raw tree reader/writer（或 fbxcel spike），對 `car.fbx`
   做 **identity 往返**（讀→寫，零修改），驗證：ufbx dump 位元組級一致、
   RC 可轉換、（如可）FBX SDK 讀通。這一步先證明容器往返無損。
2. 注入 spike：塞一顆單位立方 `$physics_proxy` node 到某 render node 下
   → RC 轉 CGF → CGF chunk 探針（既有工具）驗證 proxy subset 存在、
   render subset 不含它；Sandbox 開啟目測。
3. 驗收錨點候選：identity 往返 dump 全等；注入後 dump 差異僅限新節點；
   RC 轉換零警告；u32 與 u64 兩代各一個 fixture（car.fbx=7400、
   KB3D=7700，皆已在庫）。
4. 業主演算法就緒後再訂：頂點座標空間約定（父節點區域座標）、多 proxy
   命名（`$physics_proxy_01…`）、json 規則（materialFilename/sub_index）。

## 7. 風險與未定事項

- FBX SDK 對注入檔的容忍度未實測（ufbx/RC 是主要消費者，但美術可能把
  新 FBX 拖回 DCC）——步驟 2 應加一個 Maya/Max/Blender 開檔煙測。
- 嵌入貼圖（Video/Content 大 blob）與巨型場景：pass-through 設計天然
  不碰它們，但寫出時是全檔複製，I/O 成本 = 檔案大小，可接受。
- ~~7.5（u64）檔的 fixture 來源待找~~ → 已解決：KB3D 全系即 7700
  （u64 世代），car.fbx 補 7400 面；`fbxcel` 若走 B 案需確認其對
  7700 的支援程度（其文件主打 7400/7500）。
- ASCII FBX 輸入：本管線不支援注入（維持只認 binary），遇到再說。
