# CE Sandbox Mesh Importer：二次開啟/導入時 material 被前次儲存值污染 — 源碼調查

> 2026-07-29。業主回報：同一 Sandbox 工作階段中，第二次、第三次開啟或導入
> FBX 時，無論再導入（應顯示該模型原本設定的 material）或新導入（應可生成
> 新 material），material 欄始終被填入**前一次儲存模型時**設定的 material。
> 源碼：`S:\Crytek\crytek\CRYENGINE_Source-release`（5.7 系）。

## 結論（TL;DR）

三個相互疊加的缺陷，主犯是 #1：

1. **再導入路徑刻意繞過 json，改讀 session 快取的 StatObj**
   （`MeshImporter/MainDialog.cpp:3041-3054`）——而 3DEngine 的 StatObj
   名字快取**命中即回、永不重讀磁碟**（`Cry3DEngine/ObjMan.cpp:666,717`）。
   第二次開啟同一資產時，讀到的是「第一次載入當下」的 material 狀態 =
   前一次儲存時的值；本階段剛存的新設定（json 裡是對的）被無視。
2. **「Generate material」對既存同名材質直接整顆重用、跳過初始化**
   （`MeshImporter/CreateMaterialTask.cpp:186-199`）——新導入想生成新
   material 時，若選到的 mtl 名已在本階段的 MaterialManager 快取中
   （前一個模型剛存過的名字；存檔對話框又會預填上次的名字），就原樣
   回傳前一個模型的 material，不做 `InitializeMaterial`。
3. **正確的填入路徑存在但是死碼**（`MeshImporter/MaterialPanel.cpp:58`
   會從 `pPayload->pMetaData->materialFilename` 填入）——唯一呼叫點
   `MainDialog.cpp:2193` 傳的是 `nullptr/*pPayload*/`，旁邊就掛著
   `// TODO: fix it, currently pPayload is processed in ApplyMetaData.`

## 證據鏈

### 1. 再導入（開啟既有資產）的 material 填入來源

開啟流程：`DialogCommon.cpp:493 CBaseDialog::Open` → 從 cgf 的
`ChunkType_ImportSettings` chunk 讀 json metadata（`MainDialog.cpp:1544
ReadMetaDataFromFile`，此值**正確**，含 `materialFilename`）→ payload 進
`AssignScene` → `ApplyMetaData` → `ApplyMetaDataCommon`：

```cpp
// MainDialog.cpp:3041-3054
{
    // We read the material from the StatObj instead of the json, so that we get a fully qualified
    // name (i.e., the StatObj loading does the lookup).
    const string targetFilePath = PathUtil::Make(PathUtil::GetGameProjectAssetsPath(), GetTargetFilePath());
    IStatObj* const pTarget = GetIEditor()->Get3DEngine()->LoadStatObj(targetFilePath.c_str(), NULL, NULL, false);
    const string materialName = pTarget->GetMaterial() ? PathUtil::ToGamePath(pTarget->GetMaterial()->GetName()) : string();
    m_bMaterialNameWasRelative = materialName != metaData.materialFilename;
    m_pMaterialPanel->GetMaterialSettings()->SetMaterial(materialName);
    ...
}
```

json 的 `metaData.materialFilename` 被丟棄，改信 `LoadStatObj` 的結果。而：

```cpp
// Cry3DEngine/ObjMan.cpp:659-721（節錄）
SLoadPrepareState prepState = LoadStatObj_Prepare(szFileName, ...);  // 查 m_nameToObjectMap
CStatObj* pObject = prepState.pObject;
if (pObject) { /* 快取命中：只調 streaming/LOD，完全不重讀 cgf */ }
else { /* 第一次才 LoadCGF，然後 m_nameToObjectMap[m_szFileName] = pObject; */ }
```

**時序重現**：
1. 開啟 T.cgf（本階段第一次）→ `LoadStatObj(T)` 首載 → 快取；material 欄
   顯示磁碟上的值（= 上次儲存的設定）——此時看起來正常。
