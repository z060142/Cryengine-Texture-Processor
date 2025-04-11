# 專案結構細節 (Project Structure Details)

以下是專案中各個 Python 腳本的功能和相依性分析。

## 根目錄檔案

*   **`.gitignore`**: 指定 Git 應該忽略的檔案和目錄，通常包含暫存檔、編譯結果等。
*   **`main.py`**:
    *   **功能 (Function):** CryEngine Texture Processor 應用程式的主要進入點。初始化 UI、載入設定、處理批次作業和模型匯出。
    *   **相依性 (Dependencies - 專案模組):** `ui.main_window.MainWindow`, `ui.progress_dialog.ProgressDialog`, `language.language_manager`, `utils.config_manager.ConfigManager`, `core.batch_processor.BatchProcessor`, `utils.dds_processor.DDSProcessor`, `model_processing.texture_extractor.TextureExtractor`, `output_formats.mtl_exporter.export_mtl`, `output_formats.json_exporter.export_json`, `utils.rc_processor.RCProcessor`, `utils.thumbnail_generator.generate_thumbnail`, `model_processing.fbx_exporter.FbxExporter`, `model_processing.model_loader.ModelLoader`
    *   **相依性 (Dependencies - 外部函式庫):** `os`, `sys`, `time`, `tkinter`, `traceback`, `gc`, `signal`, `atexit`, `numpy`
*   **`README_ZH.md`**: 專案的中文說明文件。
*   **`README.md`**: 專案的英文說明文件。
*   **`requirements.txt`**: 列出專案的相依套件，用於使用 `pip` 安裝。
*   **`setup_env.py`**:
    *   **功能 (Function):** 設定 Python 虛擬環境，安裝相依套件，並建立啟動腳本。
    *   **相依性 (Dependencies):** `os`, `sys`, `subprocess`, `platform`
*   **`suffix_settings.json`**: 儲存貼圖後綴設定的 JSON 檔案。

## `core` 目錄檔案

*   **`core/__init__.py`**:
    *   **功能 (Function):** 將 `core` 目錄標示為一個 Python 套件。
    *   **相依性 (Dependencies):** 無。
*   **`core/batch_processor.py`**:
    *   **功能 (Function):** 提供批次處理 `TextureGroup` 物件的功能。
    *   **相依性 (Dependencies - 專案模組):** `core.texture_manager.TextureManager`, `core.name_parser.TextureNameParser`, `intermediate_formats.albedo_processor.AlbedoProcessor`, `intermediate_formats.normal_processor.NormalProcessor`, `intermediate_formats.reflection_processor.ReflectionProcessor`, `intermediate_formats.glossiness_processor.GlossinessProcessor`, `intermediate_formats.height_processor.HeightProcessor`, `intermediate_formats.ao_processor.AOProcessor`, `intermediate_formats.arm_processor.ARMProcessor`, `output_formats.diff_exporter.DiffExporter`, `output_formats.spec_exporter.SpecExporter`, `output_formats.ddna_exporter.DDNAExporter`, `output_formats.displ_exporter.DisplExporter`, `output_formats.emissive_exporter.EmissiveExporter`, `output_formats.sss_exporter.SSSExporter`
*   **`core/material_manager.py`**:
    *   **功能 (Function):** 提供管理材質的功能，包括建立、更新和轉換為 CryEngine 格式。
    *   **相依性 (Dependencies):** 無
*   **`core/model_manager.py`**:
    *   **功能 (Function):** 提供管理模型載入、紋理提取和更新的功能。
    *   **相依性 (Dependencies):** 無
*   **`core/name_parser.py`**:
    *   **功能 (Function):** 解析紋理文件名以提取紋理類型和基本名稱信息。
    *   **相依性 (Dependencies):** `core.texture_analyzer.TextureAnalyzer`
*   **`core/texture_analyzer.py`**:
    *   **功能 (Function):** 分析紋理以確定其類型。
    *   **相依性 (Dependencies):** `PIL.Image`, `PIL.ImageStat`, `os`, `numpy`
*   **`core/texture_manager.py`**:
    *   **功能 (Function):** 管理紋理分類、分組和處理。
    *   **相依性 (Dependencies):** `core.name_parser.TextureNameParser`

## `examples` 目錄檔案

*   **`examples/batch_process_example.py`**:
    *   **功能 (Function):** 演示如何使用批次處理功能將紋理目錄轉換為 CryEngine 格式。
    *   **相依性 (Dependencies):** `os`, `sys`, `time`, `tkinter`, `core.texture_manager.TextureManager`, `core.batch_processor.BatchProcessor`, `ui.progress_dialog.ProgressDialog`

