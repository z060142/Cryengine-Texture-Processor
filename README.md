# CryEngine Texture Processor

## 專案概述

CryEngine Texture Processor 是一個專門為 CryEngine 開發的紋理處理工具，能夠將各種來源的紋理格式轉換為 CryEngine 所需的特定格式。本工具提供了自動識別、分類、處理和導出功能，大幅簡化了遊戲美術資源的處理工作流程。

### 主要功能

- 導入並自動分類多種紋理格式（diffuse, normal, specular 等）
- 生成 CryEngine 特定紋理格式（_diff, _spec, _ddna 等）
- 批量處理多組紋理，節省時間
- 自動生成 CryEngine DDS 文件和縮圖
- 可調整輸出紋理解析度

## 已實現功能

### 核心功能
- [x] 多種紋理格式的輸入支持（jpg, png, tga, HDR 等）
- [x] 基於文件名的自動紋理分類
- [x] 基於圖像內容的智能識別
- [x] 未知紋理的手動分類界面
- [x] 中間格式處理（albedo, normal, reflection 等）
- [x] CryEngine 輸出格式生成
- [x] 紋理組處理（將相關紋理作為一組處理）
- [x] 多語言支持（英文、繁體中文）

### 高級功能
- [x] 批量處理功能
- [x] 進度顯示與取消功能
- [x] 預覽功能
- [x] 解析度調整
- [x] RC.exe 集成，生成 CryEngine DDS
- [x] 自動生成 DDS 縮略圖 (256x256)
- [x] ARM 紋理處理（從單一紋理中提取 AO、Roughness 和 Metallic）
- [x] 高度圖轉法線圖

### 已部分實現功能
- [ ] 模型文件集成 (架構已完成)
- [ ] 處理日誌系統 (架構已完成)

## 使用指南

### 基本使用流程

1. **導入紋理**
   - 點擊 "Import Textures" 按鈕
   - 選擇要處理的紋理文件
   - 系統自動分類並分組紋理

2. **預覽與檢查**
   - 在中央面板查看預覽
   - 檢查紋理分類是否正確
   - 如有未知紋理，手動設置類型

3. **設置輸出選項**
   - 設置輸出目錄
   - 選擇輸出格式（TIF、PNG、DDS）
   - 選擇解析度（原始、4096、2048、1024、512）
   - 選擇要生成的紋理類型
   - 可選：啟用 "Generate CryEngine DDS"

4. **處理紋理**
   - 點擊 "Batch Process" 按鈕開始處理
   - 查看進度對話框
   - 完成後檢查輸出目錄

### CryEngine DDS 生成設置

1. **設置 RC.exe 路徑**
   - 在 "Edit" 選單中選擇 "Preferences"
   - 在 "CryEngine Integration" 標籤中設置 RC.exe 路徑
   - 驗證路徑是否有效

2. **啟用 DDS 生成**
   - 在輸出設置面板勾選 "Generate CryEngine DDS"
   - 確保輸出格式設為 TIF (RC.exe 需要 TIF 格式輸入)

3. **檢查結果**
   - 處理完成後，輸出目錄會包含：
     - TIF 格式的紋理文件
     - DDS 格式的紋理文件
     - 256x256 的縮略圖（.dds.thmb.png）

## 架構說明

本專案採用模塊化設計，主要組件包括：

### 核心模塊
- `core/`: 核心處理邏輯
  - `texture_manager.py`: 紋理管理與分組
  - `name_parser.py`: 文件名分析
  - `texture_analyzer.py`: 圖像內容分析
  - `batch_processor.py`: 批量處理控制器

### 中間格式處理
- `intermediate_formats/`: 中間紋理處理器
  - 各種中間格式（albedo, normal, reflection 等）的處理類

### 輸出格式生成
- `output_formats/`: 輸出格式生成器
  - 各種 CryEngine 紋理格式（_diff, _spec, _ddna 等）的輸出類

### 用戶界面
- `ui/`: 用戶界面組件
  - 主窗口、面板、對話框等

### 工具類
- `utils/`: 工具類
  - `image_processing.py`: 圖像處理函數
  - `config_manager.py`: 配置管理
  - `dds_processor.py`: DDS 處理功能

### 多語言支持
- `language/`: 語言資源
  - 各種語言的文本資源

## 下一階段開發建議

以下是可能的下一階段開發方向：

1. **完成模型集成功能**
   - 實現模型文件中紋理引用的提取
   - 自動更新模型材質以使用處理後的紋理
   - 支持批量處理模型文件

2. **增強日誌系統**
   - 實現詳細的處理日誌記錄
   - 增加錯誤診斷功能

3. **紋理質量驗證**
   - 添加自動檢測紋理問題的功能
   - 提供紋理優化建議

4. **用戶體驗優化**
   - 記住用戶的紋理分類選擇
   - 添加項目保存/載入功能
   - 支持拖放操作

5. **高級預覽**
   - 使用 PBR 著色器預覽紋理效果
   - 3D 模型預覽功能

6. **批處理改進**
   - 支持文件夾遞歸處理
   - 支持處理預設

## 注意事項

- 使用 RC.exe 功能需要有效的 CryEngine 安裝
- 輸出紋理調整解析度時會保持原始縱橫比
- DDS 縮略圖生成僅在使用 RC.exe 生成 DDS 時可用
- 建議使用 TIF 格式作為中間處理格式，以保持最高質量

## 結語

CryEngine Texture Processor 已實現了主要的紋理處理功能，可以大幅提高遊戲開發中的紋理工作流效率。下一階段開發將專注於完善模型集成、增強預覽能力，以及提供更多高級功能。
