from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional, List

import requests
from app.config_manager import ConfigManager, APIConfig


class AIError(RuntimeError):
    """表示与 AI API 交互时发生的错误。"""


def truncate_context(text: str, max_chars: int = 1000) -> str:
    """截取上下文文本，最多保留 max_chars 个字符，保持句子完整性
    
    Args:
        text: 完整文本
        max_chars: 最大字符数（默认1000字）
        
    Returns:
        截取后的文本，如果原文不足 max_chars 则返回全部
    """
    if not text:
        return ""
    
    # 如果文本长度不超过限制，直接返回全部
    if len(text) <= max_chars:
        return text
    
    # 从后往前截取 max_chars 个字符
    truncated = text[-max_chars:]
    
    # 定义句子结束标记（中文和英文）
    sentence_endings = ['。', '！', '？', '…', '.', '!', '?', '\n']
    
    # 找到第一个完整句子的开始位置（从前往后找第一个句子结束标记）
    first_sentence_end = -1
    for i, char in enumerate(truncated):
        if char in sentence_endings:
            first_sentence_end = i
            break
    
    # 如果找到句子结束标记，从下一个字符开始（保持句子完整）
    if first_sentence_end >= 0:
        # 跳过句子结束标记和后续的空白字符
        start_pos = first_sentence_end + 1
        while start_pos < len(truncated) and truncated[start_pos] in [' ', '\n', '\t', '\r']:
            start_pos += 1
        
        if start_pos < len(truncated):
            return truncated[start_pos:]
    
    # 如果没有找到句子结束标记，返回原截取内容
    return truncated


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
            self._model = model or os.getenv("AI_MODEL", "deepseek-ai/DeepSeek-V3.2-Exp")
            self._base_url = base_url or os.getenv("AI_BASE_URL", self._DEFAULT_BASE_URL)
        
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds
        
        # 极简配置：只用Session，自动处理连接复用
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
        import sys
        print(f"[DEBUG API] polish_last_line 开始，target_line={target_line[:30]}, context行数={len(context_lines)}", flush=True)
        sys.stdout.flush()
        
        context_text = "\n".join(context_lines) if context_lines else "(无)"
        
        # 构建系统提示词 - 使用更清晰的结构
        system_content = "你是一位资深中文小说编辑。"
        
        # 如果有风格要求，将其作为人设的一部分
        if style_prompt:
            system_content += f"\n\n【你的润色风格】\n{style_prompt}"
        
        # 添加核心任务指令
        system_content += (
            "\n\n【核心任务】\n"
            "根据提供的上下文，对最后一行文本进行润色。\n"
            "\n"
            "【输出要求】\n"
            "1. 只输出润色后的那一行文本，不要输出上下文\n"
            "2. 不要添加任何解释、说明或标注\n"
            "3. 直接输出润色后的文本内容即可\n"
            "4. 保持原意和核心内容不变\n"
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
                    "content": f"上下文：\n{context_text}\n\n待润色文本：\n{target_line}\n\n请输出润色后的文本：",
                },
            ],
            "temperature": self._temperature,
            "stream": False,
        }

        print(f"[DEBUG API] 准备发送请求到 {self._base_url}, model={self._model}", flush=True)
        sys.stdout.flush()
        
        try:
            response = self._session.post(
                self._base_url,
                headers=self._build_headers(),
                json=payload,
                timeout=self._timeout_seconds,
            )
            
            print(f"[DEBUG API] 收到响应，状态码: {response.status_code}", flush=True)
            sys.stdout.flush()
            
        except requests.RequestException as exc:
            print(f"[DEBUG API] 请求异常: {exc}", flush=True)
            sys.stdout.flush()
            raise AIError("网络异常，无法连接至 AI 服务。") from exc

        if response.status_code >= 500:
            print(f"[DEBUG API] 服务器错误: {response.status_code}", flush=True)
            sys.stdout.flush()
            raise AIError("AI 服务暂时不可用，请稍后重试。")

        if response.status_code == 401:
            print(f"[DEBUG API] 认证失败", flush=True)
            sys.stdout.flush()
            raise AIError("AI API 认证失败，请检查密钥是否正确。")

        if not response.ok:
            print(f"[DEBUG API] 响应错误: {response.status_code} {response.text[:100]}", flush=True)
            sys.stdout.flush()
            raise AIError(f"润色失败：{response.status_code} {response.text}")

        try:
            data: Dict[str, Any] = response.json()
            print(f"[DEBUG API] 解析JSON成功", flush=True)
            sys.stdout.flush()
        except ValueError as exc:
            print(f"[DEBUG API] JSON解析失败", flush=True)
            sys.stdout.flush()
            raise AIError("无法解析 AI 响应，请稍后再试。") from exc

        choices = data.get("choices")
        if not choices:
            print(f"[DEBUG API] 没有choices", flush=True)
            sys.stdout.flush()
            raise AIError("AI 未返回内容，请稍后再试。")

        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            print(f"[DEBUG API] content为空", flush=True)
            sys.stdout.flush()
            raise AIError("AI 响应内容为空。")

        print(f"[DEBUG API] polish_last_line 完成，返回内容长度: {len(content)}", flush=True)
        print(f"[DEBUG API] content原始内容: {repr(content)}", flush=True)
        sys.stdout.flush()
        
        result = content.strip()
        print(f"[DEBUG API] strip后内容: {repr(result)}", flush=True)
        print(f"[DEBUG API] 准备返回，长度: {len(result)}", flush=True)
        sys.stdout.flush()
        
        return result

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
        
        # 截取上下文：最多1000字，保持句子完整
        context_text = truncate_context(full_text, max_chars=1000)
        
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
                    "content": f"现有剧情：\n{context_text}\n\n请预测接下来的两行剧情（只输出两行文本，每行一句完整的话）："
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
    
    def batch_polish_document(self, content: str, requirement: str = "") -> str:
        """批量润色整个文档
        
        Args:
            content: 要润色的完整文档内容
            requirement: 用户的润色需求（例如：提升专业性、口语化等）
        
        Returns:
            润色后的文档内容
        """
        # 构建系统提示词
        system_content = "你是一位资深中文文档编辑和润色专家。"
        
        # 如果有用户需求，加入需求说明
        if requirement:
            system_content += f"\n\n【润色需求】\n{requirement}"
        
        # 添加核心任务指令
        system_content += (
            "\n\n【任务】"
            "\n请对用户提供的文档内容进行全面润色和优化："
            "\n1. 保持原文的核心意思和结构不变"
            "\n2. 优化语句表达，提升流畅度和可读性"
            "\n3. 修正语法错误和不当用词"
            "\n4. 根据用户需求调整文本风格"
            "\n5. 保持段落格式和换行结构"
            "\n\n【输出要求】"
            "\n- 直接输出润色后的完整文档内容"
            "\n- 不要添加任何解释、评论或额外说明"
            "\n- 保持原文的段落结构和换行"
            "\n- 只输出润色后的文本"
        )
        
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": system_content
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            "temperature": self._temperature,
            "stream": False
        }
        
        try:
            # 批量润色使用更长超时
            response = self._session.post(
                self._base_url,
                headers=self._build_headers(),
                json=payload,
                timeout=self._timeout_seconds * 2,
            )
            
        except requests.Timeout as exc:
            raise AIError("请求超时，文档较长可能需要更长时间，请稍后重试。") from exc
        except requests.ConnectionError as exc:
            raise AIError("无法连接至 AI 服务，请检查网络。") from exc
        except requests.RequestException as exc:
            raise AIError(f"网络异常：{str(exc)}") from exc
        
        if response.status_code >= 500:
            raise AIError("AI 服务暂时不可用，请稍后重试。")
        
        if response.status_code == 401:
            raise AIError("AI API 认证失败，请检查密钥是否正确。")
        
        if not response.ok:
            raise AIError(f"批量润色失败：{response.status_code} {response.text}")
        
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
        
        print(f"[DEBUG API] batch_polish_document 完成，返回内容长度: {len(content)}", flush=True)
        
        return content.strip()
    
    def check_connection_alive(self) -> bool:
        """轻量级连接检查"""
        return hasattr(self, '_session') and self._session is not None
    
    def test_connection(self) -> Dict[str, Any]:
        """测试API连接"""
        try:
            test_payload = {
                "model": self._model,
                "messages": [{"role": "user", "content": "test"}],
                "temperature": 0.1,
                "max_tokens": 5,
                "stream": False,
            }
            
            response = self._session.post(
                self._base_url,
                headers=self._build_headers(),
                json=test_payload,
                timeout=10,
            )
            
            return {
                "success": response.status_code == 200,
                "message": "连接正常" if response.status_code == 200 else f"错误: {response.status_code}",
                "status_code": response.status_code
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "status_code": None
            }
    
    def warmup_connection(self) -> Dict[str, Any]:
        """轻量级预热 - Session自动管理连接，无需额外操作"""
        return {
            "success": True,
            "message": "就绪",
            "warmup_time": 0.0
        }
    
    def is_warmed_up(self) -> bool:
        """检查连接是否已预热"""
        return True  # Session始终就绪
    
    def close(self):
        """关闭连接池，释放资源"""
        try:
            if hasattr(self, '_session') and self._session:
                self._session.close()
        except Exception:
            pass  # 忽略关闭时的错误
    
    def __del__(self):
        """析构函数 - 确保资源被释放"""
        self.close()
