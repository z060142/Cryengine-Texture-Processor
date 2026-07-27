# CGA 輸出研究：CryEngine RC FBX Importer 能不能產生 .cga？

日期：2026-07-27
性質：READ-ONLY 原始碼考古，未改任何程式碼、未 commit。
來源根目錄：`S:\Crytek\crytek\CRYENGINE_Source-release`（以下路徑皆相對此根）

## 結論先講（TL;DR）

**CryEngine RC 的 FBX importer（`FbxConverter` / JSON import request）無法產生 `.cga`。**
`output_ext` 白名單只接受 `cgf / chr / skin / caf / i_caf`；傳 `"cga"` 會被
`RCLogError("Unsupported output file format 'cga'.")` 直接拒絕
（`Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:2783-2790`）。

`.cga`（animated geometry，node-based rigid 動畫）在 CryEngine 屬於**舊 Collada（.dae）匯出管線**
（`ColladaCompiler.cpp` / `ColladaLoader.cpp` 的 `EXPORT_CGA` / `EXPORT_CGA_ANM`），
以及對「既有 .cga/.cgf 檔案就地編譯」的 `StatCGFCompiler`。這兩條路都**不吃我們產生的 FBX import request JSON**。

在 FBX 匯入這條路上，node/bone 動畫的產物是 **CAF（`caf` / `i_caf`）**，不是 CGA。

因此：**我們的 Rust converter 不應該把 `"cga"` 加進 RC import request 的 `output_ext`。** 加了只會被 RC 拒收。
下方逐題附證據，最後一節給實作建議（含「該做什麼、不該做什麼」）。

---

## Q1. FbxConverter 接受哪些 output extension？有沒有 "cga"？cga vs cgf 路徑差異？

### 接受的副檔名（不含 cga）

`Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:2783-2790`：

```cpp
if (ir.outputFilenameExt.compare("cgf") != 0
    && ir.outputFilenameExt.compare("chr") != 0
    && ir.outputFilenameExt.compare("skin") != 0
    && ir.outputFilenameExt.compare("caf") != 0
    && ir.outputFilenameExt.compare("i_caf") != 0)
{
    RCLogError("Unsupported output file format '%s'.", ir.outputFilenameExt.c_str());
    return false;
}
```

白名單 = `{cgf, chr, skin, caf, i_caf}`。**"cga" 不在其中**，會走進 error 分支回傳 false。
（`output_ext` 在讀取時被 `MakeLower()`，所以是 case-insensitive；`ImportRequest.cpp:137-138`。）

### FBX 管線內對 "cga" 的處理：無

在 `Code/Tools/RC/ResourceCompilerPC/FBX/` 目錄下對 "cga" 做 case-insensitive 搜尋，
唯一命中的是 include path（`#include "CGA/SkeletonHelpers.h"` 等，`FbxConverter.cpp:23,29,30`），
那是引用 `ResourceCompilerPC/CGA/` 動畫壓縮共用程式庫，**不是** cga 輸出分支。FBX 匯入器內沒有任何 `outputFilenameExt == "cga"` 的判斷。

### cga 在 RC 其他地方確實存在，但都不是 FBX 匯入路徑

- `Code/Tools/RC/rc.ini:12`：`cga,AnimatedMesh;anm,MeshAnimation` — RC 認得 cga/anm 為資產型別。
- `Code/Tools/RC/ResourceCompilerPC/ColladaLoader.cpp:2475-2486`：`EXPORT_CGA` / `EXPORT_CGA_ANM` — **Collada（.dae）** node export type 字串 `"cga"` / `"cgaanm"`。
- `Code/Tools/RC/ResourceCompilerPC/ColladaCompiler.cpp:499-529`：Collada 匯出時寫出 `.cga` 與 `.anm`。
- `Code/Tools/RC/ResourceCompilerPC/StatCGFCompiler.h:38` / `StatCGFCompiler.cpp:57`：`StatCGFCompiler` 把 `cga` 當**輸入**副檔名（就地編譯既有 .cga/.cgf），不是把 FBX 轉成 cga。
- `Code/Tools/RC/ResourceCompilerPC/StaticObjectCompiler.cpp:499`、`StatCGFPhysicalize.cpp:615,738`：對「已編譯 CGF/CGA」的 physicalize 分支（`bCga` 旗標），同樣作用在既有幾何檔上。

