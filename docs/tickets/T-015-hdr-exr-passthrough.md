# T-015 — HDR/EXR 特例：跳過 TIF 管線直送 RC（cubemap HDR）

狀態：DONE（審查通過 2026-07-27；審查者獨立重跑全部錨點 + CLI JSON 往返補測）
業主裁決（2026-07-27）：
- `.hdr` **不做 TIF 轉換**，直接送 RC；RC 端將其作 cubemap HDR 轉換
  （HDR 在 CryEngine/RC 內本身就是特例格式）。
- `.exr` **先轉成 `.hdr`**，之後走與 `.hdr` 相同的路（送 RC）。
- **不在程式裡特別標注特例**（不加新 UI 面板/標籤/型別徽章）——「借道一走」：
  沿用既有掃描→處理→DDS→清理流程。
- 勾選「導出 DDS 後刪除 TIF」時**順便刪除**送 RC 的 `.hdr`。

## 工作內容

1. **掃描收編 hdr**：`texproc/src/grouping.rs` `SUPPORTED_EXTENSIONS` 加入
   `"hdr"`（`exr` 已在）。hdr/exr 檔多半無型別後綴（環境貼圖），會落到
   unknown/unassigned——特例路徑**不得**因 unknown 分類被跳過或觸發
   exit 3；以副檔名分流，早於型別判定。
2. **處理階段分流**（texproc lib，batch/output 層）：
   - `.hdr` 輸入 → 原樣**複製**到輸出目錄（不進 f32 管線、不出 TIF）。
   - `.exr` 輸入 → 解碼（image crate `exr` feature 已啟用）→ 以 Radiance HDR
     編碼寫出 `<stem>.hdr` 到輸出目錄（image crate 加 `hdr` feature，
     `HdrEncoder`/`Rgb<f32>`；**不新增依賴條目**，只加既有 image 的 feature）。
   - 兩者記入該批次報告的 `written` 清單（與 TIF 產出同列）。
   - **exr 全面改道**：本票後 `.exr` 不再進 TIF 管線（既有 exr-as-PBR-texture
     行為由此廢止）。此為業主整格式裁決；若日後遇到 exr 材質貼圖壞案例，
     與 metal gate 同政策——遇壞案例再修。
3. **DDS 佇列**：`texproc-gui/src/worker.rs` `dds_jobs()` 篩選由僅 `tif`
   擴為 `tif|hdr`。`run_dds_pool` 的 RC 呼叫對 hdr 沿用同一形式；**必須先以
   真 RC 驗證**（見驗收 3），若 hdr 需要額外旗標（如 preset），只對 hdr
   工作附加，TIF 呼叫不得變動。
4. **清理借道**：`delete_tif` 分支（worker.rs ~413，「刪 RC 消費的產出檔」
   語意）擴為同時刪除 DDS 成功後的 `.hdr`。**只刪輸出目錄裡的暫存/產出
   hdr；使用者的原始 `.hdr`/`.exr` 一律不動**（.hdr 直通靠「複製到輸出目錄」
   保證此語意）。GUI 選項文字不改。
5. **CLI 契約凍結**：不加子命令/旗標。`texproc process` 對 hdr/exr 的行為
   即上述分流；scan JSON 若需帶出這些檔案，沿用既有欄位結構。

## 驗收錨點

1. 單元：exr→hdr 轉換往返（合成小圖：已知 f32 值寫 exr → 走轉換 → 解回
   hdr 驗值，容差按 RGBE 編碼精度）；hdr 直通為位元相同複製。
2. 整合：混合輸入目錄（png 組 + 一個 .hdr + 一個 .exr）跑 scan→process：
   png 組照常出 TIF；hdr/exr 各出一個輸出目錄 .hdr；無 exit 3。
3. **真 RC 驗證**（RC 在 `S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe`）：
   取一張真實 .hdr（KB3D/素材庫找，找不到就合成）經新路徑送 RC，確認產出
   DDS 且為 cubemap/HDR 格式（DDS header 探針：cubemap caps 或 BC6H/HDR
   格式）；把實際使用的 RC 命令列與 DDS header 摘要記回本票。
4. 清理：delete_tif=true 時，DDS 成功後輸出目錄的 .tif 與 .hdr 均被刪，
   原始輸入目錄檔案不動（測試斷言兩者）。
5. `run_gates.ps1` 全綠（既有 golden 零影響——smoke 輸入無 hdr/exr）。

## 明確禁止

