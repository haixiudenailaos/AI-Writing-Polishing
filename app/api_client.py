from __future__ import annotations

import os
from typing import Any, Dict, Optional, List

import requests
from config_manager import ConfigManager, APIConfig


class AIError(RuntimeError):
    """表示与 AI API 交互时发生的错误。"""


class AIClient:
    """AI 润色 API 客户端。"""

    _DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1/chat/completions"

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        timeout_seconds: int = 45,
    ) -> None:
        self._config_manager = config_manager
        
        # 优先使用配置管理器中的配置
        if self._config_manager:
            api_config = self._config_manager.get_api_config()
            self._api_key = api_key or api_config.api_key
            self._model = model or api_config.model
            self._base_url = base_url or api_config.base_url
        else:
            # 回退到环境变量或默认值
            self._api_key = api_key or os.getenv("AI_API_KEY")
            self._model = model or os.getenv("AI_MODEL", "deepseek-ai/deepseek-llm-67b-instruct")
            self._base_url = base_url or os.getenv("AI_BASE_URL", self._DEFAULT_BASE_URL)
        
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds
        self._session = requests.Session()

    def _build_headers(self) -> Dict[str, str]:
        if not self._api_key:
            raise AIError("未配置 AI API 密钥。请设置环境变量 AI_API_KEY。")
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def polish_text(self, text: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一位资深中文小说编辑，请在保留原意的前提下润色用户文本。"
                        "优化用词、句式与节奏，输出润色后的完整文本，不要包含多余解释。"
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": self._temperature,
            "stream": False,
        }

        try:
            response = self._session.post(
                self._base_url,
                headers=self._build_headers(),
                json=payload,
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AIError("网络异常，无法连接至 AI 服务。") from exc

        if response.status_code >= 500:
            raise AIError("AI 服务暂时不可用，请稍后重试。")

        if response.status_code == 401:
            raise AIError("AI API 认证失败，请检查密钥是否正确。")

        if not response.ok:
            raise AIError(f"润色失败：{response.status_code} {response.text}")

        try:
            data: Dict[str, Any] = response.json()
        except ValueError as exc:
            raise AIError("无法解析 AI 响应，请稍后再试。") from exc

        choices = data.get("choices")
        if not choices:
            raise AIError("AI 未返回内容，请稍后再试。")

        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise AIError("AI 响应内容为空。")

        return content.strip()

    # 新增：仅润色最后一行，发送最后五行上下文
    def polish_last_line(self, context_lines: List[str], target_line: str, style_prompt: str = "") -> str:
        context_text = "\n".join(context_lines) if context_lines else "(无)"
        
        # 构建系统提示词
        system_content = (
            "你是一位资深中文小说编辑。请根据提供的上下文，仅润色最后一行文本。"
            "保持原意与风格，只输出润色后的最后一行，不要包含上下文或任何解释。"
        )
        
        # 如果有风格要求，添加到系统提示词中
        if style_prompt:
            system_content += f"\n\n风格要求：{style_prompt}"
        
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": system_content,
                },
                {
                    "role": "user",
                    "content": f"上下文：\n{context_text}\n\n需要润色的行：\n{target_line}",
                },
            ],
            "temperature": self._temperature,
            "stream": False,
        }

        try:
            response = self._session.post(
                self._base_url,
                headers=self._build_headers(),
                json=payload,
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AIError("网络异常，无法连接至 AI 服务。") from exc

        if response.status_code >= 500:
            raise AIError("AI 服务暂时不可用，请稍后重试。")

        if response.status_code == 401:
            raise AIError("AI API 认证失败，请检查密钥是否正确。")

        if not response.ok:
            raise AIError(f"润色失败：{response.status_code} {response.text}")

        try:
            data: Dict[str, Any] = response.json()
        except ValueError as exc:
            raise AIError("无法解析 AI 响应，请稍后再试。") from exc

        choices = data.get("choices")
        if not choices:
            raise AIError("AI 未返回内容，请稍后再试。")

        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise AIError("AI 响应内容为空。")

        return content.strip()

    def optimize_prompt(self, prompt_text: str) -> str:
        if not prompt_text or not prompt_text.strip():
            raise AIError("提示词为空，无法优化。")
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一位资深中文提示词工程师。" \
                        "请将用户提供的润色风格提示词进行结构化与增强：" \
                        "明确目标、风格要点、约束、输出要求；避免冗余与含糊；" \
                        "保持中文输出，只返回优化后的提示词本身，不要解释。"
                    ),
                },
                {"role": "user", "content": prompt_text},
            ],
            "temperature": self._temperature,
            "stream": False,
        }
        try:
            response = self._session.post(
                self._base_url,
                headers=self._build_headers(),
                json=payload,
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AIError("网络异常，无法连接至 AI 服务。") from exc
        if response.status_code >= 500:
            raise AIError("AI 服务暂时不可用，请稍后重试。")
        if response.status_code == 401:
            raise AIError("AI API 认证失败，请检查密钥是否正确。")
        if not response.ok:
            raise AIError(f"提示词优化失败：{response.status_code} {response.text}")
        try:
            data: Dict[str, Any] = response.json()
        except ValueError as exc:
            raise AIError("无法解析 AI 响应，请稍后再试。") from exc
        choices = data.get("choices")
        if not choices:
            raise AIError("AI 未返回内容，请稍后再试。")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise AIError("AI 响应内容为空。")
        return content.strip()

    def update_config(self, config_manager: ConfigManager) -> None:
        """更新配置管理器"""
        self._config_manager = config_manager
        if self._config_manager:
            api_config = self._config_manager.get_api_config()
            self._api_key = api_config.api_key
            self._model = api_config.model
            self._base_url = api_config.base_url
    
    def predict_plot_continuation(self, full_text: str, style_prompt: str = "") -> str:
        """预测剧情发展，生成接下来两行内容
        
        Args:
            full_text: 当前编辑器中的全部文本内容
            style_prompt: 风格提示词（可选），将作为人设发送给AI
            
        Returns:
            预测的接下来两行剧情内容
        """
        if not full_text or not full_text.strip():
            raise AIError("文本内容为空，无法预测剧情。")
        
        # 构建基础系统提示词
        system_content = (
            "你是一位资深中文小说作家，擅长剧情预测与续写。"
        )
        
        # 如果有风格提示词，将其作为人设的一部分
        if style_prompt:
            system_content += f"\n\n【你的人设与风格要求】\n{style_prompt}"
        
        # 添加任务要求
        system_content += (
            "\n\n【任务要求】\n"
            "请根据用户提供的现有剧情，严格按照上述人设与风格要求，预测并生成接下来最合理的两行内容。\n"
            "注意事项：\n"
            "1）严格遵守人设与风格要求，保持风格统一；\n"
            "2）剧情连贯自然，符合逻辑；\n"
            "3）只输出两行文本，不要任何解释或标注；\n"
            "4）每行文本应独立成句，行与行之间用换行符分隔；\n"
            "5）确保输出的是从当前文本结尾处往下的两行内容。"
        )
        
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": system_content,
                },
                {
                    "role": "user",
                    "content": f"现有剧情：\n{full_text}\n\n请预测接下来的两行剧情（只输出两行文本，每行一句完整的话）："
                },
            ],
            "temperature": 0.7,  # 使用较高温度以增加创造性
            "stream": False,
        }
        
        try:
            response = self._session.post(
                self._base_url,
                headers=self._build_headers(),
                json=payload,
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AIError("网络异常，无法连接至 AI 服务。") from exc
        
        if response.status_code >= 500:
            raise AIError("AI 服务暂时不可用，请稍后重试。")
        
        if response.status_code == 401:
            raise AIError("AI API 认证失败，请检查密钥是否正确。")
        
        if not response.ok:
            raise AIError(f"剧情预测失败：{response.status_code} {response.text}")
        
        try:
            data: Dict[str, Any] = response.json()
        except ValueError as exc:
            raise AIError("无法解析 AI 响应，请稍后再试。") from exc
        
        choices = data.get("choices")
        if not choices:
            raise AIError("AI 未返回内容，请稍后再试。")
        
        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise AIError("AI 响应内容为空。")
        
        return content.strip()
    
    def test_connection(self) -> Dict[str, Any]:
        """测试API连接"""
        try:
            # 发送一个简单的测试请求
            test_payload = {
                "model": self._model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个测试助手。"
                    },
                    {
                        "role": "user", 
                        "content": "测试"
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 10,
                "stream": False,
            }
            
            response = self._session.post(
                self._base_url,
                headers=self._build_headers(),
                json=test_payload,
                timeout=10,  # 较短的超时时间用于测试
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "API连接测试成功",
                    "status_code": response.status_code
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "message": "API密钥认证失败",
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "message": f"API返回错误: {response.status_code}",
                    "status_code": response.status_code
                }
                
        except requests.RequestException as e:
            return {
                "success": False,
                "message": f"网络连接失败: {str(e)}",
                "status_code": None
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"测试失败: {str(e)}",
                "status_code": None
            }
