"""
自动保存管理器
每30秒自动保存编辑器内容到文件
"""

import logging
from typing import Optional, Callable
from PySide6 import QtCore


class AutoSaveManager(QtCore.QObject):
    """自动保存管理器"""
    
    # 信号定义
    save_triggered = QtCore.Signal()  # 触发保存
    save_completed = QtCore.Signal(bool, str)  # 保存完成 (success, message)
    
    def __init__(self, interval_seconds: int = 30, parent=None):
        """
        初始化自动保存管理器
        
        Args:
            interval_seconds: 自动保存间隔（秒），默认30秒
            parent: Qt父对象
        """
        super().__init__(parent)
        self.interval_seconds = interval_seconds
        self.is_enabled = False
        self.current_file_path: Optional[str] = None
        self.get_content_func: Optional[Callable] = None
        self.save_func: Optional[Callable] = None
        
        # 创建定时器
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._perform_auto_save)
        self.timer.setInterval(interval_seconds * 1000)  # 转换为毫秒
        
        # 记录最后保存时间
        self.last_save_time = None
        self.save_count = 0
        
        logging.info(f"自动保存管理器已创建，间隔: {interval_seconds}秒")
    
    def start(self, file_path: str, get_content_func: Callable, save_func: Callable):
        """
        启动自动保存
        
        Args:
            file_path: 要保存的文件路径
            get_content_func: 获取内容的函数（返回str）
            save_func: 保存函数（接收file_path和content参数，返回bool）
        """
        self.current_file_path = file_path
        self.get_content_func = get_content_func
        self.save_func = save_func
        self.is_enabled = True
        self.save_count = 0
        
        # 启动定时器
        self.timer.start()
        
        logging.info(f"自动保存已启动: {file_path}, 间隔: {self.interval_seconds}秒")
        print(f"[INFO] 自动保存已启动: 每{self.interval_seconds}秒保存一次", flush=True)
    
    def stop(self):
        """停止自动保存"""
        self.timer.stop()
        self.is_enabled = False
        
        logging.info(f"自动保存已停止，共保存{self.save_count}次")
        print(f"[INFO] 自动保存已停止，共保存{self.save_count}次", flush=True)
    
    def pause(self):
        """暂停自动保存（保留配置）"""
        self.timer.stop()
        logging.info("自动保存已暂停")
    
    def resume(self):
        """恢复自动保存"""
        if self.is_enabled and self.current_file_path:
            self.timer.start()
            logging.info("自动保存已恢复")
    
    def _perform_auto_save(self):
        """执行自动保存"""
        if not self.is_enabled or not self.current_file_path:
            return
        
        if not self.get_content_func or not self.save_func:
            logging.warning("自动保存失败：缺少必要的函数")
            return
        
        try:
            # 获取当前内容
            content = self.get_content_func()
            
            if content is None:
                logging.warning("自动保存跳过：内容为空")
                return
            
            # 执行保存
            success = self.save_func(self.current_file_path, content)
            
            if success:
                self.save_count += 1
                self.last_save_time = QtCore.QDateTime.currentDateTime()
                
                time_str = self.last_save_time.toString("hh:mm:ss")
                message = f"已自动保存 ({time_str})"
                
                logging.info(f"自动保存成功 #{self.save_count}: {self.current_file_path}")
                print(f"[INFO] {message}", flush=True)
                
                self.save_completed.emit(True, message)
            else:
                error_msg = "自动保存失败"
                logging.error(error_msg)
                self.save_completed.emit(False, error_msg)
        
        except Exception as e:
            error_msg = f"自动保存异常: {str(e)}"
            logging.error(error_msg, exc_info=True)
            self.save_completed.emit(False, error_msg)
    
    def save_now(self) -> bool:
        """立即执行一次保存
        
        Returns:
            成功返回True，失败返回False
        """
        if not self.is_enabled or not self.current_file_path:
            return False
        
        try:
            content = self.get_content_func()
            if content is None:
                return False
            
            success = self.save_func(self.current_file_path, content)
            
            if success:
                self.save_count += 1
                self.last_save_time = QtCore.QDateTime.currentDateTime()
                logging.info(f"手动保存成功: {self.current_file_path}")
                self.save_completed.emit(True, "保存成功")
            
            return success
        
        except Exception as e:
            logging.error(f"手动保存失败: {e}", exc_info=True)
            self.save_completed.emit(False, f"保存失败: {str(e)}")
            return False
    
    def update_file_path(self, new_file_path: str):
        """更新保存的文件路径（例如另存为）"""
        old_path = self.current_file_path
        self.current_file_path = new_file_path
        logging.info(f"自动保存文件路径已更新: {old_path} -> {new_file_path}")
    
    def get_status(self) -> dict:
        """获取自动保存状态"""
        return {
            "enabled": self.is_enabled,
            "file_path": self.current_file_path,
            "interval_seconds": self.interval_seconds,
            "save_count": self.save_count,
            "last_save_time": self.last_save_time.toString("yyyy-MM-dd hh:mm:ss") if self.last_save_time else None,
            "is_running": self.timer.isActive()
        }
    
    def set_interval(self, seconds: int):
        """设置自动保存间隔
        
        Args:
            seconds: 新的间隔时间（秒）
        """
        if seconds < 10:
            logging.warning("自动保存间隔不能小于10秒")
            return
        
        self.interval_seconds = seconds
        self.timer.setInterval(seconds * 1000)
        logging.info(f"自动保存间隔已更新为: {seconds}秒")