- 不新增依賴（image feature 除外）。不動 CLI 旗標。不動 TIF 的 RC 呼叫。
- 不做 UI 新面板/新選項/新標籤。
- 不刪使用者原始輸入檔。

## DoD

- 上述錨點全數通過；回報：分流實作位置、RC 對 hdr 的實際命令列與
  DDS header 證據、exr→hdr 精度測試數據。

## 實作紀錄（2026-07-27，Miss Fox）

狀態：DONE。`run_gates.ps1` 全綠（含 real-RC 選項段），既有 golden 零影響。

### 分流實作位置（副檔名分流，早於型別判定）

1. `texproc/src/grouping.rs`
   - `SUPPORTED_EXTENSIONS`（第 17 行）加入 `"hdr"`（`"exr"` 原已在），讓
     scanner 不因 DEF-20 拒收 hdr。
   - `classify_path`：在 `SUPPORTED_EXTENSIONS` 檢查之後、`probe_header`
     **之前**加入 passthrough 短路 —
     `if crate::passthrough::is_passthrough_ext(&extension) { return unknown_entry(...) }`。
     這是「早於型別判定以副檔名分流」的落點：hdr 無法被既有 io 探針解析
     （會誤報 DEF-20 error），且業主「exr 全面改道」要求 exr 無視型別後綴一律
     不進 TIF 管線 —— 兩者都在此短路成 `unknown`，不做 header 探測、不出 error
     診斷。
   - `ScanResult::unknown_only_groups`（exit-3 閘）：只有當群組「無 slots 且存在
     非-passthrough 的 unknown 檔」才算被擋。純 hdr/exr 群組不再觸發 exit 3。
2. `texproc/src/passthrough.rs`（新模組）
   - `is_passthrough_ext` / `is_passthrough_path`：`hdr`|`exr` 判定（大小寫不敏感）。
   - `stage_passthrough(src, output_dir) -> PathBuf`：`.hdr` 用 `fs::copy` 位元
     相同複製到輸出目錄；`.exr` 走 `exr_to_hdr` 轉為 Radiance `.hdr`。原始輸入
     檔一律不動。
   - `exr_to_hdr`：用 image crate 直接 `ImageReader::with_format(OpenExr).decode()
     .to_rgb32f()` → `HdrEncoder::encode(&[Rgb<f32>])`。**刻意繞過 `PlanarImage`**
     —— `PlanarImage::from_interleaved_f32`/`::new` 會把樣本夾到 `0..=1`，會摧毀
     HDR range，故不可用該路徑。
3. `texproc/src/batch.rs` `process_scan_group`：先把該群組 `unknown` 中的
   passthrough 檔逐一 `stage_passthrough` 到輸出目錄並記入 `written`（與 TIF
   同列）；只有在「有 slots 或存在非-passthrough unknown」時才跑 Stage 1/2，
   確保**純 env-map 群組不會產出 fallback spec TIF**。
4. `texproc/src/output.rs`：未改（passthrough 寫檔集中在 `passthrough.rs`，
   避免 grouping→output 反向相依）。
5. `texproc/Cargo.toml`：image 只加 `"hdr"` feature（`HdrEncoder`/`HdrDecoder`），
   無新依賴條目（hdr feature 不引入新 crate，`--locked` 通過）。
6. `texproc/src/lib.rs`：`pub mod passthrough;` 與 re-export。
7. `texproc-gui/src/worker.rs`
   - `dds_jobs()`：篩選由 `tif` 擴為 `tif|hdr`。
   - `run_dds_pool` / `spawn_rc`：**未改**。同一 RC 呼叫形式即可讓 hdr 產出
     cubemap-HDR DDS，無需額外旗標。`delete_tif` 分支（`fs::remove_file(job.tif)`）
     天然適用 hdr（`job.tif` 即被 RC 消費的產出檔路徑，對 hdr 就是暫存的 .hdr）。

### RC 對 hdr 的實際命令列與 DDS header 證據（錨點 3）

- RC：`S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe`
- 命令列（`spawn_rc`，cwd=輸出目錄，null stdio，CREATE_NO_WINDOW）：
  `rc.exe <輸出目錄>\Sky.hdr /refresh /userdialog=0`
- 輸入：合成 256×128 lat-long Radiance HDR（值 >1.0）。
- 產出 `Sky.dds` header 探針結果：
  `256x256 fourCC='DX10' cubemap(caps2=0x200) BC6H (HDR)`
  —— 同時具備 **cubemap caps（0x200）與 BC6H HDR 格式**（DXGI 94–96）。
  RC 另自動產出 `Sky_diff.dds`（環境探針的 diffuse irradiance cubemap）。
  DDS 4/4 成功。