2. 改 material 為 M2，儲存 → RC 重編 T.cgf，磁碟與 json 都是 M2；
   **記憶體快取的 CStatObj 不會失效**（RC 是外部行程）。
3. 再次開啟 T.cgf（第二次）→ json 讀出 M2（正確）→ 但 3044 行
   `LoadStatObj(T)` 快取命中 → 回第 1 步狀態的物件 → 填入**前一次儲存的
   material**。第三次、第四次同理，永遠慢一拍。

註：載入失敗時回傳共享的 `m_pDefaultCGF`（ObjMan.cpp:702）再取其
material，是同段程式的次要風險。

### 2. 新導入 + Generate material 的重用缺陷

```cpp
// CreateMaterialTask.cpp:186-199（SelectNewMaterial 對話框路徑）
CMaterialManager* const pMaterialManager = GetIEditor()->GetMaterialManager();
m_pMaterial = (CMaterial*)pMaterialManager->FindItemByName(materialItemName.c_str());
if (!m_pMaterial)
{
    // Create new material.（只有找不到才建新；找到就整顆沿用，
    // 不跑 InitializeMaterial / CreateMaterial(pScene) 初始化）
    ...
}
```

前一個模型儲存過的 material 整個 session 都掛在編輯器 MaterialManager
裡；`SelectNewMaterial`（`CEngineFileDialog::RunGameSave`）的存檔對話框會
預填/延續上次的檔名，使用者直接按確認 → `FindItemByName` 命中 → 新模型
拿到**前一個模型的 material 物件**。與缺陷 1 疊加後，使用者觀感即
「無論怎麼導入都是上一次存的 material」。

（對照：同函式 201-210 行的顯式路徑 else 分支永遠 `CreateMaterial`，
兩個分支行為不一致，可見 186 行的快取命中並非深思熟慮的設計。）

### 3. 死碼：payload 沒交給 MaterialPanel

```cpp
// MaterialPanel.cpp:49-59 —— 正確的實作，從 json 填 material：
const string materialName = (pPayload && pPayload->pMetaData) ? pPayload->pMetaData->materialFilename : "";
m_pMaterialSettings->SetMaterial(materialName);

// MainDialog.cpp:2192-2193 —— 唯一呼叫點卻傳 nullptr：
// TODO: fix it, currently pPayload is processed in ApplyMetaData.
m_pMaterialPanel->AssignScene(nullptr/*pPayload*/);
```

## 修法建議（如自建 Sandbox 或提報 Crytek）

最小修正（root cause）：`ApplyMetaDataCommon` 改以 json 為權威——

```cpp
string materialName = metaData.materialFilename;
// 相對名（儲存時經 MakeMaterialNameRelative 剝目錄）就地解析回全名，
// 不需要 StatObj：
if (!materialName.empty() && 相對) {
    materialName = PathUtil::Make(PathUtil::GetPathWithoutFilename(GetTargetFilePath()), materialName);
    m_bMaterialNameWasRelative = true;
}
m_pMaterialPanel->GetMaterialSettings()->SetMaterial(materialName);
```

3041 行的註解說明繞道 StatObj 只是為了把相對名解析成全名——這件事用
cgf 所在目錄拼路徑即可完成，無須經過（會過期的）物件快取。若堅持走
StatObj，讀取前必須 `ReloadObject`/失效化該路徑的快取。

配套：`CreateMaterialTask` 在 `FindItemByName` 命中時，仍應以當前 FBX
場景重新初始化 sub-materials（或至少提示將覆蓋/沿用），並從磁碟
`Reload` 該 material，避免沿用前一模型的記憶體狀態。

## 對本專案（texproc/converter）的含意

我們的 Rust 工具鏈不經過 Sandbox 這條路（.mtl + RC 請求 json 直出），
不受此 bug 影響；但**驗證產物時**若在同一個 Sandbox 工作階段反覆開啟
同一 cgf 察看 material，看到的可能是快取殘影——確認 material 是否正確
應以磁碟上的 .mtl / cgf chunk 為準，或重啟 Sandbox 再開。
