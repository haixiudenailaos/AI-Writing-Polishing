from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional, List, TYPE_CHECKING

import requests
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
        
        # 极简配置：只用Session，自动处理连接复用
        self._session = requests.Session()

    def _build_headers(self) -> Dict[str, str]:
        if not self._api_key:
            raise AIError("未配置 AI API 密钥。请设置环境变量 AI_API_KEY。")
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
    
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
        
        # 阿里云千问价格参考（实际价格可能变化，请查阅官网）
        # qwen-plus: 输入 0.4元/百万tokens, 输出 1.2元/百万tokens
        # qwen-max: 输入 4元/百万tokens, 输出 12元/百万tokens
        # qwen-turbo: 输入 0.3元/百万tokens, 输出 0.6元/百万tokens
        
        # 根据模型估算成本（假设使用qwen-plus）
        input_cost = (input_tokens / 1_000_000) * 0.4
        output_cost = (output_tokens / 1_000_000) * 1.2
        total_cost = input_cost + output_cost
        
        print("=" * 60)
        print(f"📊 【Token消耗统计 - {operation}】")
        print(f"   输入tokens: {input_tokens:,}")
        print(f"   输出tokens: {output_tokens:,}")
        print(f"   总计tokens: {total_tokens:,}")
        print(f"   预估成本: ¥{total_cost:.4f} (按qwen-plus价格)")
        print(f"   输入成本: ¥{input_cost:.6f}")
        print(f"   输出成本: ¥{output_cost:.6f}")
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
        
        # 构建基础系统提示词
        system_content = (
            "你是一位富有创造力的资深中文小说作家，擅长为创作者提供新颖的剧情思路。\n"
            "你的核心价值：不是机械续写，而是激发创作者的灵感，提供「意料之外、情理之中」的精彩发展。"
        )
        
        # 如果有风格提示词，将其作为人设的一部分
        if style_prompt:
            system_content += f"\n\n{style_prompt}"
        
        # 添加任务要求
        system_content += (
            "\n\n【执行要求】\n"
            "1）深度分析：理解当前情境的潜在冲突、人物动机、隐藏线索\n"
            "2）创意优先：优先考虑有戏剧张力、情感冲击的发展方向\n"
            "3）合理创新：确保创意建立在已有信息的逻辑基础上\n"
            "4）风格契合：用符合作品风格的语言表达创意\n"
            "5）精炼输出：只输出两行纯文本（每行一个完整句子），不要任何解释、标注或元数据\n"
            "6）无缝衔接：确保输出可以直接接续当前文本末尾"
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
        
        # 打印Token使用统计
        if "usage" in data:
            self._print_token_usage(data["usage"], operation="_call_api通用调用")
        
        choices = data.get("choices")
        if not choices:
            raise AIError("AI 未返回内容，请稍后再试。")
        
        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise AIError("AI 响应内容为空。")
        
        return content.strip()
    
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
        kb: 'KnowledgeBase',
        rerank_client: Optional['RerankClient'] = None,
        style_prompt: str = "",
        min_relevance_threshold: float = 0.25
    ) -> str:
        """基于知识库的增强剧情预测（带查询扩展）
        
        Args:
            current_context: 当前编辑位置的上下文（上方两行）
            kb_manager: 知识库管理器
            kb: 知识库对象
            rerank_client: 重排序客户端（可选）
            style_prompt: 风格提示词
            min_relevance_threshold: 最小相关性阈值，低于此值的结果会被过滤（默认0.25）
            
        Returns:
            预测的剧情内容
        """
        # 1. 如果知识库为空，回退到普通预测
        if not kb or not kb.documents:
            print("[INFO] 知识库为空，使用普通预测")
            return self.predict_plot_continuation(current_context, style_prompt)
        
        # 2. 使用查询扩展增强检索效果
        try:
            print(f"[INFO] 开始知识库检索，知识库文档数: {len(kb.documents)}")
            print(f"[INFO] 重排客户端状态: {'已提供' if rerank_client else '未提供'}")
            if rerank_client:
                print(f"[INFO] 重排客户端对象: {rerank_client}")
            
            # 查询扩展：提取关键信息增强查询
            enhanced_query = self._enhance_query_with_context(current_context)
            if enhanced_query != current_context:
                print(f"[INFO] 查询扩展已启用，原始查询长度: {len(current_context)}, 增强后: {len(enhanced_query)}")
            
            # 搜索相似文档（使用增强查询和更大的候选集）
            similar_docs = kb_manager.search_similar_documents(
                query_text=enhanced_query,  # 使用增强后的查询
                kb=kb,
                top_k=25,  # 向量检索先取25个候选（已优化：增加召回率）
                rerank_client=rerank_client,
                final_top_n=5  # 重排后取最多5个最相关的
            )
            
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
                
                # 限制最多返回5个最相关的文档（避免上下文过长）
                filtered_docs = filtered_docs[:5]
            
            print(f"[INFO] 知识库检索：找到 {len(similar_docs)} 个相似文档，过滤后保留 {len(filtered_docs)} 个")
            
            # 4. 如果确实没有结果（知识库为空），回退到普通预测
            if not filtered_docs:
                print("[INFO] 没有找到相关内容，使用普通预测")
                return self.predict_plot_continuation(current_context, style_prompt)
            
            # 5. 提取每个文档的上下文
            kb_contexts = []
            for doc_item in filtered_docs:
                doc = doc_item['document']
                
                # 获取文档及其上下文（使用更大的上下文窗口以提供更完整的信息）
                doc_with_context = kb_manager.get_document_with_context(
                    doc=doc,
                    kb=kb,
                    context_lines_before=4,
                    context_lines_after=4
                )
                
                kb_contexts.append({
                    'content': doc.content,
                    'full_context': doc_with_context['full_context'],
                    'file_path': doc_with_context['file_path'],
                    'score': doc_item.get('relevance_score', doc_item.get('similarity_score', 0))
                })
            
            # 6. 构建增强的预测prompt（创意导向优化版）
            # 构建系统提示词
            system_content = (
                "你是一位富有创造力的资深中文小说作家，擅长为创作者提供新颖的剧情思路。\n"
                "你将基于当前上下文和知识库参考，生成「意料之外、情理之中」的精彩后续剧情。\n\n"
                "【如何创造性使用知识库参考】\n"
                "✦ 参考内容的价值：\n"
                "  • 揭示作品的人物性格深层逻辑、情节转折规律、潜在伏笔\n"
                "  • 展现作者偏好的叙事技巧、戏剧冲突模式、情感表达方式\n"
                "  • 提供可借鉴的创意元素、意外转折、人物关系张力\n"
                "✦ 创意运用策略：\n"
                "  1. 从参考中识别「意外但合理」的情节模式，迁移到当前情境\n"
                "  2. 发现参考中隐藏的伏笔线索，在后续剧情中巧妙呼应\n"
                "  3. 学习参考中制造悬念、反转、冲突的技巧\n"
                "  4. 把握参考中人物的核心动机和行为逻辑\n"
                "  5. 相关度越高的参考，越能提供精准的创意灵感\n"
                "✦ 注意事项：\n"
                "  × 不要机械复制参考内容，要创造性转化\n"
                "  × 如果参考与当前冲突，以当前上下文为准\n"
                "  × 避免平庸续写，要有创新思维"
            )
            
            # 添加风格要求
            if style_prompt:
                system_content += f"\n\n{style_prompt}"
            
            # 添加任务要求
            system_content += (
                "\n\n【执行要求】\n"
                "1. 深度分析：综合当前剧情和知识库参考，挖掘潜在冲突点和转折可能\n"
                "2. 创意优先：从多个可能方向中，选择最有戏剧张力和情感冲击的一个\n"
                "3. 合理创新：确保创意既新颖又符合作品已建立的逻辑和人物设定\n"
                "4. 风格契合：用与参考内容一致的语言风格表达创意\n"
                "5. 精炼输出：只输出两行纯文本（每行一个完整句子），不要任何解释、标注或元数据\n"
                "6. 无缝衔接：确保输出可以直接接续当前文本末尾"
            )
            
            # 构建用户提示词（结构化呈现）
            user_content = "【当前上下文】\n" + current_context + "\n\n"
            
            # 添加知识库参考内容（带相关度标注）
            user_content += "【知识库相关参考】\n"
            user_content += f"（共找到 {len(kb_contexts)} 个相关片段，按相关度排序）\n\n"
            
            for i, ctx in enumerate(kb_contexts, 1):
                score = ctx['score']
                # 根据分数添加相关性标签
                if score >= 0.7:
                    relevance_label = "高度相关"
                elif score >= 0.5:
                    relevance_label = "较为相关"
                elif score >= 0.3:
                    relevance_label = "中等相关"
                else:
                    relevance_label = "弱相关"
                
                user_content += f"═══ 参考片段 {i} ═══\n"
                user_content += f"相关度: {score:.3f} ({relevance_label})\n"
                user_content += f"内容:\n{ctx['full_context']}\n\n"
            
            user_content += "═══════════════════\n\n"
            user_content += "现在，请深度分析【当前上下文】的潜在走向，从【知识库相关参考】中汲取创意灵感，\n"
            user_content += "生成令人眼前一亮、又在情理之中的后续两行剧情。\n\n"
            user_content += "直接输出两行文本，不要任何其他内容："
            
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
