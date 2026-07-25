# T-013 (T5) — texproc → RC.exe → DDS 端到端

狀態：OPEN
上游文件：遷移計畫 T5 里程碑；T-007 的 RC smoke 模式
前置：T-012。最終驗收含業主引擎內目視（不可自動化）。

## 工作內容

1. `tools/texproc_rc_smoke.py`（stdlib only，模式照 `rc_smoke_rust.py`）：
   - `texproc process` 對指定貼圖組產出 CE TIFF。
   - 逐張餵 RC.exe（`/refresh /userdialog=0`，比照舊 texture 流程——先讀 `tools/rc_smoke_test.py` 的 texture 段確認旗標）。
   - 驗證：RC 退出碼、每張 TIFF 對應 `.dds` 產出、`_ddna` 的 DDS 帶 alpha（檔案層面驗 header 的 FourCC/flags 即可，不解壓像素）。
   - smoke 報告 JSON 存 `docs/rust_texproc_rc_smoke.json`。
2. 實跑素材：`fixtures/textures/KB3D_ENC_AtlasA_*`（含 roughness → ddna alpha 路徑）+ 至少一組含 metallic 的素材（KB3D 目錄挑一組有訊號的）。
3. `run_gates.ps1` 的選配 RC 段擴充：texproc smoke 跟 converter smoke 同段、同 SKIP 條件。
4. **業主目視包**：把 DDS 連同一個最小使用說明（放哪個引擎目錄、看什麼）寫進回報；引擎內目視由業主執行、簽核記錄在本票。

## 明確禁止

- 不動兩個 CLI 的凍結契約。不新增依賴。
- DDS 只驗存在性與 header，不做像素比對（RC 的壓縮是黑盒，目視是最終仲裁）。

## DoD

- smoke 實跑全綠，報告與指令貼回報。
- `run_gates.ps1` 兩種模式（有/無 RC）驗證過。
- 業主引擎內目視簽核（本票結票條件）。
