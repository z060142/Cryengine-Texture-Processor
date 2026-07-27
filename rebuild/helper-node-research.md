# Helper / Anchor 節點研究：FBX null/locator → CGF helper 的流向與我方保存狀況

研究性質：唯讀分析 + 一次實測探針（不改動產品程式碼）。所有結論皆附 `檔案:行號` 佐證。
日期：2026-07-27。探針對象：`rebuild/fixtures/car/car.fbx`（RC = `S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe`）。

---

## 結論摘要（先讀這段）

- **RC 會自動把「沒有 mesh 的節點」變成 CGF helper 節點**，判定純粹依「有無 mesh」，**與名稱無關**：`FbxConverter.cpp:1008` `pCGFNode->type = pCMesh ? NODE_MESH : NODE_HELPER`。預設 helperType = `HP_POINT`（`CGFContent.h:94`）。
- **我方轉換器目前已經保存 dummy/null**：`car.fbx` 的 meshless group null `KB3D_CEV_VehicSedan_A_grp` 完整走完 FBX→request→CGF，在輸出 CGF 中成為 **Helper chunk（0x1001）、type = HP_POINT**（見下方探針結果）。**此項不需修改即可運作**。
- `request.rs` 的 `is_helper`（名稱樣式 `_helper/_pivot/...`）**是死旗標**：除 `is_proxy` 外從未被消費（`request.rs:207-213` 定義、`request.rs:402` 只用 `is_proxy`），也**不需要**被消費，因為 RC 的 helper 判定不看名稱。
- 唯一潛在風險：若未來 GUI 讓使用者「勾選要匯入的節點」而產生**非空白名單**卻漏掉 null，該 null 會被丟棄（`FbxConverter.cpp:2013`）。目前我方輸出「全部節點」，無此風險。
- GUI 目前只顯示 `Meshes` 與 `Nodes` 兩個總數（`main.rs:1640-1641`），未標出 helper/null 數量。

---

## Q1：RC 的 FBX 路徑如何處理 meshless 節點？

### 1a. `nodes` 名單控制「納入/排除」——空白 = 全收，非空白 = 白名單

`CollectNodes()` 一開始：`const bool bSelectAllNodes = !bSkin && ir.nodes.empty();`（`FbxConverter.cpp:2013`），並以此初始化 `nodesToImport`（`FbxConverter.cpp:2018`）。

- **request 的 `nodes` 為空** → `bSelectAllNodes = true` → 場景**所有**節點（含 meshless null）都被匯入。
- **request 的 `nodes` 非空** → 初值 false，只有 `SelectRequestedNodesRecursively()`（`FbxConverter.cpp:2185-2206`）依 `path` 逐一比對命中的節點會被標記匯入（`nodesToImport[sceneNodeIndex] = true`，`FbxConverter.cpp:2198`）。比對用 `FindMatchingNodeInScene()`（`FbxConverter.cpp:708-735`，整條 path 逐段字串相等）。**path 找不到會直接報錯中止**：`RCLogError("Node %s is not found ...")`（`FbxConverter.cpp:2195`）。
- 因此「非空白 `nodes`」等同**白名單**：沒列進去的節點（含 null）不會出現在輸出。
- 節點 0（ufbx 合成 root / dummy root）永遠被丟棄：`nodesToImport[0] = false;`（`FbxConverter.cpp:2111`）。

### 1b. meshless 節點 → NODE_HELPER（自動、不看名稱）

在 `CreateCgfNodes()` 內，對每個被選入的節點嘗試 `BuildMesh()`；只有面數 > 0 時才建立 `pCMesh`（`FbxConverter.cpp:987-1003`），最終：

```
pCGFNode->type = pCMesh ? CNodeCGF::NODE_MESH : CNodeCGF::NODE_HELPER;   // FbxConverter.cpp:1008
```

- 沒有 mesh → `NODE_HELPER`。此時**未顯式設定 helperType**，沿用 `CNodeCGF` 建構子預設 `helperType = HP_POINT`（`CGFContent.h:94`）。
- 若是 physics proxy 或 LOD 幾何（有 mesh 但要當 helper），才改成 `HP_GEOMETRY`（`FbxConverter.cpp:1012-1016`）。

