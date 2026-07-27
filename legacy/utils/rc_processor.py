#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RC Processor

這個模組提供了調用CryEngine Resource Compiler (RC.exe)處理JSON配置文件的功能，
將其轉換為CryEngine的.cgf格式。
"""

import os
import subprocess
import threading
from utils.config_manager import ConfigManager
from language.language_manager import get_text

class RCProcessor:
    """
    用於處理JSON配置文件並生成CryEngine模型格式的處理器類。
    """
    
    def __init__(self):
        """
        初始化RC處理器。
        """
        self.config_manager = ConfigManager()
        self.rc_exe_path = self.config_manager.get("rc_exe_path", "")
        self.processing_thread = None
        self.cancel_flag = False
        self.progress_callback = None
    
    def set_progress_callback(self, callback):
        """
        設置進度回調函數。
        
        Args:
            callback: 接收進度(0.0-1.0)、當前任務和狀態的回調函數
        """
        self.progress_callback = callback
    
    def process_json_file(self, json_path, output_cgf_path=None):
        """
        處理單個JSON配置文件，生成CGF模型。
        
        Args:
            json_path: JSON配置文件的路徑
            output_cgf_path: 可選的輸出CGF文件路徑。如果未提供，將使用與JSON相同的基本名稱。
            
        Returns:
            如果處理成功開始，則為True，否則為False
        """
        # 檢查RC.exe路徑是否已設置
        if not self.rc_exe_path:
            print("RC.exe路徑未設置")
            return False
        
        # 檢查RC.exe是否存在
        if not os.path.exists(self.rc_exe_path):
            print(f"在{self.rc_exe_path}找不到RC.exe")
            return False
        
        # 檢查是否已經在處理中
        if self.processing_thread and self.processing_thread.is_alive():
            return False
            
        # 重置取消標誌
        self.cancel_flag = False
        
        # 如果沒有指定輸出CGF路徑，則使用與JSON相同的基本名稱
        if not output_cgf_path:
            output_cgf_path = os.path.splitext(json_path)[0] + ".cgf"
        
        # 啟動處理線程
        self.processing_thread = threading.Thread(
            target=self._process_thread,
            args=(json_path, output_cgf_path),
            daemon=True
        )
        self.processing_thread.start()
        
        return True
    
    def _process_thread(self, json_path, output_cgf_path):
        """
        處理JSON文件的線程函數。
        
        Args:
            json_path: JSON配置文件的路徑
            output_cgf_path: 輸出CGF文件的路徑
        """
        try:
            # 檢查是否取消處理
            if self.cancel_flag:
                return False
            
            # 檢查文件是否存在
            if not os.path.exists(json_path):
                if self.progress_callback:
                    self.progress_callback(
                        0.0,
                        "錯誤: 找不到JSON文件",
                        f"文件不存在: {json_path}"
                    )
                return False
            
            # 獲取文件名和目錄
            json_filename = os.path.basename(json_path)
            output_filename = os.path.basename(output_cgf_path)
            
            # 更新進度
            if self.progress_callback:
                self.progress_callback(
                    0.0,
                    "開始RC.exe處理",
                    f"處理文件: {json_filename} -> {output_filename}"
                )
            
            # 構建RC命令
            # 使用format: RC.exe Tree.json /overwriteextension=fbx /overwritefilename="Tree.cgf"
            base_filename = os.path.splitext(output_filename)[0]
            cmd = [
                self.rc_exe_path,
                json_path,
                "/overwriteextension=fbx",
                f"/overwritefilename=\"{base_filename}.cgf\""
            ]
            
            # 執行命令
            print(f"執行命令: {' '.join(cmd)}")
            if self.progress_callback:
                self.progress_callback(0.3, "調用RC.exe", "正在生成CGF文件...")
            
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True
            )
            
            # 輸出處理結果
            print(f"RC.exe輸出:")
            print(result.stdout)
            
            # 檢查錯誤
            if result.returncode != 0:
                print(f"RC.exe錯誤:")
                print(result.stderr)
                if self.progress_callback:
                    self.progress_callback(
                        1.0,
                        "RC.exe處理失敗",
                        f"錯誤代碼: {result.returncode}"
                    )
                return False
            
            # 檢查生成的文件是否存在
            if os.path.exists(output_cgf_path):
                print(f"成功生成CGF文件: {output_cgf_path}")
                if self.progress_callback:
                    self.progress_callback(
                        1.0,
                        "RC.exe處理完成",
                        f"生成文件: {output_filename}"
                    )
                return True
            else:
                print(f"警告: 雖然RC.exe成功執行，但找不到生成的CGF文件: {output_cgf_path}")
                if self.progress_callback:
                    self.progress_callback(
                        1.0,
                        "RC.exe處理不完整",
                        f"找不到生成的文件: {output_filename}"
                    )
                return False
            
        except Exception as e:
            print(f"處理JSON文件時發生錯誤: {e}")
            if self.progress_callback:
                self.progress_callback(
                    1.0,
                    "RC處理錯誤",
                    f"錯誤: {str(e)}"
                )
            return False
    
    def cancel(self):
        """
        取消正在進行的處理。
        """
        self.cancel_flag = True
    
    def is_processing(self):
        """
        檢查是否正在進行處理。
        
        Returns:
            如果正在處理，則為True，否則為False
        """
        return self.processing_thread is not None and self.processing_thread.is_alive()
