# EXR 與部分成功處理

EXR 材質貼圖依後綴辨識、合組，使用原生 EXR 通道解碼；不再要求檔案一定含有 RGB 通道。匯入、預覽、材質處理與環境圖暫存共用解碼邏輯。

- 支援單通道（如 Y、R、Z、roughness）、Y+A、RGB、RGBA，以及帶前綴的 RGB/A 通道。優先使用無前綴通道，再使用同一前綴的完整通道組，不跨前綴拼湊 RGB。
- 支援 HALF、FLOAT、UINT。材質處理沿用既有 0–1 浮點值範圍，Y+A 轉成 RGBA；環境圖轉 HDR 保留大於 1 的亮度。NaN/Infinity 會回報來源錯誤。
- 無材質後綴的 EXR 與 Radiance HDR 保留環境圖處理路徑。預覽現在也能解碼 Radiance HDR。
- `_nor_gl_4k.exr` 依 OpenGL 法線慣例轉換綠色通道；roughness 單通道可用於 DDNA 的 gloss alpha。

自動測試涵蓋 Uncompressed、RLE、ZIP1、ZIP16、PIZ、PXR24、B44、B44A、DWAA、DWAB，各自測試 scanline 與 tiled 寫入／讀回。另驗證單通道與混合精度、命名通道及 HDR 暫存亮度。

目前明確邊界：讀取第一個可讀取的非 deep part 與最大解析度；沒有提供 multipart/layer/mipmap 選擇介面。Deep EXR、通道子採樣及無法確定用途的任意多通道配置會回報錯誤，不會猜測或聲稱已支援所有 EXR 變體。原生讀取 API 見 [exr 文件](https://docs.rs/exr/1.74.2/exr/image/read/index.html)。

## 單張失敗的行為

- 缺檔、損壞檔案與不適用的來源通道會記錄檔名和原因，繼續載入同組其他來源。
- Stage 1 的材質步驟及 Stage 2 的每個輸出分別隔離錯誤。某個輸出無法寫入時，後續輸出仍繼續；成功路徑保留於結果，繼續送交 DDS 編譯。
- 無法分類的項目列入診斷，不阻擋 GUI 整批執行。CLI 也先完成可處理項目，最後用非零退出碼表示仍有錯誤；未指定類型的分組預設保留退出碼 3。
- CLI 明確指定 `--allow-unknown` 時，未分類項目改列警告並略過，不製造預設輸出；其他真正的讀取或處理錯誤仍以非零退出碼回報。
- 完全沒有可用來源的失敗群組不會產生假成功的預設 spec。其餘群組依原本設定，使用剩餘來源與既有 fallback 規則。
- GUI 完成摘要顯示部分成功的貼圖錯誤數量與詳細原因；模型附帶貼圖匯出也保留錯誤資訊。

故障回歸測試同時注入壞 AO、壞 EXR、未分類項目與無法寫入的 diffuse 目標，驗證同組 spec/DDNA 及另一組 diffuse 仍存在，並檢查 DDNA 綠色與 alpha 的實際像素。