### cgf 路徑 vs（不存在的）cga 路徑差異

FBX 匯入的實際分派在 `CAsIsResultingScene::GetSceneType()`（`FbxConverter.cpp:813-829`）：

```cpp
if (ir.outputFilenameExt == "skin")            return ESceneType::Skin;
else if (ext == "chr" || ext == "skel")        return ESceneType::Skeleton;
else if (ext == "i_caf" || ext == "caf")       return ESceneType::Animation;
return ESceneType::Static;   // <- cgf 以及任何未列出的字串
```

`ESceneType` enum 只有 `Static / Skeleton / Skin / Animation`（`FbxConverter.cpp:764-770`），**沒有 CGA / AnimatedMesh 型別**。
`Save()` 的三向分派（`FbxConverter.cpp:884-895`）：`Skin→SaveToSkin`、`Animation→SaveToCaf`、其餘→`SaveToCgf`。
換言之，就算 whitelist 放行 "cga"，`GetSceneType` 也會把它當 `Static` 走 `SaveToCgf`，產出的其實是一個副檔名叫 .cga 的**靜態 CGF**、不含動畫——所以 FBX 路徑上沒有真正的 CGA（rigid node animation）產生器。

---

## Q2. 什麼觸發動畫匯出？animation block 是否必要？node transform 動畫會自動 bake 嗎？

**在 FBX 匯入路徑，「動畫」= CAF，不是 CGA。** 觸發條件是 `output_ext ∈ {caf, i_caf}`（→ `ESceneType::Animation` → `SaveToCaf`），
`FbxConverter.cpp:823-825, 836, 888-890`。

### `animation` block 是否必要？

不是強制。`SetAnimationStack()`（`FbxConverter.cpp:1680-1712`）行為：

```cpp
int animationStackIndex = 0;
if (!ir.animation.name.empty()) {                 // 有給 name 才查找
    animationStackIndex = GetAnimationStackIndex(ir.animation.name);
    if (animationStackIndex < 0) { /* error + LogAnimationStacks */ return false; }
}
if (!m_pScene->GetAnimationStackCount()) { /* static pose ... */ }   // FBX 無動畫 → 靜態 pose
...
startFrame = ir.animation.startFrame >= 0 ? Clamp(ir.animation.startFrame, stack.start, stack.end) : stack.start;
endFrame   = ir.animation.endFrame   >= 0 ? Clamp(ir.animation.endFrame,   startFrame,  stack.end) : stack.end;
```

- `animation.name` 空 → 預設用**第 0 個 animation stack**。
- `startFrame/endFrame` = -1（constructor 預設，`ImportRequest.h:84-85`）→ 用該 stack 的完整範圍。
- 所以對 caf/i_caf，**request 可以完全不帶 `animation` 物件**，RC 會拿第一個 stack 的全長。`animation` block 是可選的 override，不是必要條件。

### node transform 動畫是否自動 bake？

是，從 FBX timeline 逐 frame 取樣 bake。`SaveToICaf()`（`FbxConverter.cpp:1795-1907`）針對每個 bone/node
逐 frame（`for (int frame = startFrame; frame <= endFrame; ++frame)`）取 local transform 存成 controller，
再由 `SaveToCaf()`（`1722-1793`）跑 `CAnimationCompressor` i_caf→caf 壓縮。取樣假設固定 30fps（`ImportRequest.h:30` 註解）。

### 「nodes」section 有無 per-node 控制動畫節點納入的旗標？

沒有專屬旗標。`SNodeInfoType` 只有 `path / name / properties(udp) / children`（`ImportRequest.cpp:22-44`）——
用來挑選/改名要匯入的節點與掛 user-defined properties，**沒有 "animated" 之類開關**。
哪些 node 被寫入動畫由 skinning info（bone/skeleton）決定，不是靠 nodes section 的旗標。

---

## Q3. SAnimation 欄位語意（name / motionNodePath / startFrame / endFrame）

定義：`ImportRequest.h:26-32`；序列化：`ImportRequest.cpp:88-95`。