## `intermediate_formats` 目錄檔案

*   **`intermediate_formats/__init__.py`**:
    *   **功能 (Function):** 將 `intermediate_formats` 目錄標示為一個 Python 套件。
    *   **相依性 (Dependencies):** 無。
*   **`intermediate_formats/albedo_processor.py`**:
    *   **功能 (Function):** 處理輸入紋理以生成反照率中間格式。
    *   **相依性 (Dependencies):** `numpy`, `PIL.Image`, `utils.image_processing.ImageProcessor`
*   **`intermediate_formats/ao_processor.py`**:
    *   **功能 (Function):** 處理環境光遮蔽 (AO) 貼圖。
    *   **相依性 (Dependencies):** `utils.image_processing.ImageProcessor`
*   **`intermediate_formats/arm_processor.py`**:
    *   **功能 (Function):** 處理 ARM 紋理，提取 AO、粗糙度和金屬度通道。
    *   **相依性 (Dependencies):** `os`, `subprocess`, `shutil`, `pathlib`, `utils.image_processing.ImageProcessor`
*   **`intermediate_formats/glossiness_processor.py`**:
    *   **功能 (Function):** 處理輸入紋理以生成光澤度中間格式。
    *   **相依性 (Dependencies):** `os`, `subprocess`, `shutil`, `pathlib`, `utils.image_processing.ImageProcessor`
*   **`intermediate_formats/height_processor.py`**:
    *   **功能 (Function):** 處理高度/位移貼圖。
    *   **相依性 (Dependencies):** `utils.image_processing.ImageProcessor`
*   **`intermediate_formats/normal_processor.py`**:
    *   **功能 (Function):** 處理法線貼圖，包括在 DirectX 和 OpenGL 格式之間進行轉換。
    *   **相依性 (Dependencies):** `utils.image_processing.ImageProcessor`, `PIL.ImageStat`
*   **`intermediate_formats/reflection_processor.py`**:
    *   **功能 (Function):** 處理輸入紋理以生成反射中間格式。
    *   **相依性 (Dependencies):** `os`, `subprocess`, `shutil`, `pathlib`, `utils.image_processing.ImageProcessor`, `numpy`, `PIL.Image`

## `language` 目錄檔案

*   **`language/__init__.py`**:
    *   **功能 (Function):** 將 `language` 目錄標示為一個 Python 套件。
    *   **相依性 (Dependencies):** 無。
*   **`language/EN.py`**:
    *   **功能 (Function):** 包含英文 UI 文字的語言字典。
    *   **相依性 (Dependencies):** 無。
*   **`language/language_manager.py`**:
    *   **功能 (Function):** 提供管理 UI 語言和本地化的功能。
    *   **相依性 (Dependencies):** `os`, `importlib`, `utils.config_manager.ConfigManager`
*   **`language/ZHT.py`**:
    *   **功能 (Function):** 包含繁體中文 UI 文字的語言字典。
    *   **相依性 (Dependencies):** 無。

## `model_processing` 目錄檔案

*   **`model_processing/__init__.py`**:
    *   **功能 (Function):** 將 `model_processing` 目錄標示為一個 Python 套件。
    *   **相依性 (Dependencies):** 無。
*   **`model_processing/bpy_diagnostic.py`**:
    *   **功能 (Function):** 檢查 Blender Python API (bpy) 是否可用，並提供詳細的環境信息以幫助診斷問題。
    *   **相依性 (Dependencies):** `os`, `sys`, `platform`, `traceback`
*   **`model_processing/fbx_export_numpy_fix.py`**:
    *   **功能 (Function):** 創建一個具有 NumPy 1.x 的獨立環境，以修復在主環境中安裝了 NumPy 2.x 時的導出問題。
    *   **相依性 (Dependencies):** `os`, `sys`, `subprocess`, `argparse`, `platform`, `venv`, `tempfile`, `shutil`, `json`
*   **`model_processing/fbx_exporter.py`**:
    *   **功能 (Function):** 使用 Blender Python API 將模型導出為 FBX 格式。
    *   **相依性 (Dependencies):** `os`, `sys`, `traceback`, `pathlib`
*   **`model_processing/material_converter.py`**:
    *   **功能 (Function):** 使用 Blender Python API 將材質轉換為 CryEngine 格式。
    *   **相依性 (Dependencies):** 無
