"""
FastAPI 后端主程序
提供小说润色的Web API服务
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import asyncio
from datetime import datetime
import logging

# 导入现有的业务逻辑模块
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "app"))

from api_client import AIClient, AIError
from config_manager import ConfigManager
from text_processor import TextProcessor
from preset_styles import get_preset_styles, get_combined_prompt

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="小说润色Web API",
    description="基于AI的小说润色服务",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局实例
config_manager = ConfigManager()
ai_client = AIClient(config_manager=config_manager)
text_processor = TextProcessor()

# WebSocket连接管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"新WebSocket连接，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket断开，当前连接数: {len(self.active_connections)}")
    
    async def send_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

# 请求模型
class PolishRequest(BaseModel):
    context_lines: List[str] = []
    target_line: str
    line_number: int
    style_prompt: Optional[str] = None

class PredictRequest(BaseModel):
    full_text: str
    style_prompt: Optional[str] = None

class ConfigUpdateRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    timeout: Optional[int] = None

class TestConnectionRequest(BaseModel):
    api_key: str
    base_url: Optional[str] = None
    model: Optional[str] = None

class ThemeRequest(BaseModel):
    theme_key: str

class OptimizePromptRequest(BaseModel):
    original_prompt: str
    context: Optional[str] = None  # 用户说明的上下文

# 响应模型
class PolishResponse(BaseModel):
    success: bool
    original_text: str
    polished_text: Optional[str] = None
    line_number: int
    error: Optional[str] = None
    timestamp: str

class PredictResponse(BaseModel):
    success: bool
    predictions: List[str]
    error: Optional[str] = None
    timestamp: str

class OptimizePromptResponse(BaseModel):
    success: bool
    optimized_prompt: Optional[str] = None
    error: Optional[str] = None
    timestamp: str

# API路由
@app.get("/")
async def root():
    """API根路径"""
    return {
        "message": "小说润色Web API",
        "version": "1.0.0",
        "endpoints": {
            "polish": "/api/polish",
            "predict": "/api/predict",
            "config": "/api/config",
            "health": "/api/health"
        }
    }

@app.get("/api/health")
async def health_check():
    """健康检查"""
    try:
        # 测试AI连接
        result = ai_client.test_connection()
        return {
            "status": "healthy",
            "api_connection": result.get("success", False),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/api/polish", response_model=PolishResponse)
async def polish_text(request: PolishRequest):
    """润色文本接口"""
    try:
        logger.info(f"收到润色请求，行号: {request.line_number}")
        
        # 为每个请求创建独立的AI客户端实例，避免并发问题
        client = AIClient(config_manager=config_manager)
        
        # 调用AI润色
        polished_text = client.polish_last_line(
            context_lines=request.context_lines,
            target_line=request.target_line,
            style_prompt=request.style_prompt or ""
        )
        
        return PolishResponse(
            success=True,
            original_text=request.target_line,
            polished_text=polished_text,
            line_number=request.line_number,
            timestamp=datetime.now().isoformat()
        )
    
    except AIError as e:
        logger.error(f"AI润色失败: {str(e)}")
        return PolishResponse(
            success=False,
            original_text=request.target_line,
            line_number=request.line_number,
            error=str(e),
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        logger.error(f"润色请求处理失败: {str(e)}")
        return PolishResponse(
            success=False,
            original_text=request.target_line,
            line_number=request.line_number,
            error=f"服务器错误: {str(e)}",
            timestamp=datetime.now().isoformat()
        )

@app.post("/api/predict", response_model=PredictResponse)
async def predict_plot(request: PredictRequest):
    """剧情预测接口"""
    try:
        # 验证输入内容不为空
        if not request.full_text or not request.full_text.strip():
            return PredictResponse(
                success=False,
                predictions=[],
                error="文本内容为空，无需预测",
                timestamp=datetime.now().isoformat()
            )
        
        logger.info("收到剧情预测请求")
        
        # 为每个请求创建独立的AI客户端实例，避免并发问题
        client = AIClient(config_manager=config_manager)
        
        # 调用AI预测，传递风格提示词
        predicted_text = client.predict_plot_continuation(
            request.full_text,
            style_prompt=request.style_prompt or ""
        )
        
        # 解析预测的两行内容
        # 分割成行，去除空行和空白字符
        lines = [line.strip() for line in predicted_text.strip().split('\n') if line.strip()]
        
        # 确保只取前两行
        predictions = lines[:2] if len(lines) >= 2 else lines
        
        # 如果只有一行，记录警告
        if len(predictions) < 2:
            logger.warning(f"预测结果不足2行，实际返回{len(predictions)}行")
        
        return PredictResponse(
            success=True,
            predictions=predictions,
            timestamp=datetime.now().isoformat()
        )
    
    except AIError as e:
        logger.error(f"AI预测失败: {str(e)}")
        return PredictResponse(
            success=False,
            predictions=[],
            error=str(e),
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        logger.error(f"预测请求处理失败: {str(e)}")
        return PredictResponse(
            success=False,
            predictions=[],
            error=f"服务器错误: {str(e)}",
            timestamp=datetime.now().isoformat()
        )

@app.get("/api/config")
async def get_config():
    """获取当前配置"""
    try:
        config = config_manager.get_config()
        api_config = config.api_config
        
        return {
            "success": True,
            "config": {
                "model": api_config.model,
                "base_url": api_config.base_url,
                "timeout": api_config.timeout,
                "has_api_key": bool(api_config.api_key)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config")
async def update_config(request: ConfigUpdateRequest):
    """更新配置"""
    try:
        if request.api_key:
            config_manager.update_api_config(
                api_key=request.api_key,
                base_url=request.base_url,
                model=request.model,
                timeout=request.timeout
            )
            
            # 更新AI客户端配置
            ai_client.update_config(config_manager)
            
            return {"success": True, "message": "配置已更新"}
        else:
            raise HTTPException(status_code=400, detail="API密钥不能为空")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/test-connection")
async def test_connection(request: TestConnectionRequest):
    """测试API连接"""
    try:
        # 创建临时AI客户端测试连接
        test_client = AIClient(
            api_key=request.api_key,
            base_url=request.base_url or None,
            model=request.model or None
        )
        
        # 调用测试方法
        result = test_client.test_connection()
        
        if result.get("success"):
            return {
                "success": True,
                "message": "连接成功！"
            }
        else:
            return {
                "success": False,
                "message": result.get("message", "连接失败")
            }
    
    except Exception as e:
        logger.error(f"测试连接失败: {str(e)}")
        return {
            "success": False,
            "message": f"测试失败: {str(e)}"
        }


@app.get("/api/preset-styles")
async def get_preset_styles_api():
    """获取所有预设润色风格"""
    try:
        styles = get_preset_styles()
        return {"success": True, "styles": styles}
    except Exception as e:
        logger.error(f"获取预设风格失败: {str(e)}")
        return {"success": False, "message": str(e)}

@app.post("/api/optimize-prompt", response_model=OptimizePromptResponse)
async def optimize_prompt(request: OptimizePromptRequest):
    """使用AI优化用户输入的提示词"""
    try:
        logger.info("收到提示词优化请求")
        
        # 为每个请求创建独立的AI客户端实例
        client = AIClient(config_manager=config_manager)
        
        # 构建优化提示词的系统提示
        system_prompt = """你是一位专业的AI提示词（Prompt）工程师，擅长优化和改进用于文本生成的提示词。