- **name**：FBX animation stack 名稱（`"FBX Animation Stack Name"`）。空 → 用 stack index 0；給了但找不到 → error 並列出可用 stacks（`FbxConverter.cpp:1684-1691, 1670-1677`）。
- **motionNodePath**：`std::vector<string>`，「derive character's motion from」的節點路徑。實際使用在 `SaveToCaf`：
  `const char* szMotionNodeName = !ir.animation.motionNodePath.empty() ? ir.animation.motionNodePath.back() : "";`
  （`FbxConverter.cpp:1761`）——取路徑**最後一段**當作 root motion node 名稱，餵給 CAF 壓縮器決定角色位移（locomotion）來源。空則無 root motion node。
- **startFrame / endFrame**：以 frame 表示（假設 30fps，`ImportRequest.h:30`）。預設 -1（`ImportRequest.h:84-85`）代表「用 stack 全長」。給正值時會被 `Clamp` 進 stack 邊界（`FbxConverter.cpp:1709-1710`）。
- **能否多個 animation entry？** 不行。`CImportRequest` 內是**單一** `SAnimation animation;`（`ImportRequest.h:121`），不是 vector。一個 request 只能匯出一段動畫。要多段就得多個 request（多次 RC 呼叫）。

---

## Q4. CGA 會不會另外產生 .anm？還是動畫內嵌在 .cga？

對 **FBX 匯入資產：兩者皆非**——FBX 路徑根本不產 cga/anm，只產 CAF（動畫內嵌於 .caf；bone controller chunk 見 `FbxConverter.cpp:1795-1907`）。

`.anm` 只存在於 **Collada 管線**：`ColladaLoader.h:88-92` 定義 `EXPORT_CGA` 與 `EXPORT_CGA_ANM`；
`ColladaCompiler.cpp:499-529` 對 `EXPORT_CGA` 寫 `.cga`、對其動畫 track 寫 `.anm`（`PathUtil::ReplaceExtension(exportFileName,"anm")`, line 529）。
也就是「`.cga` 幾何 + 伴隨 `.anm` node 動畫」是 Collada 時代 rigid 動畫幾何的作法。
在 `Code/Tools/RC/ResourceCompilerPC/FBX/` 目錄對 `.anm` / `"anm"` 搜尋**無任何命中**（FBX 管線不碰 anm）。

---

## Q5. CGA 對我們 converter 有哪些約束（merge_all_nodes / scene_origin / hierarchy / LOD）？

因為 FBX importer 不支援 cga，**「CGA 專屬約束」在 FBX request 這條路上不存在**——沒有可設的合法 cga request。
與動畫（CAF）相關、我們仍需注意的約束：

- **merge_all_nodes**：CAF 動畫依賴 skinning/bone 節點結構。若 `merge_all_nodes=true` 會把節點合併，破壞逐節點動畫的前提；動畫輸出應維持 `merge_all_nodes=false`。（旗標定義 `ImportRequest.cpp:160`，`bMergeAllNodes` 影響 `CExportInfoCGF`，`FbxConverter.cpp:851`。）
- **scene_origin**：`bSceneOrigin` 僅在 `!nodes.empty()` 時生效（`ImportRequest.h:109` 註解），控制用 scene 原點或各 root node 原點（`ImportRequest.cpp:161`），套用於 `ComputeNodeTransforms(ir.bSceneOrigin)`（`FbxConverter.cpp:843`）。
- **root bone 限制**：動畫對 root bone 有正交/無初始位移的要求——`SaveToICaf` 有 `nontrivialRoot` 檢查，root 若含 translation/scale 或非正交，node 動畫可能不正常（`FbxConverter.cpp:1842-1862` 附近註解）。
- **LOD**：`NodeInfo.lod`（`FbxConverter.cpp:779,793`）在靜態 CGF 才有意義；動畫（Animation/Skeleton）路徑不走 LOD 分支（`FbxConverter.cpp:1454` 對 Skeleton/Animation 另行處理）。CAF 不需要 LOD。

---

## Q6. Sandbox FBX importer UI 怎麼選 CGA？產生的 request/metadata 長怎樣？

**Sandbox（MeshImporter plugin）UI 完全不提供 CGA 輸出。** 對整個
`Code/Sandbox/Plugins/MeshImporter` 搜 "cga" **零命中**。
所有 `outputFileExt` 的設定點只會是 `cgf / chr / skin / caf`：

- `AssetImporterFBX.cpp:507("cgf"),524("chr"),561("skin"),604("caf")`
- `DialogCAF.cpp:811("caf"),825("chr"),833("skin")`
- `DialogCHR.cpp:973("chr"),993("skin"),1002("cgf")`
- `GenerateCharacter.cpp:256("chr"),262("skin"),277("caf")`
- `MainDialog.cpp:2828("cgf"),3295("skin")`

