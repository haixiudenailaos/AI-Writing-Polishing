from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional, List, TYPE_CHECKING
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.config_manager import ConfigManager, APIConfig

# 避免循环导入
if TYPE_CHECKING:
    from app.knowledge_base import KnowledgeBase, KnowledgeBaseManager, RerankClient


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
        
        # 优化：配置连接池和重试策略（弱网优化）
        self._session = requests.Session()
        
        # 配置重试策略：针对网络错误和临时性故障自动重试
        retry_strategy = Retry(
            total=3,  # 最多重试3次
            backoff_factor=0.5,  # 重试间隔：0.5s, 1s, 2s
            status_forcelist=[408, 429, 500, 502, 503, 504],  # 这些状态码会重试
            allowed_methods=["POST", "GET"],  # 允许重试的方法
            raise_on_status=False  # 不在重试后抛出异常
        )
        
        # 配置HTTP适配器：优化连接池
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # 连接池大小
            pool_maxsize=20,  # 最大连接数
            pool_block=False  # 非阻塞模式
        )
        
        # 为http和https都配置适配器
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        
        # 启用keep-alive和压缩
        self._session.headers.update({
            'Connection': 'keep-alive',
            'Accept-Encoding': 'gzip, deflate'
        })

    def _build_headers(self) -> Dict[str, str]:
        if not self._api_key:
            raise AIError("未配置 AI API 密钥。请设置环境变量 AI_API_KEY。")
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
    
    def _make_request_with_retry(self, payload: Dict[str, Any], timeout: Optional[int] = None) -> Dict[str, Any]:
        """发送请求并处理重试逻辑（针对弱网环境优化）
        
        Args:
            payload: 请求负载
            timeout: 超时时间（秒），None则使用默认值
            
        Returns:
            API响应的JSON数据
            
        Raises:
            AIError: 请求失败时抛出
        """
        timeout = timeout or self._timeout_seconds
        last_error = None
        
        # 手动实现额外的重试逻辑（在Session重试之外）
        # 这样可以更好地处理超时和连接错误
        for attempt in range(2):  # 额外重试1次
            try:
                response = self._session.post(
                    self._base_url,
                    headers=self._build_headers(),
                    json=payload,
                    timeout=timeout,
                )
                
                # 处理HTTP错误
                if response.status_code >= 500:
                    last_error = AIError("AI 服务暂时不可用，请稍后重试。")
                    if attempt < 1:  # 如果还有重试机会
                        time.sleep(1)  # 等待1秒后重试
                        continue
                    raise last_error
                
                if response.status_code == 401:
                    raise AIError("AI API 认证失败，请检查密钥是否正确。")
                
                if not response.ok:
                    raise AIError(f"请求失败：{response.status_code} {response.text}")
                
                # 解析响应
                try:
                    data: Dict[str, Any] = response.json()
                    return data
                except ValueError as exc:
                    raise AIError("无法解析 AI 响应，请稍后再试。") from exc
                    
            except requests.Timeout as exc:
                last_error = AIError(f"请求超时（{timeout}秒），请检查网络连接或稍后重试。")
                if attempt < 1:  # 如果还有重试机会
                    time.sleep(1)
                    continue
                raise last_error from exc
                
            except requests.ConnectionError as exc:
                last_error = AIError("网络连接失败，请检查网络设置。")
                if attempt < 1:
                    time.sleep(1)
                    continue
                raise last_error from exc
                
            except requests.RequestException as exc:
                last_error = AIError("网络异常，无法连接至 AI 服务。")
                if attempt < 1:
                    time.sleep(1)
                    continue
                raise last_error from exc
        
        # 如果所有重试都失败
        if last_error:
            raise last_error
        raise AIError("请求失败")
    
    def _print_token_usage(self, usage_data: Dict[str, Any], operation: str = "API调用"):
        """打印Token使用统计
        
        Args:
            usage_data: API返回的usage数据
            operation: 操作描述
        """
        if not usage_data:
            return
        
        input_tokens = usage_data.get('input_tokens', usage_data.get('prompt_tokens', 0))
        output_tokens = usage_data.get('output_tokens', usage_data.get('completion_tokens', 0))
        total_tokens = usage_data.get('total_tokens', input_tokens + output_tokens)
        
        # DeepSeek-V3.2-Exp 价格参考
        # DeepSeek-V3.2-Exp: 输入 2元/百万tokens, 输出 3元/百万tokens
        # 官网：https://platform.deepseek.com/api-docs/pricing/
        
        # 根据模型估算成本（使用DeepSeek-V3.2-Exp价格）
        input_cost = (input_tokens / 1_000_000) * 2.0
        output_cost = (output_tokens / 1_000_000) * 3.0
        total_cost = input_cost + output_cost
        
        print("=" * 60)
        print(f"📊 【Token消耗统计 - {operation}】")
        print(f"   输入tokens: {input_tokens:,}")
        print(f"   输出tokens: {output_tokens:,}")
        print(f"   总计tokens: {total_tokens:,}")
        print(f"   预估成本: ¥{total_cost:.4f} (按DeepSeek-V3.2-Exp价格)")
        print(f"   输入成本: ¥{input_cost:.6f} (¥2/百万)")
        print(f"   输出成本: ¥{output_cost:.6f} (¥3/百万)")
        print("=" * 60)

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

        # 使用优化的请求方法（包含重试和错误处理）
        data = self._make_request_with_retry(payload)

        choices = data.get("choices")
        if not choices:
            raise AIError("AI 未返回内容，请稍后再试。")

        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise AIError("AI 响应内容为空。")
        
        # 打印Token使用统计
        if "usage" in data:
            self._print_token_usage(data["usage"], operation="润色")

        return content.strip()

    # 新增：仅润色最后一行，发送最后五行上下文
    def polish_last_line(self, context_lines: List[str], target_line: str, style_prompt: str = "") -> str:
        import sys
        print(f"[DEBUG API] polish_last_line 开始，target_line={target_line[:30]}, context行数={len(context_lines)}", flush=True)
        sys.stdout.flush()
        
        context_text = "\n".join(context_lines) if context_lines else "(无)"
        
        # 构建系统提示词 - 润色专注于优化表达，不做预测性创作
        system_content = "你是一位资深中文小说编辑。"
        
        # 如果有风格要求，将其作为人设的一部分
        if style_prompt:
            system_content += f"\n\n【你的润色风格】\n{style_prompt}"
        
        # 添加核心任务指令 - 纯粹的润色，不做创造性改写
        system_content += (
            "\n\n【核心任务】\n"
            "对最后一行文本进行润色优化，保持原意和情节，提升表达质量。\n"
            "\n"
            "【润色要求】\n"
            "1. 保持原文的核心意思、情节和人物动作不变\n"
            "2. 优化用词、句式、节奏，提升文字的流畅度和可读性\n"
            "3. 修正语法问题和不当表达，让文字更通顺自然\n"
            "4. 符合上述风格要求，保持文本的整体风格统一\n"
            "5. 仅做润色优化，不要添加新情节或改变原意\n"
            "\n"
            "【输出要求】\n"
            "1. 只输出润色后的那一行文本，不要输出上下文\n"
            "2. 不要添加任何解释、说明或标注\n"
            "3. 直接输出润色后的文本内容即可\n"
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
        
        # 使用优化的请求方法（包含重试和错误处理）
        data = self._make_request_with_retry(payload)
        
        print(f"[DEBUG API] 解析JSON成功", flush=True)
        sys.stdout.flush()

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
        
        # 打印Token使用统计
        if "usage" in data:
            self._print_token_usage(data["usage"], operation="润色最后一行")
        
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
        
        # 使用优化的请求方法（包含重试和错误处理）
        data = self._make_request_with_retry(payload)
        
        # 打印Token使用统计
        if "usage" in data:
            self._print_token_usage(data["usage"], operation="优化提示词")
        
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
        
        # 构建预测系统提示词 - 明确标注为"剧情预测"任务
        system_content = (
            "你是一位富有创造力的资深中文小说作家。\n"
            "\n"
            "【你的任务】剧情预测与创作\n"
            "为创作者提供新颖的剧情思路，生成接下来的故事内容。\n"
            "这不是润色任务，而是创造性的续写和剧情发展。\n"
            "\n"
            "【核心原则】\n"
            "🔴 最重要：必须紧密基于用户当前书写的剧情内容来预测\n"
            "🎭 创意发展：在当前剧情基础上，提供有张力的后续发展\n"
            "🔗 无缝衔接：预测内容必须直接接续当前文本末尾，不能跳跃"
        )
        
        # 如果有风格提示词，将其作为写作人设的一部分
        if style_prompt:
            system_content += f"\n\n【你的写作风格】\n{style_prompt}"
        
        # 添加预测任务要求
        system_content += (
            "\n\n【剧情预测要求（权重排序）】\n"
            "1. 🔴 紧扣当前剧情：必须基于【当前剧情】的具体情境、人物状态、场景细节\n"
            "2. 🎭 创意发展：从当前情境出发，选择最有戏剧张力和情感冲击的发展方向\n"
            "3. ✅ 逻辑合理：确保预测既新颖又符合已建立的逻辑和情境\n"
            "4. 🎨 风格契合：用符合上述写作风格的语言表达\n"
            "5. 🔗 无缝衔接：输出必须直接接续当前剧情的末尾，不能跳跃或脱节\n"
            "\n"
            "【输出要求】\n"
            "- 只输出两行纯文本（每行一个完整句子）\n"
            "- 不要任何解释、标注或元数据\n"
            "- 直接输出预测的后续剧情"
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
                    "content": f"【当前剧情】\n{context_text}\n\n请基于上述剧情，生成令人眼前一亮的后续两行内容（直接输出两行文本）："
                },
            ],
            "temperature": 0.85,  # 使用较高温度以增加创造性和意外性
            "stream": False,
        }
        
        # 使用优化的请求方法（包含重试和错误处理）
        data = self._make_request_with_retry(payload)
        
        # 打印Token使用统计
        if "usage" in data:
            self._print_token_usage(data["usage"], operation="剧情预测")
        
        choices = data.get("choices")
        if not choices:
            raise AIError("AI 未返回内容，请稍后再试。")
        
        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise AIError("AI 响应内容为空。")
        
        return content.strip()
    
    def polish_last_line_with_kb(
        self,
        context_lines: List[str],
        target_line: str,
        kb_manager: 'KnowledgeBaseManager',
        character_kb: Optional['KnowledgeBase'] = None,
        outline_kbs: Optional[List['KnowledgeBase']] = None,
        character_kbs: Optional[List['KnowledgeBase']] = None,
        rerank_client: Optional['RerankClient'] = None,
        style_prompt: str = "",
        min_relevance_threshold: float = 0.25
    ) -> str:
        """基于大纲和人设知识库的增强润色
        
        注意：润色同时使用大纲知识库和人设知识库，最多5条上下文
        
        Args:
            context_lines: 上下文行
            target_line: 待润色的目标行
            kb_manager: 知识库管理器
            character_kb: 人设知识库（可选，向后兼容）
            outline_kbs: 大纲知识库列表（可选）
            character_kbs: 人设知识库列表（可选）
            rerank_client: 重排序客户端（可选）
            style_prompt: 风格提示词
            min_relevance_threshold: 最小相关性阈值
            
        Returns:
            润色后的文本
        """
        # 向后兼容：如果传入了 character_kb，将其添加到 character_kbs 列表
        if character_kb and character_kb.documents:
            if character_kbs is None:
                character_kbs = [character_kb]
            elif character_kb not in character_kbs:
                character_kbs = list(character_kbs) + [character_kb]
        
        # 1. 如果既没有大纲知识库也没有人设知识库，回退到普通润色
        has_outline = outline_kbs and any(kb.documents for kb in outline_kbs)
        has_character = character_kbs and any(kb.documents for kb in character_kbs)
        
        if not has_outline and not has_character:
            print("[INFO] 大纲和人设知识库均为空，使用普通润色")
            return self.polish_last_line(context_lines, target_line, style_prompt)
        
        # 2. 使用上下文和目标行构建查询
        query_context = "\n".join(context_lines[-2:]) if context_lines else ""  # 最后两行上下文
        query_text = f"{query_context}\n{target_line}"
        
        try:
            # 3. 从大纲和人设知识库检索相关内容
            all_similar_docs = []
            
            # 从大纲知识库检索
            if outline_kbs:
                for outline_kb in outline_kbs:
                    if outline_kb.documents:
                        print(f"[INFO] 开始大纲知识库检索: {outline_kb.name}")
                        outline_docs = kb_manager.search_similar_documents(
                            query_text=query_text,
                            kb=outline_kb,
                            top_k=20,
                            rerank_client=rerank_client,
                            final_top_n=5
                        )
                        if outline_docs:
                            # 标记来源
                            for doc_item in outline_docs:
                                doc_item['kb_source'] = 'outline'
                                doc_item['kb_name'] = outline_kb.name
                                doc_item['kb_obj'] = outline_kb
                            all_similar_docs.extend(outline_docs)
                            print(f"[INFO] 大纲知识库 {outline_kb.name} 检索到 {len(outline_docs)} 个文档")
            
            # 从人设知识库检索
            if character_kbs:
                for character_kb_item in character_kbs:
                    if character_kb_item.documents:
                        print(f"[INFO] 开始人设知识库检索: {character_kb_item.name}")
                        character_docs = kb_manager.search_similar_documents(
                            query_text=query_text,
                            kb=character_kb_item,
                            top_k=20,
                            rerank_client=rerank_client,
                            final_top_n=5
                        )
                        if character_docs:
                            # 标记来源
                            for doc_item in character_docs:
                                doc_item['kb_source'] = 'character'
                                doc_item['kb_name'] = character_kb_item.name
                                doc_item['kb_obj'] = character_kb_item
                            all_similar_docs.extend(character_docs)
                            print(f"[INFO] 人设知识库 {character_kb_item.name} 检索到 {len(character_docs)} 个文档")
            
            # 4. 合并并按相关性排序所有检索结果
            if all_similar_docs:
                all_similar_docs.sort(
                    key=lambda x: x.get('relevance_score', x.get('similarity_score', 0)),
                    reverse=True
                )
                print(f"[INFO] 合并后共检索到 {len(all_similar_docs)} 个文档")
            
            # 5. 过滤低质量结果
            filtered_docs = []
            if all_similar_docs:
                max_score = all_similar_docs[0].get('relevance_score', all_similar_docs[0].get('similarity_score', 0))
                if max_score >= 0.7:
                    dynamic_threshold = max(min_relevance_threshold, max_score * 0.4)
                elif max_score >= 0.4:
                    dynamic_threshold = max(min_relevance_threshold, max_score * 0.3)
                else:
                    dynamic_threshold = min_relevance_threshold
                
                for doc_item in all_similar_docs:
                    score = doc_item.get('relevance_score', doc_item.get('similarity_score', 0))
                    if score >= dynamic_threshold:
                        filtered_docs.append(doc_item)
                
                if not filtered_docs and all_similar_docs:
                    filtered_docs = all_similar_docs[:min(2, len(all_similar_docs))]
            
            print(f"[INFO] 知识库检索：找到 {len(all_similar_docs)} 个文档，过滤后保留 {len(filtered_docs)} 个")
            
            # 6. 如果没有相关结果，回退到普通润色
            if not filtered_docs:
                print("[INFO] 没有找到相关的大纲/人设内容，使用普通润色")
                return self.polish_last_line(context_lines, target_line, style_prompt)
            
            # 限制最多5条上下文
            filtered_docs = filtered_docs[:5]
            
            # 7. 提取知识库上下文（区分大纲和人设）
            outline_contexts = []
            character_contexts = []
            
            for doc_item in filtered_docs:
                doc = doc_item['document']
                kb_source = doc_item.get('kb_source', 'character')
                kb_obj = doc_item.get('kb_obj')
                
                if kb_obj:
                    doc_with_context = kb_manager.get_document_with_context(
                        doc=doc,
                        kb=kb_obj,
                        context_lines_before=2,
                        context_lines_after=2
                    )
                    
                    context_item = {
                        'content': doc.content,
                        'full_context': doc_with_context['full_context'],
                        'score': doc_item.get('relevance_score', doc_item.get('similarity_score', 0)),
                        'kb_name': doc_item.get('kb_name', '')
                    }
                    
                    if kb_source == 'outline':
                        outline_contexts.append(context_item)
                    else:
                        character_contexts.append(context_item)
            
            # 8. 构建增强的润色prompt（结构化标注）
            system_content = "你是一位资深中文小说编辑。"
            
            # 添加风格要求
            if style_prompt:
                system_content += f"\n\n【你的润色风格】\n{style_prompt}"
            
            # 添加任务说明（根据有哪些知识库动态调整）
            task_description = "\n\n"
            
            if outline_contexts and character_contexts:
                # 同时有大纲和人设
                task_description += (
                    "【大纲和人设资料的作用】\n"
                    "• 大纲资料：揭示故事的整体框架、剧情走向、关键事件、世界观设定等宏观信息\n"
                    "• 人设资料：揭示人物的性格、背景、行为模式、语言习惯等核心特征\n"
                    "\n"
                    "请基于这些资料对文本进行润色，确保：\n"
                    "1. 剧情表达符合大纲设定，与整体故事框架保持一致\n"
                    "2. 人物性格和行为的表达符合人设定位\n"
                    "3. 对话和心理活动的措辞符合角色个性和语言习惯\n"
                    "4. 细节描写的用词契合世界观和人物背景\n"
                    "5. 在符合设定的前提下，优化表达质量\n"
                )
            elif outline_contexts:
                # 只有大纲
                task_description += (
                    "【大纲资料的作用】\n"
                    "大纲资料揭示了故事的整体框架、剧情走向、关键事件、世界观设定等宏观信息。\n"
                    "\n"
                    "请基于大纲资料对文本进行润色，确保：\n"
                    "1. 剧情表达符合大纲设定，与整体故事框架保持一致\n"
                    "2. 细节描写的用词契合世界观设定\n"
                    "3. 在符合设定的前提下，优化表达质量\n"
                )
            elif character_contexts:
                # 只有人设
                task_description += (
                    "【人设资料的作用】\n"
                    "人设资料揭示了人物的性格、背景、行为模式、语言习惯等核心特征。\n"
                    "\n"
                    "请基于人设资料对文本进行润色，确保：\n"
                    "1. 人物性格和行为的表达符合人设定位\n"
                    "2. 对话和心理活动的措辞符合角色个性和语言习惯\n"
                    "3. 细节描写的用词契合人物背景\n"
                    "4. 在符合人设的前提下，优化表达质量\n"
                )
            
            task_description += (
                "\n"
                "【润色要求】\n"
                "1. 保持原文的核心意思、情节和人物动作不变\n"
                "2. 优化用词、句式、节奏，提升文字的流畅度和可读性\n"
                "3. 修正语法问题和不当表达，让文字更通顺自然\n"
                "4. 符合风格要求和知识库设定，保持文本的整体风格统一\n"
                "5. 仅做润色优化，不要添加新情节或改变原意\n"
                "\n"
                "【输出要求】\n"
                "1. 只输出润色后的那一行文本，不要输出上下文\n"
                "2. 不要添加任何解释、说明或标注\n"
                "3. 直接输出润色后的文本内容即可\n"
            )
            
            system_content += task_description
            
            # 构建用户prompt
            context_text = "\n".join(context_lines) if context_lines else "(无)"
            
            user_content = "【上下文】\n" + context_text + "\n\n"
            
            # 添加大纲参考（如果有）
            if outline_contexts:
                user_content += "【大纲参考资料】\n"
                user_content += f"（从大纲库找到 {len(outline_contexts)} 个相关设定，用于确保剧情发展符合整体框架）\n\n"
                
                for i, ctx in enumerate(outline_contexts, 1):
                    score = ctx['score']
                    if score >= 0.7:
                        relevance_label = "高度相关"
                    elif score >= 0.5:
                        relevance_label = "较为相关"
                    else:
                        relevance_label = "中等相关"
                    
                    kb_name = ctx.get('kb_name', '')
                    user_content += f"═══ 大纲 {i} ({kb_name}) ═══\n"
                    user_content += f"相关度: {score:.3f} ({relevance_label})\n"
                    user_content += f"作用: 帮助理解故事框架、剧情走向和世界观设定\n"
                    user_content += f"内容:\n{ctx['full_context']}\n\n"
                
                user_content += "═══════════════════\n\n"
            
            # 添加人设参考（如果有）
            if character_contexts:
                user_content += "【人设参考资料】\n"
                user_content += f"（从人设库找到 {len(character_contexts)} 个相关人设，用于确保人物行为符合角色设定）\n\n"
                
                for i, ctx in enumerate(character_contexts, 1):
                    score = ctx['score']
                    if score >= 0.7:
                        relevance_label = "高度相关"
                    elif score >= 0.5:
                        relevance_label = "较为相关"
                    else:
                        relevance_label = "中等相关"
                    
                    kb_name = ctx.get('kb_name', '')
                    user_content += f"═══ 人设 {i} ({kb_name}) ═══\n"
                    user_content += f"相关度: {score:.3f} ({relevance_label})\n"
                    user_content += f"作用: 帮助理解角色的性格特征、行为逻辑和语言风格\n"
                    user_content += f"内容:\n{ctx['full_context']}\n\n"
                
                user_content += "═══════════════════\n\n"
            
            user_content += f"【待润色文本】\n{target_line}\n\n"
            
            # 根据有哪些资料调整提示
            if outline_contexts and character_contexts:
                user_content += "请基于上述大纲和人设参考及上下文，输出润色后的文本："
            elif outline_contexts:
                user_content += "请基于上述大纲参考和上下文，输出润色后的文本："
            elif character_contexts:
                user_content += "请基于上述人设参考和上下文，输出润色后的文本："
            
            # 8. 调用AI进行润色
            payload = {
                "model": self._model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_content,
                    },
                    {
                        "role": "user",
                        "content": user_content,
                    },
                ],
                "temperature": self._temperature,
                "stream": False,
            }
            
            data = self._make_request_with_retry(payload)
            
            # 打印Token使用统计
            if "usage" in data:
                self._print_token_usage(data["usage"], operation="人设知识库增强润色")
            
            choices = data.get("choices")
            if not choices:
                raise AIError("AI 未返回内容，请稍后再试。")
            
            message = choices[0].get("message", {})
            content = message.get("content")
            if not content:
                raise AIError("AI 响应内容为空。")
            
            print(f"[INFO] 人设知识库增强润色完成")
            
            return content.strip()
            
        except Exception as e:
            # 如果人设知识库增强润色失败，回退到普通润色
            print(f"[ERROR] 人设知识库增强润色失败: {str(e)}，回退到普通润色")
            import traceback
            traceback.print_exc()
            return self.polish_last_line(context_lines, target_line, style_prompt)
    
    def _enhance_query_with_context(self, query_text: str) -> str:
        """查询扩展：提取关键信息增强查询
        
        Args:
            query_text: 原始查询文本
            
        Returns:
            增强后的查询文本
        """
        # 简单的关键词提取策略
        # 提取可能的人名、场景、情节关键词
        enhanced_query = query_text
        
        # 提取引号内的对话和专有名词（通常是关键信息）
        import re
        quoted_text = re.findall(r'[「『"\'](.*?)[」』"\']', query_text)
        if quoted_text:
            # 将对话内容权重提升
            enhanced_query = query_text + "\n关键对话: " + " ".join(quoted_text)
        
        # 提取可能的人名（中文姓名模式：2-4个汉字）
        # 匹配常见姓氏开头的2-4字人名
        names = re.findall(r'[赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜][一-龥]{1,3}(?=[，。！？\s"」』]|$)', query_text)
        if names:
            enhanced_query += "\n相关人物: " + " ".join(set(names))
        
        return enhanced_query
    
    def predict_plot_continuation_with_kb(
        self,
        current_context: str,
        kb_manager: 'KnowledgeBaseManager',
        history_kb: Optional['KnowledgeBase'] = None,
        outline_kb: Optional['KnowledgeBase'] = None,
        character_kb: Optional['KnowledgeBase'] = None,
        rerank_client: Optional['RerankClient'] = None,
        style_prompt: str = "",
        min_relevance_threshold: float = 0.25
    ) -> str:
        """基于知识库的增强剧情预测（支持历史、大纲、人设三库检索）
        
        Args:
            current_context: 当前编辑位置的上下文（上方两行）
            kb_manager: 知识库管理器
            history_kb: 历史文本知识库（可选）
            outline_kb: 大纲知识库（可选）
            character_kb: 人设知识库（可选）
            rerank_client: 重排序客户端（可选）
            style_prompt: 风格提示词
            min_relevance_threshold: 最小相关性阈值，低于此值的结果会被过滤（默认0.25）
            
        Returns:
            预测的剧情内容
        """
        # 1. 如果三个知识库都为空，回退到普通预测
        if not any([
            history_kb and history_kb.documents,
            outline_kb and outline_kb.documents,
            character_kb and character_kb.documents
        ]):
            print("[INFO] 所有知识库都为空，使用普通预测")
            return self.predict_plot_continuation(current_context, style_prompt)
        
        # 2. 使用查询扩展增强检索效果
        try:
            # 查询扩展：提取关键信息增强查询
            enhanced_query = self._enhance_query_with_context(current_context)
            if enhanced_query != current_context:
                print(f"[INFO] 查询扩展已启用，原始查询长度: {len(current_context)}, 增强后: {len(enhanced_query)}")
            
            # 3. 分别从三个知识库检索（每个最多5条）
            history_docs = []
            outline_docs = []
            character_docs = []
            
            # 从历史文本知识库检索
            if history_kb and history_kb.documents:
                print(f"[INFO] 开始历史文本知识库检索，文档数: {len(history_kb.documents)}")
                history_docs = kb_manager.search_similar_documents(
                    query_text=enhanced_query,
                    kb=history_kb,
                    top_k=25,
                    rerank_client=rerank_client,
                    final_top_n=5
                )
                print(f"[INFO] 历史文本检索：找到 {len(history_docs)} 个相关文档")
            
            # 从大纲知识库检索
            if outline_kb and outline_kb.documents:
                print(f"[INFO] 开始大纲知识库检索，文档数: {len(outline_kb.documents)}")
                outline_docs = kb_manager.search_similar_documents(
                    query_text=enhanced_query,
                    kb=outline_kb,
                    top_k=20,
                    rerank_client=rerank_client,
                    final_top_n=5
                )
                print(f"[INFO] 大纲检索：找到 {len(outline_docs)} 个相关文档")
            
            # 从人设知识库检索
            if character_kb and character_kb.documents:
                print(f"[INFO] 开始人设知识库检索，文档数: {len(character_kb.documents)}")
                character_docs = kb_manager.search_similar_documents(
                    query_text=enhanced_query,
                    kb=character_kb,
                    top_k=20,
                    rerank_client=rerank_client,
                    final_top_n=5
                )
                print(f"[INFO] 人设检索：找到 {len(character_docs)} 个相关文档")
            
            # 合并检索结果
            similar_docs = history_docs + outline_docs + character_docs
            
            # 3. 根据动态阈值过滤低质量结果（优化版）
            filtered_docs = []
            
            if similar_docs:
                # 动态阈值策略：基于最高分数调整阈值
                max_score = similar_docs[0].get('relevance_score', similar_docs[0].get('similarity_score', 0))
                
                # 如果最高分数很高(>=0.7)，使用相对阈值（最高分的40%）
                # 如果最高分数中等(0.4-0.7)，使用较低的相对阈值（最高分的30%）
                # 如果最高分数较低(<0.4)，使用绝对最低阈值
                if max_score >= 0.7:
                    dynamic_threshold = max(min_relevance_threshold, max_score * 0.4)
                elif max_score >= 0.4:
                    dynamic_threshold = max(min_relevance_threshold, max_score * 0.3)
                else:
                    dynamic_threshold = min_relevance_threshold
                
                print(f"[INFO] 动态阈值计算：最高分={max_score:.3f}，动态阈值={dynamic_threshold:.3f}，基础阈值={min_relevance_threshold:.3f}")
                
                for doc_item in similar_docs:
                    # 如果有重排分数，使用重排分数；否则使用相似度分数
                    score = doc_item.get('relevance_score', doc_item.get('similarity_score', 0))
                    
                    if score >= dynamic_threshold:
                        filtered_docs.append(doc_item)
                
                # 如果过滤后没有结果，至少保留相关性最高的1-2个文档
                if not filtered_docs:
                    filtered_docs = similar_docs[:min(2, len(similar_docs))]
                    print(f"[INFO] 知识库检索：所有文档相关性低于阈值，保留最高的 {len(filtered_docs)} 个")
                
                # 不需要限制总数，因为每个知识库已经限制为最多5条
            
            print(f"[INFO] 知识库检索：找到 {len(similar_docs)} 个相似文档，过滤后保留 {len(filtered_docs)} 个")
            
            # 4. 如果确实没有结果（知识库为空），回退到普通预测
            if not filtered_docs:
                print("[INFO] 没有找到相关内容，使用普通预测")
                return self.predict_plot_continuation(current_context, style_prompt)
            
            # 5. 提取每个文档的上下文，并标记来源（三种知识库分别处理）
            history_contexts = []
            outline_contexts = []
            character_contexts = []
            
            for doc_item in filtered_docs:
                doc = doc_item['document']
                
                # 判断文档来源（通过doc_id在哪个知识库中）
                is_from_history = False
                is_from_outline = False
                is_from_character = False
                
                if history_kb and history_kb.documents:
                    if any(d.id == doc.id for d in history_kb.documents):
                        is_from_history = True
                
                if outline_kb and outline_kb.documents:
                    if any(d.id == doc.id for d in outline_kb.documents):
                        is_from_outline = True
                
                if character_kb and character_kb.documents:
                    if any(d.id == doc.id for d in character_kb.documents):
                        is_from_character = True
                
                # 获取文档及其上下文
                if is_from_history:
                    doc_with_context = kb_manager.get_document_with_context(
                        doc=doc,
                        kb=history_kb,
                        context_lines_before=4,
                        context_lines_after=4
                    )
                    history_contexts.append({
                        'content': doc.content,
                        'full_context': doc_with_context['full_context'],
                        'file_path': doc_with_context['file_path'],
                        'score': doc_item.get('relevance_score', doc_item.get('similarity_score', 0))
                    })
                elif is_from_outline:
                    doc_with_context = kb_manager.get_document_with_context(
                        doc=doc,
                        kb=outline_kb,
                        context_lines_before=2,
                        context_lines_after=2
                    )
                    outline_contexts.append({
                        'content': doc.content,
                        'full_context': doc_with_context['full_context'],
                        'file_path': doc_with_context['file_path'],
                        'score': doc_item.get('relevance_score', doc_item.get('similarity_score', 0))
                    })
                elif is_from_character:
                    doc_with_context = kb_manager.get_document_with_context(
                        doc=doc,
                        kb=character_kb,
                        context_lines_before=2,
                        context_lines_after=2
                    )
                    character_contexts.append({
                        'content': doc.content,
                        'full_context': doc_with_context['full_context'],
                        'file_path': doc_with_context['file_path'],
                        'score': doc_item.get('relevance_score', doc_item.get('similarity_score', 0))
                    })
            
            # 6. 构建知识库增强预测prompt - 明确标注为"剧情预测"任务
            # 构建系统提示词
            system_content = (
                "你是一位富有创造力的资深中文小说作家。\n"
                "\n"
                "【你的任务】基于知识库的剧情预测与创作\n"
                "结合当前上下文和知识库参考资料，生成接下来的故事内容。\n"
                "这不是润色任务，而是创造性的续写和剧情发展。\n"
                "\n"
                "【核心原则：权重优先级】\n"
                "🔴 最高优先级：【当前上下文】- 这是用户正在书写的实际内容，是剧情发展的核心依据\n"
                "🟡 辅助参考：知识库资料 - 提供背景设定和创意灵感，但必须服从当前上下文\n"
                "\n"
                "⚠️ 关键要求：\n"
                "• 当前上下文是最重要的，必须紧密基于它来预测后续剧情\n"
                "• 知识库资料仅作为辅助，用于理解背景、人设、世界观\n"
                "• 如果知识库参考与当前上下文冲突，必须以当前上下文为准\n"
                "• 预测必须无缝接续当前上下文的末尾，不能脱离当前情境\n"
                "\n"
                "【如何使用知识库参考（辅助性质）】\n"
                "✦ 参考内容的价值：\n"
                "  • 揭示人物性格深层逻辑、情节转折规律、潜在伏笔\n"
                "  • 展现作者偏好的叙事技巧、戏剧冲突模式、情感表达方式\n"
                "  • 提供可借鉴的创意元素、意外转折、人物关系张力\n"
                "✦ 创意运用策略：\n"
                "  1. 在不偏离当前上下文的前提下，借鉴参考中的情节模式\n"
                "  2. 发现参考中的伏笔线索，在符合当前情境时巧妙呼应\n"
                "  3. 学习参考中制造悬念、反转、冲突的技巧\n"
                "  4. 从参考中理解人物的核心动机和行为逻辑\n"
                "✦ 注意事项：\n"
                "  × 不要机械复制参考内容，要创造性转化\n"
                "  × 参考只是灵感来源，当前上下文才是创作基础\n"
                "  × 避免平庸续写，但也不能脱离当前剧情"
            )
            
            # 添加风格要求
            if style_prompt:
                system_content += f"\n\n【你的写作风格】\n{style_prompt}"
            
            # 添加预测任务要求
            system_content += (
                "\n\n【剧情预测要求（权重排序）】\n"
                "1. 🔴 紧扣当前上下文：必须基于【当前上下文】的具体情境、人物状态、场景细节来预测\n"
                "2. 🟡 参考知识库：在理解当前情境的基础上，借鉴知识库中的人设、大纲、历史剧情\n"
                "3. 🎭 创意发展：从当前情境出发，选择最有戏剧张力和情感冲击的发展方向\n"
                "4. ✅ 逻辑合理：确保预测既新颖又符合当前已建立的逻辑和情境\n"
                "5. 🎨 风格契合：用符合上述写作风格的语言表达\n"
                "6. 🔗 无缝衔接：输出必须直接接续当前上下文的末尾，不能跳跃或脱节\n"
                "\n"
                "【输出要求】\n"
                "- 只输出两行纯文本（每行一个完整句子）\n"
                "- 不要任何解释、标注或元数据\n"
                "- 直接输出预测的后续剧情"
            )
            
            # 构建用户提示词（结构化呈现三种知识库，并标注各自作用）
            user_content = "【当前上下文】\n" + current_context + "\n\n"
            
            # 添加历史文本参考（如果有）
            if history_contexts:
                user_content += "【历史剧情参考】\n"
                user_content += f"（从历史文本库找到 {len(history_contexts)} 个相关片段，最多5条）\n"
                user_content += "作用: 提供相似情节的写作风格、剧情发展模式和创意灵感\n\n"
                
                for i, ctx in enumerate(history_contexts, 1):
                    score = ctx['score']
                    if score >= 0.7:
                        relevance_label = "高度相关"
                    elif score >= 0.5:
                        relevance_label = "较为相关"
                    elif score >= 0.3:
                        relevance_label = "中等相关"
                    else:
                        relevance_label = "弱相关"
                    
                    user_content += f"═══ 历史片段 {i} ═══\n"
                    user_content += f"相关度: {score:.3f} ({relevance_label})\n"
                    user_content += f"内容:\n{ctx['full_context']}\n\n"
                
                user_content += "═══════════════════\n\n"
            
            # 添加大纲参考（如果有）
            if outline_contexts:
                user_content += "【大纲参考资料】\n"
                user_content += f"（从大纲库找到 {len(outline_contexts)} 个相关设定，最多5条）\n"
                user_content += "作用: 确保剧情发展符合整体规划和世界观设定\n\n"
                
                for i, ctx in enumerate(outline_contexts, 1):
                    score = ctx['score']
                    if score >= 0.7:
                        relevance_label = "高度相关"
                    elif score >= 0.5:
                        relevance_label = "较为相关"
                    else:
                        relevance_label = "中等相关"
                    
                    user_content += f"═══ 大纲 {i} ═══\n"
                    user_content += f"相关度: {score:.3f} ({relevance_label})\n"
                    user_content += f"内容:\n{ctx['full_context']}\n\n"
                
                user_content += "═══════════════════\n\n"
            
            # 添加人设参考（如果有）
            if character_contexts:
                user_content += "【人设参考资料】\n"
                user_content += f"（从人设库找到 {len(character_contexts)} 个相关人设，最多5条）\n"
                user_content += "作用: 确保角色行为、对话和心理活动符合人物设定\n\n"
                
                for i, ctx in enumerate(character_contexts, 1):
                    score = ctx['score']
                    if score >= 0.7:
                        relevance_label = "高度相关"
                    elif score >= 0.5:
                        relevance_label = "较为相关"
                    else:
                        relevance_label = "中等相关"
                    
                    user_content += f"═══ 人设 {i} ═══\n"
                    user_content += f"相关度: {score:.3f} ({relevance_label})\n"
                    user_content += f"内容:\n{ctx['full_context']}\n\n"
                
                user_content += "═══════════════════\n\n"
            
            # 添加任务说明 - 强调当前上下文的优先级
            user_content += "【预测指令】\n"
            user_content += "🔴 核心依据：请紧密基于【当前上下文】的具体情境来预测后续剧情\n"
            
            refs = []
            if history_contexts:
                refs.append("【历史剧情参考】")
            if outline_contexts:
                refs.append("【大纲参考资料】")
            if character_contexts:
                refs.append("【人设参考资料】")
            
            if refs:
                user_content += f"🟡 辅助参考：{' '.join(refs)}可作为背景理解和创意灵感\n"
            
            user_content += "\n重要提醒：\n"
            user_content += "• 【当前上下文】是最重要的，预测必须从它出发\n"
            user_content += "• 知识库参考仅作为辅助，不能偏离当前情境\n"
            user_content += "• 如果参考与当前冲突，以当前上下文为准\n\n"
            user_content += "现在，请基于【当前上下文】生成令人眼前一亮、又在情理之中的后续两行剧情：\n"
            user_content += "（直接输出两行文本，不要任何其他内容）"
            
            # 7. 调用AI生成预测
            payload = {
                "model": self._model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_content,
                    },
                    {
                        "role": "user",
                        "content": user_content
                    },
                ],
                "temperature": 0.8,  # 使用较高温度以增加创造性和意外性
                "stream": False,
            }
            
            # 使用优化的请求方法（包含重试和错误处理）
            data = self._make_request_with_retry(payload)
            
            # 打印Token使用统计（知识库增强剧情预测）
            if "usage" in data:
                self._print_token_usage(data["usage"], operation="知识库增强剧情预测")
            
            choices = data.get("choices")
            if not choices:
                raise AIError("AI 未返回内容，请稍后再试。")
            
            message = choices[0].get("message", {})
            content = message.get("content")
            if not content:
                raise AIError("AI 响应内容为空。")
            
            return content.strip()
            
        except Exception as e:
            # 如果知识库检索或预测失败，回退到普通预测
            print(f"[ERROR] 知识库增强预测失败: {str(e)}，回退到普通预测")
            import traceback
            traceback.print_exc()
            return self.predict_plot_continuation(current_context, style_prompt)
    
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
        
        # 添加核心任务指令 - 纯粹的润色，不做创造性改写
        system_content += (
            "\n\n【核心任务】"
            "\n对整个文档进行润色优化，保持原意和情节，提升表达质量。"
            "\n\n【润色要求】"
            "\n1. 保持原文的核心意思、情节结构和段落组织不变"
            "\n2. 优化用词、句式、节奏，提升文字的流畅度和可读性"
            "\n3. 修正语法错误和不当表达，让文字更通顺自然"
            "\n4. 根据用户需求调整文本风格，保持整体风格统一"
            "\n5. 保持原文的段落格式和换行结构"
            "\n6. 仅做润色优化，不要添加新情节或改变原意"
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
        
        # 批量润色使用更长超时（2倍超时）
        data = self._make_request_with_retry(payload, timeout=self._timeout_seconds * 2)
        
        # 打印Token使用统计
        if "usage" in data:
            self._print_token_usage(data["usage"], operation="批量润色")
        
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