*   **`model_processing/model_loader.py`**:
    *   **功能 (Function):** 使用 Blender Python API 載入 3D 模型。
    *   **相依性 (Dependencies):** `os`, `importlib`
*   **`model_processing/texture_extractor.py`**:
    *   **功能 (Function):** 使用 Blender Python API 從模型中提取紋理引用。
    *   **相依性 (Dependencies):** `os`, `importlib`

## `output_formats` 目錄檔案

*   **`output_formats/__init__.py`**:
    *   **功能 (Function):** 將 `output_formats` 目錄標示為一個 Python 套件。
    *   **相依性 (Dependencies):** 無。
*   **`output_formats/ddna_exporter.py`**:
    *   **功能 (Function):** 導出 CryEngine 的 _ddna 紋理。
    *   **相依性 (Dependencies):** `os`, `subprocess`, `shutil`
*   **`output_formats/diff_exporter.py`**:
    *   **功能 (Function):** 導出 CryEngine 的 _diff 紋理。
    *   **相依性 (Dependencies):** `os`, `subprocess`, `shutil`, `numpy`, `PIL.Image`, `PIL.ImageChops`
*   **`output_formats/displ_exporter.py`**:
    *   **功能 (Function):** 導出 CryEngine 的 _displ 紋理。
    *   **相依性 (Dependencies):** `os`, `subprocess`, `shutil`
*   **`output_formats/emissive_exporter.py`**:
    *   **功能 (Function):** 導出 CryEngine 的 _emissive 紋理。
    *   **相依性 (Dependencies):** `os`, `subprocess`, `shutil`, `utils.image_processing.ImageProcessor`, `PIL.Image`, `numpy`
*   **`output_formats/json_exporter.py`**:
    *   **功能 (Function):** 導出 CryEngine 兼容的 JSON 配置文件。
    *   **相依性 (Dependencies):** `os`, `json`, `re`, `traceback`, `pathlib`, `importlib`
*   **`output_formats/mtl_exporter.py`**:
    *   **功能 (Function):** 導出 CryEngine 兼容的 .mtl 文件及對應的 .mtl.cryasset 元數據文件。
    *   **相依性 (Dependencies):** `os`, `uuid`, `xml.etree.ElementTree`, `xml.dom.minidom`, `PIL.Image`
    *   **主要功能:**
        * 生成 CryEngine 材質 (.mtl) 文件，包含材質屬性和貼圖引用
        * 智能處理 AlphaTest 參數，僅在材質含有透明度時添加
        * 自動檢測 diffuse 貼圖中的 alpha 通道
        * 識別專用透明度貼圖 (alpha, opacity, transparency, mask)
        * 自動生成配套的 .mtl.cryasset 元數據文件
        * 處理貼圖依賴項和相對路徑計算
*   **`output_formats/spec_exporter.py`**:
    *   **功能 (Function):** 導出 CryEngine 的 _spec 紋理。
    *   **相依性 (Dependencies):** `os`, `subprocess`, `shutil`, `utils.image_processing.ImageProcessor`, `PIL.Image`, `numpy`
*   **`output_formats/sss_exporter.py`**:
    *   **功能 (Function):** 導出 CryEngine 的 _sss 紋理。
    *   **相依性 (Dependencies):** `os`, `subprocess`, `shutil`, `utils.image_processing.ImageProcessor`, `PIL.Image`, `numpy`

## `ui` 目錄檔案

*   **`ui/__init__.py`**:
    *   **功能 (Function):** 將 `ui` 目錄標示為一個 Python 套件。
    *   **相依性 (Dependencies):** 無。
*   **`ui/export_settings.py`**:
    *   **功能 (Function):** 提供用於配置紋理導出設置和 CryEngine 兼容輸出選項的 UI 組件。
    *   **相依性 (Dependencies):** `os`, `tkinter`, `language.language_manager`, `ui.progress_dialog.ProgressDialog`
    *   **主要功能:**
        * 提供「貼圖輸出設定」面板，允許用戶配置紋理生成和處理選項
        * 提供「模型輸出設定」面板
        * 提供「雜項設定」面板，包含導出後刪除TIF、FBX、JSON檔案的選項（僅刪除當次操作新產生的檔案）
        * 整合「批次處理」功能，完整執行貼圖生成、MTL導出及FBX導出流程
        * TIF刪除選項只有在啟用DDS生成時才能使用
        * 將所有相關提示訊息備給日誌系統，避免訊息窗影響操作流程