metadata 序列化欄位為 `output_ext`（`FbxMetaData.cpp:138`，欄位 `outputFileExt`，`FbxMetaData.h:181`），
最終透過 `CRcCaller::OptionOverwriteFilename(...ReplaceExtension(filename, metaData.outputFileExt))` 交給 RC
（`AssetImporterFBX.cpp:171`）。UI 從不填 "cga"，所以生出的 request/metadata 的 `output_ext` 永遠是那四種之一——**沒有 CGA 對應的 UI 或 metadata 範本可參考**。

（旁證：`MetadataCompiler.cpp:316,384` 把 cga 與 cgf/skin 並列做 metadata，但那是針對「已經存在的 .cga 檔」產 .cryasset metadata，與 FBX 匯入無關。）

---

## 對我們 converter 的實作意涵（implementation implications）

### 最重要：不要加 "cga" 到 `output_ext`

- **不要**把 `"cga"` 放進 `RC_IMPORT_OUTPUT_EXTENSIONS`（目前 `output_formats/rc_import_schema.py:129` 是 `{cgf, chr, skin, caf, i_caf}`，**與 source 一致，正確**）。加了 RC 會回 `Unsupported output file format 'cga'` 而失敗。
- 若產品面確實要「animated geometry」輸出，正解不是 cga，而是 **caf/i_caf 動畫路徑**（bone/skinned 動畫）。真正的 rigid-body CGA 需要 Collada(.dae) 匯出器或直接產出 .cga 檔再就地編譯，**不在 FBX import request 能力範圍內**——這是一個「該不該存在」層級的取捨，建議直接砍掉 CGA 選項，只做 CGF（靜態）與 CAF（動畫）。

### 若要支援 CAF（動畫）輸出，需新增/推導的欄位

RC request 端已由 `rc_import_schema.py` 覆蓋 `animation` 物件（Phase 82）。要真的產動畫 request：

1. `output_ext` 設 `"caf"`（壓縮成品）或 `"i_caf"`（中間未壓縮）。
2. `animation` 物件（全部可選，省略則取第 0 個 stack 全長）：
   - `name`：對應 FBX animation stack 名。可由 ufbx 的 `ufbx_scene.anim_stacks[i].name` 取得。
   - `startFrame` / `endFrame`：省略/`-1` = 用 stack 全長（建議預設就這樣，最省事）。要換算 frame：`frame = time * 30`（source 假設 30fps）。
   - `motionNodePath`：root motion 節點路徑（陣列，取 `.back()`）。無 root motion 需求就留空。
3. 維持 `merge_all_nodes=false`（動畫需要節點結構）。

### FBX 是否「有動畫」的偵測 heuristic（ufbx）

用 ufbx anim stacks 判斷：`scene.anim_stacks.count > 0` 且該 stack 內有非空 `ufbx_anim_layer` / 節點有 transform anim curves。
- 有 anim stack → 可提供 CAF 輸出（若同時有 skin/bone 則走 skinned；純節點剛體動畫在 FBX 路徑仍只能落到 CAF 的 node controller，不是 CGA）。
- 無 anim stack → 只提供 CGF（`SetAnimationStack` 也會在 stack count 為 0 時退化成 static pose，`FbxConverter.cpp:1695-1701`）。

### GUI 輸出型別選擇器

建議 **Auto / CGF / CAF**（**不要放 CGA**）：
- **Auto**：偵測 ufbx anim stacks——有動畫且使用者想要動畫 → CAF；否則 CGF。
- **CGF**：靜態幾何（`output_ext="cgf"`，`ESceneType::Static`）。
- **CAF**：動畫（`output_ext="caf"`），帶可選 `animation` block。
- 如果為了對齊使用者心智模型硬要出現「CGA」字樣，也應在 UI 明說「FBX 匯入不支援 CGA，動畫請用 CAF」，避免產出必然被 RC 拒收的 request。

### 一句話總結

RC FBX importer 的 5 種合法 `output_ext` 沒有 cga；CGA 是 Collada/就地編譯路徑的產物。
我們的 converter 對「animated geometry」的正確對應是 **CAF**，schema 現況正確、**不需也不應**新增 cga。
