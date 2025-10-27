"""
文本处理器
负责智能文本分析和处理逻辑
"""

from typing import List, Tuple, Optional, Dict, Any
import re
from dataclasses import dataclass


@dataclass
class TextContext:
    """文本上下文信息"""
    context_lines: List[str]
    target_line: str
    line_number: int
    total_lines: int
    is_paragraph_start: bool
    is_paragraph_end: bool
    is_dialogue: bool
    estimated_context_relevance: float


class TextProcessor:
    """智能文本处理器"""
    
    def __init__(self):
        # 对话标识符
        self.dialogue_patterns = [
            r'^["""].*["""]$',  # 引号包围
            r'^[「」『』].*[「」『』]$',  # 中文引号
            r'^.*[说道讲问答回][:：]',  # 说话动词
            r'^.*[说道讲问答回][，,]',  # 说话动词+逗号
        ]
        
        # 段落结束标识符
        self.paragraph_end_patterns = [
            r'[。！？…]+$',  # 句号、感叹号、问号、省略号结尾
            r'[.!?…]+$',  # 英文标点结尾
        ]
        
        # 段落开始标识符
        self.paragraph_start_patterns = [
            r'^　　',  # 中文段落缩进
            r'^\s{2,}',  # 多个空格缩进
            r'^\t',  # Tab缩进
        ]
    
    def analyze_text_context(self, text: str, cursor_position: Optional[int] = None) -> TextContext:
        """
        分析文本上下文，确定最佳的处理范围
        
        Args:
            text: 完整文本
            cursor_position: 光标位置，如果为None则处理最后一行
            
        Returns:
            TextContext: 文本上下文信息
        """
        lines = text.splitlines()
        if not lines:
            return TextContext([], "", 0, 0, True, True, False, 0.0)
        
        # 确定目标行
        if cursor_position is not None:
            target_line_idx = self._get_line_from_position(text, cursor_position)
        else:
            target_line_idx = len(lines) - 1
        
        target_line = lines[target_line_idx] if target_line_idx < len(lines) else ""
        
        # 获取上下文行
        context_lines = self._get_optimal_context(lines, target_line_idx)
        
        # 分析文本特征
        is_dialogue = self._is_dialogue_line(target_line)
        is_paragraph_start = self._is_paragraph_start(target_line)
        is_paragraph_end = self._is_paragraph_end(target_line)
        
        # 计算上下文相关性
        relevance = self._calculate_context_relevance(context_lines, target_line)
        
        return TextContext(
            context_lines=context_lines,
            target_line=target_line,
            line_number=target_line_idx + 1,
            total_lines=len(lines),
            is_paragraph_start=is_paragraph_start,
            is_paragraph_end=is_paragraph_end,
            is_dialogue=is_dialogue,
            estimated_context_relevance=relevance
        )
    
    def _get_line_from_position(self, text: str, position: int) -> int:
        """根据字符位置获取行号"""
        lines_before = text[:position].count('\n')
        return lines_before
    
    def _get_optimal_context(self, lines: List[str], target_idx: int, max_context: int = 4) -> List[str]:
        """
        获取最优上下文行
        
        Args:
            lines: 所有行
            target_idx: 目标行索引
            max_context: 最大上下文行数
            
        Returns:
            List[str]: 上下文行列表
        """
        if target_idx == 0:
            return []
        
        # 基础上下文范围
        start_idx = max(0, target_idx - max_context)
        context_candidates = lines[start_idx:target_idx]
        
        # 智能调整上下文范围
        context_lines = self._filter_relevant_context(context_candidates, lines[target_idx])
        
        return context_lines
    
    def _filter_relevant_context(self, candidates: List[str], target_line: str) -> List[str]:
        """
        过滤相关的上下文行
        
        Args:
            candidates: 候选上下文行
            target_line: 目标行
            
        Returns:
            List[str]: 过滤后的上下文行
        """
        if not candidates:
            return []
        
        # 如果目标行是对话，优先保留对话相关的上下文
        if self._is_dialogue_line(target_line):
            return self._filter_dialogue_context(candidates, target_line)
        
        # 如果目标行是段落开始，减少上下文
        if self._is_paragraph_start(target_line):
            return candidates[-2:] if len(candidates) >= 2 else candidates
        
        # 移除空行和无关内容
        filtered = []
        for line in candidates:
            if line.strip():  # 非空行
                filtered.append(line)
        
        # 保持最多4行上下文
        return filtered[-4:] if len(filtered) > 4 else filtered
    
    def _filter_dialogue_context(self, candidates: List[str], target_line: str) -> List[str]:
        """过滤对话相关的上下文"""
        # 对于对话，保留说话人和前一句对话
        relevant_lines = []
        
        for line in reversed(candidates):
            if not line.strip():
                continue
                
            # 如果是对话行或包含说话动词，保留
            if (self._is_dialogue_line(line) or 
                any(word in line for word in ['说', '道', '问', '答', '回', '讲'])):
                relevant_lines.append(line)
                
            # 最多保留3行相关上下文
            if len(relevant_lines) >= 3:
                break
        
        return list(reversed(relevant_lines))
    
    def _is_dialogue_line(self, line: str) -> bool:
        """判断是否为对话行"""
        line = line.strip()
        if not line:
            return False
            
        for pattern in self.dialogue_patterns:
            if re.search(pattern, line):
                return True
        return False
    
    def _is_paragraph_start(self, line: str) -> bool:
        """判断是否为段落开始"""
        for pattern in self.paragraph_start_patterns:
            if re.match(pattern, line):
                return True
        return False
    
    def _is_paragraph_end(self, line: str) -> bool:
        """判断是否为段落结束"""
        line = line.strip()
        if not line:
            return False
            
        for pattern in self.paragraph_end_patterns:
            if re.search(pattern, line):
                return True
        return False
    
    def _calculate_context_relevance(self, context_lines: List[str], target_line: str) -> float:
        """
        计算上下文相关性得分
        
        Args:
            context_lines: 上下文行
            target_line: 目标行
            
        Returns:
            float: 相关性得分 (0.0 - 1.0)
        """
        if not context_lines or not target_line.strip():
            return 0.0
        
        score = 0.0
        total_factors = 0
        
        # 因素1: 上下文行数适中性
        context_count = len(context_lines)
        if 2 <= context_count <= 4:
            score += 0.3
        elif context_count == 1:
            score += 0.2
        total_factors += 1
        
        # 因素2: 对话连贯性
        target_is_dialogue = self._is_dialogue_line(target_line)
        context_dialogue_count = sum(1 for line in context_lines if self._is_dialogue_line(line))
        
        if target_is_dialogue and context_dialogue_count > 0:
            score += 0.3
        elif not target_is_dialogue and context_dialogue_count == 0:
            score += 0.2
        total_factors += 1
        
        # 因素3: 段落连贯性
        if context_lines:
            last_context_ends_paragraph = self._is_paragraph_end(context_lines[-1])
            target_starts_paragraph = self._is_paragraph_start(target_line)
            
            if not (last_context_ends_paragraph and target_starts_paragraph):
                score += 0.2
        total_factors += 1
        
        # 因素4: 词汇相关性
        target_words = set(re.findall(r'[\u4e00-\u9fff]+', target_line))
        if target_words:
            context_text = ' '.join(context_lines)
            context_words = set(re.findall(r'[\u4e00-\u9fff]+', context_text))
            
            if context_words:
                overlap = len(target_words & context_words)
                relevance_ratio = overlap / len(target_words)
                score += min(0.2, relevance_ratio * 0.4)
        total_factors += 1
        
        return score / total_factors if total_factors > 0 else 0.0
    
    def prepare_polish_request(self, context: TextContext, style_prompt: str = "") -> Dict[str, Any]:
        """
        准备润色请求数据
        
        Args:
            context: 文本上下文
            style_prompt: 风格提示词
            
        Returns:
            Dict[str, Any]: 请求数据
        """
        # 构建基础提示词
        base_prompt = "请润色以下文本中的最后一行，保持原意的同时提升表达质量。"
        
        # 根据文本特征调整提示词
        if context.is_dialogue:
            base_prompt += "注意保持对话的自然性和人物语气特点。"
        
        if context.is_paragraph_start:
            base_prompt += "这是段落的开始，注意开头的吸引力。"
        
        if context.is_paragraph_end:
            base_prompt += "这是段落的结尾，注意结尾的完整性。"
        
        # 添加风格要求
        if style_prompt:
            base_prompt += f"\n\n风格要求：{style_prompt}"
        
        # 构建上下文说明
        context_info = ""
        if context.context_lines:
            context_info = f"\n\n上下文（前{len(context.context_lines)}行）：\n"
            for i, line in enumerate(context.context_lines, 1):
                context_info += f"{i}. {line}\n"
        
        context_info += f"\n需要润色的行：{context.target_line}"
        
        return {
            "prompt": base_prompt + context_info,
            "context_lines": context.context_lines,
            "target_line": context.target_line,
            "metadata": {
                "line_number": context.line_number,
                "total_lines": context.total_lines,
                "is_dialogue": context.is_dialogue,
                "is_paragraph_start": context.is_paragraph_start,
                "is_paragraph_end": context.is_paragraph_end,
                "context_relevance": context.estimated_context_relevance
            }
        }
    
    def validate_polish_result(self, original_line: str, polished_line: str) -> Dict[str, Any]:
        """
        验证润色结果的质量
        
        Args:
            original_line: 原始行
            polished_line: 润色后的行
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        result = {
            "valid": True,
            "score": 0.0,
            "issues": [],
            "suggestions": []
        }
        
        # 检查基本有效性
        if not polished_line or not polished_line.strip():
            result["valid"] = False
            result["issues"].append("润色结果为空")
            return result
        
        # 检查长度变化
        original_len = len(original_line.strip())
        polished_len = len(polished_line.strip())
        length_ratio = polished_len / original_len if original_len > 0 else 0
        
        if length_ratio > 3.0:
            result["issues"].append("润色后文本过长")
            result["score"] -= 0.2
        elif length_ratio < 0.3:
            result["issues"].append("润色后文本过短")
            result["score"] -= 0.1
        else:
            result["score"] += 0.2
        
        # 检查是否保持了原意
        original_words = set(re.findall(r'[\u4e00-\u9fff]+', original_line))
        polished_words = set(re.findall(r'[\u4e00-\u9fff]+', polished_line))
        
        if original_words:
            preserved_ratio = len(original_words & polished_words) / len(original_words)
            if preserved_ratio < 0.3:
                result["issues"].append("可能偏离原意过多")
                result["score"] -= 0.3
            elif preserved_ratio > 0.7:
                result["score"] += 0.2
        
        # 检查标点符号
        if re.search(r'[。！？…]+$', original_line) and not re.search(r'[。！？…]+$', polished_line):
            result["suggestions"].append("建议保持原有的结尾标点")
        
        # 检查对话格式
        if self._is_dialogue_line(original_line) and not self._is_dialogue_line(polished_line):
            result["issues"].append("对话格式可能丢失")
            result["score"] -= 0.2
        
        # 计算最终得分
        result["score"] = max(0.0, min(1.0, result["score"] + 0.5))
        
        return result
    
    def extract_sentences(self, text: str) -> List[Tuple[str, int, int]]:
        """
        提取文本中的句子
        
        Args:
            text: 输入文本
            
        Returns:
            List[Tuple[str, int, int]]: 句子列表，每个元素为(句子, 开始位置, 结束位置)
        """
        sentences = []
        
        # 句子分隔符
        sentence_patterns = [
            r'[。！？…]+',
            r'[.!?…]+',
            r'\n+',
        ]
        
        current_pos = 0
        for match in re.finditer('|'.join(sentence_patterns), text):
            sentence_end = match.end()
            sentence = text[current_pos:sentence_end].strip()
            
            if sentence:
                sentences.append((sentence, current_pos, sentence_end))
            
            current_pos = sentence_end
        
        # 处理最后一个句子（如果没有结尾标点）
        if current_pos < len(text):
            remaining = text[current_pos:].strip()
            if remaining:
                sentences.append((remaining, current_pos, len(text)))
        
        return sentences