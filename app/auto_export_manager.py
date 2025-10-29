"""实时导出管理器模块

提供编辑器内容的实时同步导出功能，使用防抖机制避免频繁写入磁盘。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Callable
from PySide6 import QtCore


class AutoExportManager(QtCore.QObject):
    """实时导出管理器
    
    负责监听编辑器文本变化，并在用户选择了导出目录时自动保存文本。
    使用防抖机制（debounce）避免频繁写入磁盘。
    
    信号：
        - export_started: 开始导出 (str: 文件路径)
        - export_completed: 导出完成 (str: 文件路径)
        - export_failed: 导出失败 (str: 错误信息)
        - export_status_changed: 导出状态变化 (bool: 是否启用)
    """
    
    # 定义信号
    export_started = QtCore.Signal(str)  # 文件路径
    export_completed = QtCore.Signal(str)  # 文件路径
    export_failed = QtCore.Signal(str)  # 错误信息
    export_status_changed = QtCore.Signal(bool)  # 是否启用
    
    def __init__(self, debounce_ms: int = 2000, parent: Optional[QtCore.QObject] = None) -> None:
        """初始化实时导出管理器
        
        Args:
            debounce_ms: 防抖延迟时间（毫秒），默认2000ms（2秒）
            parent: 父对象
        """
        super().__init__(parent)
        
        self._export_directory: str = ""
        self._export_filename: str = "字见润新.txt"
        self._enabled: bool = False
        self._pending_text: Optional[str] = None
        
        # 防抖定时器
        self._debounce_timer = QtCore.QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(debounce_ms)
        self._debounce_timer.timeout.connect(self._perform_export)
    
    def set_export_directory(self, directory: str) -> None:
        """设置导出目录
        
        Args:
            directory: 导出目录路径
        """
        self._export_directory = directory
        
        # 如果设置了有效目录，自动启用实时导出
        if directory and os.path.isdir(directory):
            self.set_enabled(True)
        else:
            self.set_enabled(False)
    
    def set_export_filename(self, filename: str) -> None:
        """设置导出文件名
        
        Args:
            filename: 导出文件名
        """
        self._export_filename = filename or "字见润新.txt"
    
    def set_enabled(self, enabled: bool) -> None:
        """设置是否启用实时导出
        
        Args:
            enabled: 是否启用
        """
        old_enabled = self._enabled
        self._enabled = enabled
        
        if old_enabled != enabled:
            self.export_status_changed.emit(enabled)
        
        # 如果禁用了，取消待处理的导出
        if not enabled:
            self._debounce_timer.stop()
            self._pending_text = None
    
    def is_enabled(self) -> bool:
        """检查是否启用实时导出"""
        return self._enabled and bool(self._export_directory)
    
    def get_export_path(self) -> Optional[str]:
        """获取完整的导出文件路径"""
        if not self._export_directory:
            return None
        return os.path.join(self._export_directory, self._export_filename)
    
    def request_export(self, text: str) -> None:
        """请求导出文本（使用防抖机制）
        
        Args:
            text: 要导出的文本内容
        """
        # 如果未启用或未设置导出目录，直接返回
        if not self.is_enabled():
            return
        
        # 更新待导出文本
        self._pending_text = text
        
        # 重启防抖定时器
        self._debounce_timer.stop()
        self._debounce_timer.start()
    
    def _perform_export(self) -> None:
        """执行实际的导出操作"""
        if not self._pending_text:
            return
        
        export_path = self.get_export_path()
        if not export_path:
            self.export_failed.emit("导出路径未设置")
            return
        
        try:
            # 发送开始信号
            self.export_started.emit(export_path)
            
            # 确保目录存在
            export_dir = Path(export_path).parent
            export_dir.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            with open(export_path, 'w', encoding='utf-8') as f:
                f.write(self._pending_text)
            
            # 发送完成信号
            self.export_completed.emit(export_path)
            
        except Exception as e:
            # 发送失败信号
            self.export_failed.emit(f"导出失败: {str(e)}")
    
    def export_now(self, text: str) -> bool:
        """立即导出文本（不使用防抖机制）
        
        Args:
            text: 要导出的文本内容
            
        Returns:
            是否导出成功
        """
        if not self._export_directory:
            return False
        
        export_path = self.get_export_path()
        if not export_path:
            return False
        
        try:
            # 发送开始信号
            self.export_started.emit(export_path)
            
            # 确保目录存在
            export_dir = Path(export_path).parent
            export_dir.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            with open(export_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            # 发送完成信号
            self.export_completed.emit(export_path)
            return True
            
        except Exception as e:
            # 发送失败信号
            self.export_failed.emit(f"导出失败: {str(e)}")
            return False
    
    def clear_export_directory(self) -> None:
        """清除导出目录设置"""
        self._export_directory = ""
        self.set_enabled(False)

