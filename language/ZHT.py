#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Traditional Chinese Language Module (繁體中文語言模組)

This module contains the Traditional Chinese language dictionary for UI text.
"""

# Language name for display in UI
LANGUAGE_NAME = "繁體中文"

LANGUAGE_DICT = {
    "app": {
        "title": "CryEngine 貼圖處理器",
        "ready": "就緒"
    },
    "menu": {
        "file": {
            "title": "檔案",
            "import_textures": "導入貼圖...",
            "import_model": "導入模型...",
            "export": "導出...",
            "exit": "退出"
        },
        "edit": {
            "title": "編輯",
            "suffix_settings": "後綴設定...",
            "preferences": "偏好設定...",
            "language": "語言"
        },
        "help": {
            "title": "幫助",
            "about": "關於"
        }
    },
    "import": {
        "texture": {
            "title": "貼圖導入",
            "button": "導入貼圖",
            "list_title": "已導入貼圖",
            "classification_title": "分類選項",
            "default_classification": "預設分類:",
            "reclassify": "重新分類",
            "import_success": "成功導入 {0} 個貼圖。"
        },
        "model": {
            "title": "模型導入",
            "button": "導入模型",
            "info_title": "模型資訊",
            "path": "路徑:",
            "materials": "材質:",
            "textures": "貼圖:",
            "list_title": "提取的貼圖",
            "extract_button": "提取貼圖",
            "update_button": "更新材質",
            "extract_success": "成功提取 {0} 個貼圖。",
            "update_success": "成功更新材質。",
            "import_success": "成功導入 {0}。"
        }
    },
    "preview": {
        "title": "預覽",
        "texture": "貼圖:",
        "type": "類型:",
        "view": "視圖:",
        "original": "原始",
        "processed": "處理後",
        "no_texture": "未選擇貼圖"
    },
    "groups": {
        "title": "偵測到的貼圖組",
        "details_title": "組詳情",
        "base_name": "基本名稱:",
        "texture_types": "貼圖類型:"
    },
    "export": {
        "title": "導出設定",
        "texture_output_directory": "貼圖輸出目錄:", # 重命名
        "model_output_directory": "模型輸出目錄:",   # 新增
        "select_texture_directory": "選取貼圖輸出目錄", # 重命名
        "select_model_directory": "選取模型輸出目錄",   # 新增
        "no_directory_selected": "尚未選取目錄。將在匯出時提示。", # 新增通用版本
        "directory_valid": "目錄有效且可寫入。", # 新增通用版本
        "directory_not_writable": "警告：目錄不可寫入！", # 新增通用版本
        "directory_not_exist": "目錄不存在。將在匯出時建立。", # 新增通用版本
        "create_texture_dir_error": "建立貼圖輸出目錄失敗：{0}", # 重命名
        "create_model_dir_error": "建立模型輸出目錄失敗：{0}",     # 新增
        "diff_format": "漫反射格式:",
        "normal_flip": "翻轉法線圖綠色通道",
        "spec_generate": "生成缺失的高光貼圖",
        "output_format": "輸出格式:",
        "output_resolution": "輸出解析度:",
        "types_title": "輸出貼圖類型",
        "diff": "漫反射 (_diff)",
        "spec": "高光 (_spec)",
        "ddna": "法線和光澤度 (_ddna)",
        "displ": "位移 (_displ)",
        "emissive": "自發光 (_emissive)",
        "sss": "次表面散射 (_sss)",
        "export_textures": "匯出貼圖", # 鍵名稍微更改以更清晰
        "export_model": "匯出模型", # 新增
        "save_settings": "儲存設定",
        "settings_saved_title": "設定已儲存", # 新增標題鍵
        "settings_saved_message": "匯出設定已儲存。", # 新增訊息鍵 (修改現有 settings_saved)
        "error_no_texture_dir": "未設定貼圖輸出目錄。", # 重命名
        "error_no_model_dir": "未設定模型輸出目錄。", # 新增
        "warning_no_groups": "沒有可導出的貼圖組。",
        "export_preview_title": "導出預覽",
        "preview_message": "將使用以下設定匯出 {0} 個貼圖群組：", # 新增鍵
        "preview_texture_dir": "貼圖輸出目錄: {0}", # 新增鍵
        "preview_diff": "漫反射格式: {0}", # 新增鍵
        "preview_flip": "翻轉法線圖綠色通道: {0}", # 新增鍵
        "preview_spec": "生成缺失的高光貼圖: {0}", # 新增鍵
        "preview_metallic": "轉換金屬度貼圖: {0}", # 新增鍵 (簡化翻譯)
        "preview_format": "輸出格式: {0}", # 新增鍵
        "preview_resolution": "輸出解析度: {0}", # 新增鍵
        "preview_types": "啟用的貼圖類型: {0}", # 新增鍵
        "model_export_not_implemented": "模型匯出（包含 MTL 生成）已規劃但尚未完全實作。選取的模型目錄：{0}", # 新增
        "no_model_dir": "請先選取模型輸出目錄。", # 新增警告
        "not_implemented": "尚未實作", # 新增通用鍵
        "batch_not_available": "批次處理尚不可用。", # 新增鍵
        "settings": "貼圖輸出設定", # 更改為「貼圖輸出設定」
        "model_settings": "模型輸出設定", # 新增
        "model_settings_note": "模型輸出設定將在此處添加。", # 新增
        "misc_settings": "雜項設定", # 新增
        "delete_after_export": "導出後刪除:", # 新增
        "cleanup_title": "清理結果", # 新增
        "batch_process": "批次處理" # 新增
    },
    "suffix_settings": {
        "title": "貼圖後綴設定",
        "instruction": "配置每種貼圖類型的後綴。使用逗號分隔多個後綴。",
        "save": "儲存",
        "cancel": "取消",
        "diffuse": "漫反射/反照率",
        "normal": "法線貼圖",
        "specular": "高光貼圖",
        "glossiness": "光澤度貼圖",
        "roughness": "粗糙度貼圖",
        "displacement": "位移/高度貼圖",
        "metallic": "金屬度貼圖",
        "ao": "環境光遮蔽貼圖",
        "alpha": "透明度貼圖",
        "emissive": "自發光貼圖",
        "sss": "次表面散射貼圖",
        "success": "後綴設定已更新。"
    },
    "about": {
        "title": "關於",
        "content": "CryEngine 貼圖處理器\n\n用於處理 CryEngine 貼圖的工具。\n\n版本: 0.1"
    },
    "errors": {
        "no_model": "未載入模型。",
        "no_model_or_textures": "未載入模型或貼圖。",
        "suffix_load_error": "無法載入後綴設定: {0}",
        "suffix_save_error": "無法儲存後綴設定: {0}"
    },
    "language": {
        "title": "語言",
        "changed": "語言已更改為{0}。部分更改將立即生效，但完整更新請重新啟動應用程式。"
    },
    "preferences": {
        "not_implemented": "偏好設定對話框將在此實現。"
    }
}