**沒有 `$` 前綴或 "dummy" 之類的名稱規則**參與此 FBX→CGF 的 helper 判定。節點名稱在轉換器內只影響兩件事：`ni.bPhysicsProxy = IsProxyFromName(...)`（`FbxConverter.cpp:2141`）與 `ni.lod = GetLodIndexFromName(...)`（`FbxConverter.cpp:2142`）。
（附帶：`$` / `$physics_proxy` 這類名稱規則是在**載入端** `CGFLoader.cpp:2384-2394` 才生效——`name[0]=='$'` 會被載入器強制當 helper。與 FBX 匯入端無關。）

### 1c. `ImportRequest.h` 的 `SNodeInfoType` 支援哪些 per-node 欄位？

`SNodeInfoType` 只有四個成員：`name`、`path`、`properties`、`children`（`ImportRequest.h:11-17`）。

反序列化時（`ImportRequest.cpp:22-45`）：
- `path`（來源場景定位）、`name`（輸出後改名），`ImportRequest.cpp:26-27`；
- **所有 per-node 物理欄位**（mass/density/dynamic/pieces/primitive/stiffness…）由 `CNodeProperties np; np.Serialize(ar);` 讀入（`ImportRequest.cpp:29-32`），再與 `udp`（user-defined properties）合併成一個 `properties` **字串**（`ImportRequest.cpp:35-42`）；
- `children`（子節點）`ImportRequest.cpp:44`。

也就是說：我方 `RequestNode` 那一長串 `mass/density/dynamic/...`（`request.rs:57-108`）在 RC 端**不是各自獨立欄位**，而是被 `CNodeProperties` 收集後烘成 CGF 節點的 `properties` 字串（`pCGFNode->properties = ...`，`FbxConverter.cpp:1018`）。對 helper/anchor 而言真正有用的是 `name`、`path` 與（若需要）`udp`。

---

## Q2：CGF 為 helper 存了什麼？下游如何讀取/使用？

### 資料結構
- `CNodeCGF`：`enum ENodeType { NODE_MESH, NODE_LIGHT, NODE_HELPER }`（`CGFContent.h:24-28`）、`HelperTypes helperType`、`Vec3 helperSize`（`CGFContent.h:45-46`），transform 存於 `localTM`/`worldTM`（`FbxConverter.cpp:957-958`）。
- `enum HelperTypes { HP_POINT=0, HP_DUMMY=1, HP_XREF=2, HP_CAMERA=3, HP_GEOMETRY=4 }`（`CryHeaders.h:1103-1110`）。
- Helper chunk 磁碟格式 `HELPER_CHUNK_DESC_0744 { HelperTypes type; Vec3 size; }`（`CryHeaders.h:1112-1120`）。Node chunk `NODE_CHUNK_DESC_0824`：`name[64]`、`ObjectID`、`ParentID`、`tm[4][4]`…（`CryHeaders.h:1068-1098`）。chunk 型別 `ChunkType_Node = 0x100B`、`ChunkType_Helper = 0x1001`（`CryHeaders.h:20-31`）。

### 寫入（Saver）
`CSaverCGF::SaveNode()`：`NODE_MESH` 或 `NODE_HELPER + HP_GEOMETRY` 走 `SaveNodeMesh()`；**其餘 NODE_HELPER（含 HP_POINT/HP_DUMMY）走 `SaveHelperChunk()`**（`CGFSaver.cpp:438-446`），即另存一個 Helper chunk。