*   **`ui/main_window.py`**:
    *   **功能 (Function):** 提供主應用程式窗口並協調不同 UI 組件之間的交互。
    *   **相依性 (Dependencies):** `tkinter`, `ui.texture_import.TextureImportPanel`, `ui.model_import.ModelImportPanel`, `ui.preview_panel.PreviewPanel`, `ui.export_settings.ExportSettingsPanel`, `ui.texture_group_panel.TextureGroupPanel`, `ui.suffix_settings.SuffixSettingsDialog`, `ui.preferences_dialog.PreferencesDialog`, `language.language_manager`
*   **`ui/model_import.py`**:
    *   **功能 (Function):** 提供用於導入模型文件和從中提取紋理引用的 UI 組件。
    *   **相依性 (Dependencies):** `os`, `tkinter`, `threading`, `queue`, `model_processing.model_loader.ModelLoader`, `model_processing.texture_extractor.TextureExtractor`, `ui.progress_dialog.ProgressDialog`, `language.language_manager`
*   **`ui/preferences_dialog.py`**:
    *   **功能 (Function):** 提供用於設置應用程式偏好設定的對話框。
    *   **相依性 (Dependencies):** `os`, `tkinter`, `language.language_manager`, `utils.config_manager.ConfigManager`
*   **`ui/preview_panel.py`**:
    *   **功能 (Function):** 提供用於預覽紋理和可視化紋理處理結果的 UI 組件。
    *   **相依性 (Dependencies):** `os`, `tkinter`, `PIL.Image`, `PIL.ImageTk`
*   **`ui/progress_dialog.py`**:
    *   **功能 (Function):** 提供進度對話框 UI 組件，以在長時間運算期間顯示進度信息。
    *   **相依性 (Dependencies):** `tkinter`, `language.language_manager`
*   **`ui/suffix_settings.py`**:
    *   **功能 (Function):** 提供用於配置紋理類型後綴設定的對話框。
    *   **相依性 (Dependencies):** `os`, `json`, `tkinter`
*   **`ui/texture_group_panel.py`**:
    *   **功能 (Function):** 提供用於顯示和管理紋理組的 UI 組件。
    *   **相依性 (Dependencies):** `os`, `tkinter`
*   **`ui/texture_import.py`**:
    *   **功能 (Function):** 提供用於導入和分類紋理的 UI 組件。
    *   **相依性 (Dependencies):** `os`, `json`, `re`, `tkinter`, `core.texture_manager.TextureManager`

## `utils` 目錄檔案

*   **`utils/__init__.py`**:
    *   **功能 (Function):** 將 `utils` 目錄標示為一個 Python 套件。
    *   **相依性 (Dependencies):** 無。
*   **`utils/cgf_processor.py`**:
    *   **功能 (Function):** 使用 RC.exe 處理 JSON 配置文件以生成 CGF 文件。
    *   **相依性 (Dependencies):** `os`, `subprocess`, `threading`, `utils.config_manager.ConfigManager`
*   **`utils/config_manager.py`**:
    *   **功能 (Function):** 管理應用程式配置（加載/保存 JSON）。
    *   **相依性 (Dependencies):** `os`, `json`
*   **`utils/dds_processor.py`**:
    *   **功能 (Function):** 使用 RC.exe 將 TIF 文件處理為 DDS 文件。
    *   **相依性 (Dependencies):** `os`, `subprocess`, `threading`, `concurrent.futures`, `utils.config_manager.ConfigManager`, `utils.image_processing.ImageProcessor`
*   **`utils/file_operations.py`**:
    *   **功能 (Function):** 提供文件和目錄操作的實用函數。
    *   **相依性 (Dependencies):** `os`, `shutil`, `re`
*   **`utils/image_processing.py`**:
    *   **功能 (Function):** 提供使用 Pillow (PIL) 庫的圖像處理實用函數。
    *   **相依性 (Dependencies):** `PIL.Image`, `PIL.ImageOps`, `PIL.ImageFilter`, `PIL.ImageChops`, `PIL.ImageStat`, `os`, `numpy`
*   **`utils/rc_processor.py`**:
    *   **功能 (Function):** 處理與 CryEngine 資源編譯器 (RC.exe) 的交互。
    *   **相依性 (Dependencies):** `os`, `subprocess`, `threading`, `utils.config_manager.ConfigManager`, `language.language_manager`
*   **`utils/thumbnail_generator.py`**:
    *   **功能 (Function):** 使用 Blender 的 bpy 模塊為 FBX 模型生成 PNG 縮略圖。
    *   **相依性 (Dependencies):** `bpy`, `os`, `math`, `mathutils`, `traceback`
