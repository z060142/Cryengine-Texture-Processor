# T-013 (T5) — texproc → RC.exe → DDS 端到端

狀態：DONE（2026-07-25：自動化 DoD 全數通過 + 業主引擎內目視簽核 PASS。T5 完工，重構主線 C1–C5 / T1–T5 全數結案）
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

## 實作與自動驗收

- 新增 stdlib-only `tools/texproc_rc_smoke.py`：先執行 frozen
  `texproc process`，再逐張以
  `RC.exe <tif> /refresh /userdialog=0` 轉 DDS。
- 每張產物驗 RC exit code、同 stem `.dds` 存在、DDS magic/header/FourCC；
  `_ddna` 額外驗 alpha-capable header。
- CryEngine 5.7 的 `NormalsWithSmoothness` 實際輸出是 DX10 header、主面
  DXGI 84（BC5），smoothness 不在標準 alpha mask，而是以 Cry attached
  channel 附加。驗證器依引擎 `DDS_HEADER.dwTextureStage == 'CRYF'` 與
  `dwReserved1 & EIF_AttachedAlpha (0x400)` 判定，仍只讀 header、不解壓像素。
- 素材一為 AtlasA 7 張；素材二為 GlassClean 六張，metallic 灰階範圍
  35–155，確認不是無訊號常數圖。GlassClean 的 `_refraction` 未納入，因
  T-012 的 deterministic grouping 正確把它列為 unknown-only。

真機命令：

```powershell
uv run python tools\texproc_rc_smoke.py `
  --rc S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe `
  --texproc rebuild\target\release\texproc.exe `
  --work-dir rebuild\fixtures\t013-visual `
  --output docs\rust_texproc_rc_smoke.json `
  rebuild\fixtures\textures
```

結果：

| gate | 結果 |
|---|---:|
| texproc TIFF | 8 |
| RC exit 0 | 8/8 |
| 對應 DDS 存在 | 8/8 |
| DDS header 可讀 | 8/8 |
| `_ddna` attached alpha | 2/2 |

機器可讀報告：`docs/rust_texproc_rc_smoke.json`。

## 業主目視包

本機 ignored artifact：

```text
E:\CryEngineTextureProcessor\rebuild\fixtures\t013-visual\
  VISUAL_CHECK.md
  textures\KB3D_ENC_AtlasA_{diff,spec,ddna,displ}.dds
  textures\KB3D_ENC_GlassClean_{diff,spec,ddna,displ}.dds
```

最小步驟已寫入包內 `VISUAL_CHECK.md`：把 DDS 複製到目標 GameSDK 的測試
texture 目錄；在 Sandbox Material Editor 對應 Diffuse / Specular / Normal /
Height；套到受光球體或方塊，檢查 diffuse、normal、`_ddna` alpha gloss 與
displacement。GlassClean 另檢查 metallic 路徑沒有平坦化或破圖。

## 業主引擎內目視簽核

狀態：**PASS**（2026-07-25）。

| 日期 | Engine / project | 結果 | 備註 |
|---|---|---|---|
| 2026-07-25 | CryEngine 5.7.1 LTS | PASS | 業主目視簽核：無問題 |

## Gate 驗證（2026-07-25）

```text
.\run_gates.ps1 -SkipRC
  Rust workspace: PASS
  texproc fixture/CLI: PASS
  Python asset_flow: 28 passed, 2 skipped
  RC policy tests: 6 passed
  Optional RC: SKIP
  ALL GATES PASSED

.\run_gates.ps1
  上述非 RC gates: PASS
  converter RC: exit 0, CGF exists, material alignment 16/16
  texproc RC: 8/8 DDS, 2/2 _ddna attached alpha
  ALL GATES PASSED
```

自動化 DoD 已全數完成；本票維持 IMPLEMENTED 而不標 CLOSED，唯一未完成項為
業主在目標引擎／專案內的目視簽核。