### 讀取 / 使用（3DEngine 載入端）
- `CStatObj` 建立 SubObjects 時，`NODE_HELPER` 依 helperType 轉成對應 SubObject 型別：`HP_POINT → STATIC_SUB_OBJECT_POINT`、`HP_DUMMY → STATIC_SUB_OBJECT_DUMMY`（含 `helperSize`）、`HP_XREF/HP_CAMERA/HP_GEOMETRY` 各自對應（`StatObjLoad.cpp:990-1013`）。SubObject 保存 `name`、`tm = worldTM`、`localTM`、`properties`（`StatObjLoad.cpp:954-961`）。
- **依名稱查詢附著點**：`CStatObj::GetHelperPos(name)` / `GetHelperTM(name)` 透過 `FindSubObject(name)` 取回該 helper 的位移/transform（`StatObjConstr.cpp:384-405`）。物理/附著程式即以此定位，例如 `StatObjPhys.cpp:3159` `pHelpersHost->GetHelperPos(sname)`。

**結論**：一個 meshless FBX null 最終在遊戲端就是一個「可用名稱查到世界座標/transform 的附著點（HP_POINT sub-object）」。這正是 anchor 的預期行為。

---

## Q3：我方目前的鏈路

### model.rs——ufbx 場景樹是否含 meshless 節點？含。
`node_record()` 遞迴走訪 `node.children` 的**所有**子節點，不因無 mesh 而略過（`model.rs:273-284`）；`scene_tree = node_record(&scene.root_node)`（`model.rs:253`），`node_count = scene.nodes.count`（`model.rs:254`）。

實測 `dump car.fbx`：`counts = {materials:16, meshes:21, nodes:23}`。場景樹為：
```
<root, 合成>            ← ufbx 合成 root（未命名）
└─ KB3D_CEV_VehicSedan_A_grp   ← meshless group/null（21 個 mesh 的父節點）
   ├─ 21 個 mesh 節點 ...
```
故 **23 nodes vs 21 meshes 的「多出 2 個」= ①ufbx 合成 root（未命名）＋②`KB3D_CEV_VehicSedan_A_grp`（真正的 meshless null）**。此 null 即本題的決定性測試對象。

### request.rs——null 是否進入 request `nodes`？進入。
`build_import_request` 由 `model.scene_tree.children` 遞迴建 nodes（`request.rs:324-330`；丟棄合成 root，只從其 children 開始），`request_node()` 對每個子節點遞迴（`request.rs:354-391`）。因 scene_tree 已含 null，request 頂層即為 `[KB3D_CEV_VehicSedan_A_grp]`，其下掛 21 個 mesh。每個節點固定填 `mass=-1, density=-1`，其餘物理欄位與 `udp` 皆 `None`（`request.rs:366-388`）。

由於**我方輸出的 `nodes` 是「列出全部節點」的非空白名單**，RC 視其為白名單並精確匯入這些節點——null 在名單內，故被保留。

### is_helper 是否影響輸出 JSON？完全不影響（死旗標）。
`detect_node_type()` 計算 `is_lod/is_proxy/is_helper`（`request.rs:197-215`），但整個 crate 內**只有 `is_proxy` 被使用**（`request.rs:402`，用於 `collect_joint_physics`）。`is_helper`、`is_lod` 除單元測試外無任何消費點（全 repo grep：`request.rs` 190-213、402、653-657 皆為定義或測試）。因此 `is_helper` 不會被寫進 request，也不會被 strip——它從一開始就沒進 JSON。

### Python 參考對照
`process_node_hierarchy()` 只輸出 `name/path/nodes` 加內部旗標 `_is_proxy`（`rc_request_builder.py:117-139`）；`is_helper` 有算但**不寫入節點**（`rc_request_builder.py:58-59`）。`strip_internal_node_fields()` 移除 `_` 開頭鍵（`rc_request_builder.py:142-153`）。與 Rust 行為一致：helper 名稱旗標兩邊都是「算了但不用」。

---

## Q4：實測探針（決定性證據）

流程：`converter.exe convert car.fbx --manifest ...` → `rc.exe`（產生 CGF）→ 自寫拋棄式 Python 探針走 chunk table，列出 Node/Helper/Mesh chunk 並判定每個 Node 指向的物件型別。探針與臨時檔皆置於 `%TEMP%`，已於完成後刪除；RC 為同步呼叫，結束後無殘留行程。

