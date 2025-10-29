"""
异步润色处理器模块
实现非阻塞的后台润色处理逻辑，保持用户输入流畅性
"""

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication
import time
import logging
from typing import Optional, Callable, Dict, Any
import threading
import queue


class PolishRequest:
    """润色请求数据类"""
    def __init__(self, text: str, request_id: str, timestamp: float = None):
        self.text = text
        self.request_id = request_id
        self.timestamp = timestamp or time.time()
        self.status = "pending"  # pending, processing, completed, failed
        self.result = None
        self.error = None


class AsyncPolishWorker(QObject):
    """异步润色工作线程"""
    
    # 信号定义
    polish_started = Signal(str)  # request_id
    polish_progress = Signal(str, str)  # request_id, progress_message
    polish_completed = Signal(str, str)  # request_id, result
    polish_failed = Signal(str, str)  # request_id, error_message
    
    def __init__(self, ai_client, parent=None):
        super().__init__(parent)
        self.ai_client = ai_client
        self.is_running = True
        self.request_queue = queue.Queue()
        self.current_request = None
        
        # 启动工作线程
        self.worker_thread = threading.Thread(target=self._process_requests, daemon=True)
        self.worker_thread.start()
    
    def add_request(self, request: PolishRequest):
        """添加润色请求到队列"""
        self.request_queue.put(request)
    
    def stop(self):
        """停止工作线程"""
        self.is_running = False
        # 添加停止信号到队列
        self.request_queue.put(None)
    
    def _process_requests(self):
        """处理请求队列的主循环"""
        while self.is_running:
            try:
                # 从队列获取请求
                request = self.request_queue.get(timeout=1.0)
                
                if request is None:  # 停止信号
                    break
                
                self.current_request = request
                self._process_single_request(request)
                
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"处理请求时发生错误: {e}")
                if self.current_request:
                    self.polish_failed.emit(self.current_request.request_id, str(e))
    
    def _process_single_request(self, request: PolishRequest):
        """处理单个润色请求"""
        try:
            # 发送开始信号
            self.polish_started.emit(request.request_id)
            request.status = "processing"
            
            # 发送进度信号
            self.polish_progress.emit(request.request_id, "正在连接AI服务...")
            
            # 调用AI客户端进行润色
            if not self.ai_client:
                raise Exception("AI客户端未初始化")
            
            self.polish_progress.emit(request.request_id, "正在处理文本...")
            
            # 执行润色
            result = self.ai_client.polish_text(request.text)
            
            if result:
                request.status = "completed"
                request.result = result
                self.polish_completed.emit(request.request_id, result)
            else:
                raise Exception("润色结果为空")
                
        except Exception as e:
            request.status = "failed"
            request.error = str(e)
            self.polish_failed.emit(request.request_id, str(e))


class AsyncPolishProcessor(QObject):
    """异步润色处理器主类"""
    
    # 信号定义
    polish_started = Signal(str)  # request_id
    polish_progress = Signal(str, str)  # request_id, progress_message
    polish_completed = Signal(str, str)  # request_id, result
    polish_failed = Signal(str, str)  # request_id, error_message
    
    def __init__(self, ai_client, parent=None):
        super().__init__(parent)
        self.ai_client = ai_client
        self.worker = None
        self.requests: Dict[str, PolishRequest] = {}
        self.request_counter = 0
        
        # 性能监控
        self.response_times = []
        self.max_response_time = 100  # 100ms目标
        
        # 初始化工作线程
        self._init_worker()
    
    def _init_worker(self):
        """初始化工作线程"""
        if self.worker:
            self.worker.stop()
        
        self.worker = AsyncPolishWorker(self.ai_client)
        
        # 连接信号
        self.worker.polish_started.connect(self._on_polish_started)
        self.worker.polish_progress.connect(self._on_polish_progress)
        self.worker.polish_completed.connect(self._on_polish_completed)
        self.worker.polish_failed.connect(self._on_polish_failed)
    
    def polish_text_async(self, text: str) -> str:
        """异步润色文本，立即返回请求ID"""
        start_time = time.time()
        
        # 生成请求ID
        self.request_counter += 1
        request_id = f"polish_{self.request_counter}_{int(time.time() * 1000)}"
        
        # 创建请求
        request = PolishRequest(text, request_id, start_time)
        self.requests[request_id] = request
        
        # 添加到处理队列
        if self.worker:
            self.worker.add_request(request)
        
        # 记录响应时间
        response_time = (time.time() - start_time) * 1000  # 转换为毫秒
        self.response_times.append(response_time)
        
        # 保持最近100次的响应时间记录
        if len(self.response_times) > 100:
            self.response_times.pop(0)
        
        # 检查响应时间是否超标
        if response_time > self.max_response_time:
            logging.warning(f"响应时间超标: {response_time:.2f}ms > {self.max_response_time}ms")
        
        return request_id
    
    def get_request_status(self, request_id: str) -> Optional[str]:
        """获取请求状态"""
        request = self.requests.get(request_id)
        return request.status if request else None
    
    def get_request_result(self, request_id: str) -> Optional[str]:
        """获取请求结果"""
        request = self.requests.get(request_id)
        return request.result if request and request.status == "completed" else None
    
    def cancel_request(self, request_id: str) -> bool:
        """取消请求"""
        request = self.requests.get(request_id)
        if request and request.status == "pending":
            request.status = "cancelled"
            return True
        return False
    
    def get_average_response_time(self) -> float:
        """获取平均响应时间（毫秒）"""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        return {
            "average_response_time": self.get_average_response_time(),
            "max_response_time": max(self.response_times) if self.response_times else 0,
            "min_response_time": min(self.response_times) if self.response_times else 0,
            "total_requests": len(self.requests),
            "pending_requests": len([r for r in self.requests.values() if r.status == "pending"]),
            "processing_requests": len([r for r in self.requests.values() if r.status == "processing"]),
            "completed_requests": len([r for r in self.requests.values() if r.status == "completed"]),
            "failed_requests": len([r for r in self.requests.values() if r.status == "failed"])
        }
    
    def cleanup_old_requests(self, max_age_seconds: int = 300):
        """清理旧的请求记录（默认5分钟）"""
        current_time = time.time()
        old_request_ids = []
        
        for request_id, request in self.requests.items():
            if current_time - request.timestamp > max_age_seconds:
                if request.status in ["completed", "failed", "cancelled"]:
                    old_request_ids.append(request_id)
        
        for request_id in old_request_ids:
            del self.requests[request_id]
        
        if old_request_ids:
            logging.info(f"清理了 {len(old_request_ids)} 个旧请求记录")
    
    def _on_polish_started(self, request_id: str):
        """处理润色开始信号"""
        self.polish_started.emit(request_id)
    
    def _on_polish_progress(self, request_id: str, progress_message: str):
        """处理润色进度信号"""
        self.polish_progress.emit(request_id, progress_message)
    
    def _on_polish_completed(self, request_id: str, result: str):
        """处理润色完成信号"""
        self.polish_completed.emit(request_id, result)
    
    def _on_polish_failed(self, request_id: str, error_message: str):
        """处理润色失败信号"""
        self.polish_failed.emit(request_id, error_message)
    
    def shutdown(self):
        """关闭处理器"""
        if self.worker:
            self.worker.stop()
        
        # 清理定时器
        self.cleanup_old_requests(0)  # 清理所有请求
        
        logging.info("异步润色处理器已关闭")


