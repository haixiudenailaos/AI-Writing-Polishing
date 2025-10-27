"""
性能优化中间件和缓存管理
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from functools import lru_cache
import time
import logging

logger = logging.getLogger(__name__)

class PerformanceMiddleware(BaseHTTPMiddleware):
    """性能监控中间件"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # 记录慢请求
        if process_time > 2.0:  # 超过2秒
            logger.warning(f"慢请求: {request.url.path} - {process_time:.2f}秒")
        
        return response

class CacheManager:
    """简单的缓存管理器"""
    
    def __init__(self, max_size=100, ttl=300):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
    
    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, key, value):
        if len(self.cache) >= self.max_size:
            # 删除最旧的项
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        
        self.cache[key] = (value, time.time())
    
    def clear(self):
        self.cache.clear()

# 全局缓存实例
polish_cache = CacheManager(max_size=200, ttl=600)  # 10分钟缓存