### exr→hdr 精度測試數據（錨點 1）

合成 2×1 EXR（非 2 的冪次值以確實觸發 RGBE 量化），轉 hdr 後讀回：
- 像素0 (0.3, 0.7, 1.3)，pixel-max 容差 1.3/128≈0.010156：
  |Δ| = 0.003125 / 0.004687 / 0.003125
- 像素1 (5.1, 2.9, 0.15)，pixel-max 容差 5.1/128≈0.039844：
  |Δ| = 0.006250 / 0.025000 / 0.025000
- 容差模型：RGBE 每像素共用單一 8-bit 指數，故每通道絕對誤差上界由「該像素
  最大通道值 / 128」決定（非逐通道）。`.hdr` 直通則為位元相同複製（斷言全等）。

### 新增／修改測試

- `texproc/src/passthrough.rs`
  - `exr_to_hdr_roundtrip_preserves_values_within_rgbe_precision`（錨點 1，含 >1.0 值）
  - `hdr_passthrough_is_byte_identical_copy`（錨點 1，位元相同 + 源檔不動）
  - `passthrough_extension_predicate_is_case_insensitive`
- `texproc/src/batch.rs`
  - `mixed_png_hdr_exr_dir_stages_hdr_and_keeps_tif_pipeline`（錨點 2：混合目錄
    scan→process，無 exit 3；png 出 TIF、hdr/exr 各出一個 .hdr、env-map 不出 TIF）
- `texproc-gui/src/worker.rs`
  - `dds_jobs_selects_tiff_and_staged_hdr_outputs`（改：涵蓋 hdr 收編、排除 dds/txt）
  - `hdr_passthrough_rc_produces_dds_and_cleans_staged_files`（錨點 3+4，`#[ignore]`
    需真 RC：跑 GUI 完整 dds_jobs→run_dds_pool→delete_tif 路徑，斷言 DDS 產出、
    header 具 cubemap/BC6H 證據、輸出目錄 .tif/.hdr 均被刪、輸入目錄源檔不動）

### 與票面差異（已據理處理）

- 票面第 3 點示意 RC 呼叫為 `rc <file> /userdialog=0`；實際既有程式碼為
  `rc <file> /refresh /userdialog=0`（未更動）。真 RC 驗證下同一形式即產出
  cubemap-HDR DDS，故未加任何 hdr 專屬旗標。
- 分流除了 batch/output 層外，另在 `grouping.rs::classify_path` 加了副檔名短路。
  原因：Radiance HDR 非既有 io 探針可解析（否則每個 hdr 都噴 DEF-20 error），
  且「exr 全面改道」需在型別判定前攔截 —— 兩者正是票面「以副檔名分流，早於
  型別判定」的要求，故置於 scan 分類的最前段。passthrough 寫檔邏輯集中在新的
  `passthrough.rs`（而非 output.rs），以避免低層 `grouping` 反向相依 `output`。

## 審查紀錄（2026-07-27，協調者）

- 獨立重跑：texproc 66 測試、texproc-gui 35 測試（閘門不含 GUI 測試，另跑）、
  真 RC ignored 測試（`Sky.dds` = 256x256 DX10 cubemap(0x200) BC6H；清理後輸出
  目錄僅剩 .dds/.cryasset；RC 附產 `Sky_diff.dds` irradiance probe）、
  `run_gates.ps1` 全綠。
- 補測 Fox 未蓋的面：**CLI JSON 往返**（`texproc scan` 寫 groups.json →
  `texproc process` 讀回）——`unknown` 條目活過 serde，hdr 正確 staging，
  scan/process exit 0，源檔不動。手工構造 flat RGBE hdr 驗證。
- 程式碼審：`PlanarImage` 夾值主張屬實（planar.rs:87 `clamp(0.0,1.0)`），
  exr 繞道必要；exit-3 閘放寬範圍正確（僅純 passthrough 群組放行，混有
  非-passthrough unknown 仍擋）。
- 已知小邊界（不擋票，記錄在案）：同 stem 的 `X.hdr` + `X.exr` 同批輸入時
  staging 目的檔相同（`X.hdr`），後者覆蓋前者——與既有 TIF 管線同 stem 行為
  同類；遇實際案例再處理。