class HeartbeatManager(QObject):
    """心跳管理器 - 保持API连接稳定"""
    
    # 信号定义
    heartbeat_sent = Signal()
    heartbeat_failed = Signal(str)  # error_message
    connection_status_changed = Signal(bool)  # is_connected
    
    def __init__(self, ai_client, interval_seconds: int = 30, parent=None):
        super().__init__(parent)
        self.ai_client = ai_client
        self.interval_seconds = interval_seconds
        self.is_connected = False
        self.consecutive_failures = 0
        self.max_failures = 3
        
        # 创建心跳定时器
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self._send_heartbeat)
        self.heartbeat_timer.setInterval(interval_seconds * 1000)  # 转换为毫秒
        
        # 【性能优化】不在初始化时立即启动心跳
        # 而是等待主窗口调用force_reconnect来执行首次检查
        # 这样可以与API预热配合，避免重复的连接测试
        # 启动心跳定时器（但首次检查由外部触发）
        self.start()
    
    def start(self):
        """启动心跳定时器"""
        self.heartbeat_timer.start()
        logging.info(f"心跳管理器已启动，间隔: {self.interval_seconds}秒")
        logging.info(f"提示：首次心跳检查将在{self.interval_seconds}秒后自动执行，或调用force_reconnect()立即执行")
    
    def stop(self):
        """停止心跳"""
        self.heartbeat_timer.stop()
        logging.info("心跳管理器已停止")
    
    def _send_heartbeat(self):
        """轻量级心跳 - 只检查连接池状态，不发送真实请求"""
        try:
            # 始终使用轻量级检查（不发送HTTP请求）
            if self.ai_client and hasattr(self.ai_client, 'check_connection_alive'):
                is_alive = self.ai_client.check_connection_alive()
                
                if is_alive:
                    # 连接池存在，认为连接正常
                    self.consecutive_failures = 0
                    if not self.is_connected:
                        self.is_connected = True
                        self.connection_status_changed.emit(True)
                        logging.info("API连接已建立")
                    self.heartbeat_sent.emit()
                else:
                    # 连接池不存在，标记可能断开
                    self._handle_heartbeat_failure("连接池未就绪")
            else:
                # 如果没有轻量级检查方法，假设连接正常
                # （避免发送实际请求浪费资源）
                self.consecutive_failures = 0
                if not self.is_connected:
                    self.is_connected = True
                    self.connection_status_changed.emit(True)
                self.heartbeat_sent.emit()
                    
        except Exception as e:
            self._handle_heartbeat_failure(f"心跳检查异常: {str(e)}")
    
    def _handle_heartbeat_failure(self, error_message: str):
        """处理心跳失败"""
        self.consecutive_failures += 1
        logging.warning(f"心跳失败 ({self.consecutive_failures}/{self.max_failures}): {error_message}")
        
        if self.consecutive_failures >= self.max_failures:
            if self.is_connected:
                self.is_connected = False
                self.connection_status_changed.emit(False)
                logging.error("连接已断开")
        
        self.heartbeat_failed.emit(error_message)
    
    def force_reconnect(self):
        """强制重连 - 立即执行一次心跳检查
        
        该方法通常在以下情况调用：
        1. 程序启动时，配合API预热
        2. 用户手动触发重连
        3. 检测到连接断开后尝试恢复
        """
        logging.info("强制执行心跳检查...")
        self.consecutive_failures = 0
        self._send_heartbeat()
    
    def get_connection_status(self) -> bool:
        """获取连接状态"""
        return self.is_connected
    
    def set_interval(self, seconds: int):
        """设置心跳间隔"""
        self.interval_seconds = seconds
        self.heartbeat_timer.setInterval(seconds * 1000)
        logging.info(f"心跳间隔已更新为: {seconds}秒")