**探針輸出（節錄）**：
```
REQUEST node names (22):  KB3D_CEV_VehicSedan_A_grp, <21 個 mesh 名> ...
RC returncode: 0   cgf exists: True

CHUNK TYPE HISTOGRAM:
  0x1000 Mesh   x21
  0x1001 Helper x1        ← 有 helper chunk
  0x100b Node   x22       ← grp + 21 mesh
  0x1014 MtlName x1, 0x1015 ExportFlags x1, 0x1016 DataStream x105, 0x1017 MeshSubsets x21, 0x1019 ImportSettings x1

NODE CHUNKS：
  KB3D_CEV_VehicSedan_A_grp   obj_id=3   HELPER(0x1001) HP_POINT   ← null 存活為 HP_POINT helper
  <其餘 21 個>                            MESH(0x1000)
SUMMARY: node_chunks=22 mesh_nodes=21 helper/nonmesh_nodes=1
```

**判定：meshless null `KB3D_CEV_VehicSedan_A_grp` 完整存活至輸出 CGF，成為 Helper chunk（0x1001）、type = HP_POINT，並保留節點名與 transform。** 我方現行轉換器**已可保存 dummy/anchor 節點**，無需另尋含 null 的 FBX 再測（car.fbx 本身即含真 null）。

---

## Q5：落差分析與實作意涵

### 基本保存：無需改動
FBX→request→CGF 的 dummy/anchor 保存**已運作**（Q4 實證）。核心原因是 RC 以「有無 mesh」而非名稱決定 helper（`FbxConverter.cpp:1008`），而我方 request 已把全部節點（含 null）列入白名單（`request.rs:324-330`）。

### 應遵守的慣例 / 注意事項
1. **命名即附著點名**：RC 不看名稱造 helper，故 helper 在遊戲端就叫 FBX null 的原名；`GetHelperPos()` 是**依名稱**查（`StatObjConstr.cpp:384-390`）。因此「anchor 要叫什麼」由美術在 FBX 端命名決定，遊戲程式再以同名查詢。我方 `detect_node_type` 的 `_helper/_pivot/...` 後綴對 RC 無意義且為死碼——**不要**誤以為改這些樣式能影響 helper 產出。
2. **白名單完整性**：目前輸出「全部節點」所以安全。若未來 GUI 加入「選擇性匯入節點」，**務必**讓 null/anchor 一併留在 `nodes` 名單，否則會被 `FbxConverter.cpp:2013/2185-2198` 的白名單邏輯排除（且漏列的 path 反而不會報錯，只是被略過）。
3. **UDP / properties（如需）**：若某些 anchor 需要把 user-defined properties 烘進 CGF 節點 `properties`（供遊戲端讀 `SSubObject.properties`），需在 request 節點填 `udp`（RC 端 `ImportRequest.cpp:29-42` 會收集）。目前一律 `None`（`request.rs:388`），一般 anchor 用不到。
4. **`$` 前綴的載入端特例**：若 null 以 `$` 開頭，`CGFLoader.cpp:2390` 載入時會另有強制 helper 行為；一般命名不必觸碰此路徑。

### GUI 應顯示什麼
目前 Model 面板只顯示 `Meshes: N`、`Nodes: node_count`（`main.rs:1640-1641`）。`node_count` 含合成 root，使用者無從得知有幾個 helper/null。建議（可選、低優先）：在 model summary 增列「Helper/anchor 節點數」＝概略以 `node_count − meshes − 1(合成 root)` 估算，或更精確地由轉換器輸出「meshless 節點清單」，讓使用者確認 anchor 有被辨識。此為顯示層增強，與保存正確性無關。

### 一句話總結
**不需要為了讓 dummy/anchor 存活而改產品程式碼**；現況已正確保存為 HP_POINT helper。可考慮的只有兩件「錦上添花」：GUI 標出 helper 數、以及（未來若做節點選擇性匯入時）確保 null 不被白名單漏掉。`is_helper` 名稱旗標可視為死碼，未來清理時可一併移除或改為僅供 GUI 統計用。
