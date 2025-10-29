"""
请求队列管理器
用于协调润色和预测请求，避免并发冲突
"""

import queue
import threading
import logging
from typing import Callable, Optional, Any
from enum import Enum
from PySide6.QtCore import QObject, Signal


class RequestType(Enum):
    """请求类型"""
    POLISH = "polish"  # 润色请求
    PREDICTION = "prediction"  # 预测请求


class RequestPriority(Enum):
    """请求优先级"""
    HIGH = 1    # 高优先级（润色）
    NORMAL = 2  # 普通优先级
    LOW = 3     # 低优先级（预测）


class Request:
    """请求对象"""
    
    def __init__(
        self,
        request_id: str,
        request_type: RequestType,
        priority: RequestPriority,
        execute_func: Callable,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        **kwargs
    ):
        self.request_id = request_id
        self.request_type = request_type
        self.priority = priority
        self.execute_func = execute_func
        self.on_success = on_success
        self.on_error = on_error
        self.kwargs = kwargs
        self.status = "pending"  # pending, executing, completed, failed, cancelled
        self.result = None
        self.error = None
    
    def __lt__(self, other):
        """用于优先级队列排序"""
        return self.priority.value < other.priority.value


class RequestQueueManager(QObject):
    """请求队列管理器 - 确保请求按顺序执行，避免冲突"""
    
    # 信号定义
    request_started = Signal(str, str)  # request_id, request_type
    request_completed = Signal(str, object)  # request_id, result
    request_failed = Signal(str, str)  # request_id, error_message
    queue_status_changed = Signal(int)  # queue_size
    
    def __init__(self, max_concurrent: int = 1, parent=None):
        """
        初始化请求队列管理器
        
        Args:
            max_concurrent: 最大并发请求数（默认1，确保同一时间只有一个请求执行）
            parent: Qt父对象
        """
        super().__init__(parent)
        self.max_concurrent = max_concurrent
        
        # 使用优先级队列
        self.request_queue = queue.PriorityQueue()
        
        # 当前执行中的请求
        self.executing_requests = {}
        
        # 请求历史记录（最近100个）
        self.request_history = []
        self.max_history = 100
        
        # 线程控制
        self.is_running = True
        self.lock = threading.Lock()
        
        # 启动工作线程
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        
        logging.info("请求队列管理器已启动")
    
    def add_request(
        self,
        request_id: str,
        request_type: RequestType,
        priority: RequestPriority,
        execute_func: Callable,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        **kwargs
    ) -> str:
        """
        添加请求到队列
        
        Args:
            request_id: 请求ID
            request_type: 请求类型
            priority: 优先级
            execute_func: 执行函数
            on_success: 成功回调
            on_error: 失败回调
            **kwargs: 额外参数
        
        Returns:
            request_id: 请求ID
        """
        request = Request(
            request_id=request_id,
            request_type=request_type,
            priority=priority,
            execute_func=execute_func,
            on_success=on_success,
            on_error=on_error,
            **kwargs
        )
        
        self.request_queue.put(request)
        queue_size = self.request_queue.qsize()
        self.queue_status_changed.emit(queue_size)
        
        logging.info(f"请求已加入队列: {request_id} ({request_type.value}), 队列长度: {queue_size}")
        
        return request_id
    
    def cancel_request(self, request_id: str) -> bool:
        """取消请求（仅能取消未执行的请求）"""
        with self.lock:
            # 检查是否正在执行
            if request_id in self.executing_requests:
                logging.warning(f"请求 {request_id} 正在执行，无法取消")
                return False
            
            # 创建新队列，过滤掉要取消的请求
            new_queue = queue.PriorityQueue()
            cancelled = False
            
            while not self.request_queue.empty():
                try:
                    request = self.request_queue.get_nowait()
                    if request.request_id == request_id:
                        request.status = "cancelled"
                        cancelled = True
                        logging.info(f"请求已取消: {request_id}")
                    else:
                        new_queue.put(request)
                except queue.Empty:
                    break
            
            self.request_queue = new_queue
            return cancelled
    
    def cancel_all_requests_of_type(self, request_type: RequestType) -> int:
        """取消特定类型的所有待执行请求"""
        with self.lock:
            new_queue = queue.PriorityQueue()
            cancelled_count = 0
            
            while not self.request_queue.empty():
                try:
                    request = self.request_queue.get_nowait()
                    if request.request_type == request_type and request.status == "pending":
                        request.status = "cancelled"
                        cancelled_count += 1
                        logging.info(f"请求已取消: {request.request_id}")
                    else:
                        new_queue.put(request)
                except queue.Empty:
                    break
            
            self.request_queue = new_queue
            logging.info(f"已取消 {cancelled_count} 个 {request_type.value} 类型的请求")
            return cancelled_count
    
    def _process_queue(self):
        """处理请求队列的主循环"""
        while self.is_running:
            try:
                # 检查是否可以执行新请求
                with self.lock:
                    can_execute = len(self.executing_requests) < self.max_concurrent
                
                if not can_execute:
                    # 等待一段时间再检查
                    threading.Event().wait(0.1)
                    continue
                
                # 从队列获取请求（阻塞，超时1秒）
                try:
                    request = self.request_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # 检查请求是否已被取消
                if request.status == "cancelled":
                    continue
                
                # 执行请求
                self._execute_request(request)
                
            except Exception as e:
                logging.error(f"处理请求队列时发生错误: {e}", exc_info=True)
    
    def _execute_request(self, request: Request):
        """执行单个请求"""
        try:
            # 标记为执行中
            with self.lock:
                request.status = "executing"
                self.executing_requests[request.request_id] = request
            
            # 发送开始信号
            self.request_started.emit(request.request_id, request.request_type.value)
            
            logging.info(f"开始执行请求: {request.request_id} ({request.request_type.value})")
            
            # 执行请求
            logging.info(f"开始执行请求函数: {request.request_id}")
            print(f"[DEBUG] 请求队列管理器：开始执行 {request.request_id}", flush=True)
            result = request.execute_func(**request.kwargs)
            print(f"[DEBUG] 请求队列管理器：执行完成 {request.request_id}, result类型: {type(result)}", flush=True)
            
            # 标记为完成
            with self.lock:
                request.status = "completed"
                request.result = result
                self.executing_requests.pop(request.request_id, None)
                self._add_to_history(request)
            
            # 发送完成信号
            self.request_completed.emit(request.request_id, result)
            
            # 调用成功回调（在后台线程中，需要确保回调能处理线程安全问题）
            if request.on_success:
                try:
                    # 直接在后台线程调用回调，回调函数自己负责线程安全
                    logging.info(f"调用成功回调: {request.request_id}")
                    print(f"[DEBUG] 请求队列管理器：调用成功回调 {request.request_id}", flush=True)
                    request.on_success(result)
                    print(f"[DEBUG] 请求队列管理器：成功回调完成 {request.request_id}", flush=True)
                except Exception as e:
                    logging.error(f"执行成功回调时发生错误: {e}", exc_info=True)
                    print(f"[ERROR] 请求队列管理器：成功回调失败 {request.request_id}: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
            
            logging.info(f"请求执行完成: {request.request_id}")
            
        except Exception as e:
            # 标记为失败
            error_message = str(e)
            with self.lock:
                request.status = "failed"
                request.error = error_message
                self.executing_requests.pop(request.request_id, None)
                self._add_to_history(request)
            
            # 发送失败信号
            self.request_failed.emit(request.request_id, error_message)
            
            # 调用失败回调
            if request.on_error:
                try:
                    request.on_error(error_message)
                except Exception as callback_error:
                    logging.error(f"执行失败回调时发生错误: {callback_error}", exc_info=True)
            
            logging.error(f"请求执行失败: {request.request_id}, 错误: {error_message}")
        
        finally:
            # 更新队列状态
            queue_size = self.request_queue.qsize()
            self.queue_status_changed.emit(queue_size)
    
    def _add_to_history(self, request: Request):
        """添加到历史记录"""
        self.request_history.append({
            "request_id": request.request_id,
            "request_type": request.request_type.value,
            "status": request.status,
            "error": request.error
        })
        
        # 保持历史记录在限制范围内
        if len(self.request_history) > self.max_history:
            self.request_history.pop(0)
    
    def get_queue_size(self) -> int:
        """获取队列中等待的请求数"""
        return self.request_queue.qsize()
    
    def get_executing_count(self) -> int:
        """获取正在执行的请求数"""
        with self.lock:
            return len(self.executing_requests)
    
    def get_status(self) -> dict:
        """获取队列管理器状态"""
        with self.lock:
            return {
                "queue_size": self.request_queue.qsize(),
                "executing_count": len(self.executing_requests),
                "executing_requests": list(self.executing_requests.keys()),
                "max_concurrent": self.max_concurrent
            }
    
    def clear_queue(self):
        """清空队列（不影响正在执行的请求）"""
        with self.lock:
            cleared = 0
            while not self.request_queue.empty():
                try:
                    self.request_queue.get_nowait()
                    cleared += 1
                except queue.Empty:
                    break
            
            logging.info(f"已清空队列，清除了 {cleared} 个待执行请求")
            self.queue_status_changed.emit(0)
            return cleared
    
    def stop(self):
        """停止队列管理器"""
        self.is_running = False
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
        logging.info("请求队列管理器已停止")