你的任务是对用户提供的润色风格提示词进行优化，使其：

1. **更加具体明确**：
   - 将模糊的描述转化为具体的指导
   - 明确指出润色的具体方向和要求
   - 使用可操作的标准和示例

2. **结构化表达**：
   - 使用分点列表和清晰的层次结构
   - 将不同维度的要求分开说明
   - 添加必要的标题和分类

3. **贴近功能场景**：
   - 明确这是用于小说文本润色的提示词
   - 强调保持原文核心内容和情节
   - 注重文学性、可读性和语言表达

4. **增强可执行性**：
   - 提供具体的评判标准
   - 给出明确的做与不做
   - 包含关键的注意事项

请直接返回优化后的提示词，不要包含任何解释或其他内容。优化后的提示词应该可以直接使用。"""
        
        # 构建用户输入
        user_content = f"""请优化以下润色风格提示词：

{request.original_prompt}"""
        
        # 如果有上下文说明，添加到用户输入中
        if request.context:
            user_content += f"\n\n补充说明：{request.context}"
        
        # 调用AI进行优化
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        # 使用AI客户端的通用方法
        response = client._call_api(messages, temperature=0.7)
        optimized_prompt = response.strip()
        
        return OptimizePromptResponse(
            success=True,
            optimized_prompt=optimized_prompt,
            timestamp=datetime.now().isoformat()
        )
    
    except AIError as e:
        logger.error(f"AI优化提示词失败: {str(e)}")
        return OptimizePromptResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        logger.error(f"优化提示词请求处理失败: {str(e)}")
        return OptimizePromptResponse(
            success=False,
            error=f"服务器错误: {str(e)}",
            timestamp=datetime.now().isoformat()
        )

@app.get("/api/themes")
async def get_themes():
    """获取可用主题列表"""
    from widgets.theme_manager import THEME_CATALOG
    
    themes = []
    for key, theme_data in THEME_CATALOG.items():
        themes.append({
            "key": key,
            "label": theme_data.get("label", key),
            "colors": theme_data
        })
    
    return {"success": True, "themes": themes}

@app.websocket("/ws/polish")
async def websocket_polish(websocket: WebSocket):
    """WebSocket润色接口 - 实时处理"""
    await manager.connect(websocket)
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "polish":
                # 润色请求
                context_lines = data.get("context_lines", [])
                target_line = data.get("target_line", "")
                line_number = data.get("line_number", -1)
                style_prompt = data.get("style_prompt", "")
                
                try:
                    # 发送处理中状态
                    await manager.send_message({
                        "type": "status",
                        "message": "正在润色...",
                        "line_number": line_number
                    }, websocket)
                    
                    # 为每个请求创建独立的AI客户端实例，避免并发问题
                    client = AIClient(config_manager=config_manager)
                    
                    # 执行润色
                    polished_text = client.polish_last_line(
                        context_lines=context_lines,
                        target_line=target_line,
                        style_prompt=style_prompt
                    )
                    
                    # 发送结果
                    await manager.send_message({
                        "type": "polish_result",
                        "success": True,
                        "original_text": target_line,
                        "polished_text": polished_text,
                        "line_number": line_number,
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    
                except AIError as e:
                    await manager.send_message({
                        "type": "polish_result",
                        "success": False,
                        "error": str(e),
                        "line_number": line_number,
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
            
            elif action == "predict":
                # 剧情预测请求
                full_text = data.get("full_text", "")
                style_prompt = data.get("style_prompt", "")
                
                # 验证输入内容不为空
                if not full_text or not full_text.strip():
                    await manager.send_message({
                        "type": "predict_result",
                        "success": False,
                        "error": "文本内容为空，无需预测",
                        "predictions": [],
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    continue
                
                try:
                    await manager.send_message({
                        "type": "status",
                        "message": "正在预测剧情..."
                    }, websocket)
                    
                    # 为每个请求创建独立的AI客户端实例，避免并发问题
                    client = AIClient(config_manager=config_manager)
                    
                    # 调用AI预测，传递风格提示词
                    predicted_text = client.predict_plot_continuation(
                        full_text,
                        style_prompt=style_prompt
                    )
                    # 解析预测的两行内容
                    lines = [line.strip() for line in predicted_text.strip().split('\n') if line.strip()]
                    # 确保只取前两行
                    predictions = lines[:2] if len(lines) >= 2 else lines
                    
                    if len(predictions) < 2:
                        logger.warning(f"预测结果不足2行，实际返回{len(predictions)}行")
                    
                    await manager.send_message({
                        "type": "predict_result",
                        "success": True,
                        "predictions": predictions,
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    
                except AIError as e:
                    await manager.send_message({
                        "type": "predict_result",
                        "success": False,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
            
            elif action == "ping":
                # 心跳
                await manager.send_message({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket连接断开")
    
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
