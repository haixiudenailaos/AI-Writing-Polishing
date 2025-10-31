"""
提示词生成器
基于知识库文档内容自动生成定制化的润色风格提示词和预测提示词
"""

import random
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
import re


class PromptGenerator:
    """提示词生成器 - 从知识库内容中提取特征并生成提示词"""
    
    def __init__(self):
        """初始化提示词生成器"""
        pass
    
    def extract_features_from_documents(self, documents: List[Any], sample_size: int = 50) -> Dict[str, Any]:
        """从文档中提取特征
        
        Args:
            documents: 知识库文档列表
            sample_size: 采样文档数量（默认50个）
            
        Returns:
            特征字典，包含：
            - avg_sentence_length: 平均句子长度
            - punctuation_freq: 标点符号使用频率
            - vocabulary_richness: 词汇丰富度
            - common_phrases: 常见短语
            - writing_style: 写作风格特征
            - common_patterns: 常见句式模式
        """
        if not documents:
            return self._get_default_features()
        
        # 随机采样文档（避免处理全部文档，提高效率）
        sampled_docs = random.sample(documents, min(sample_size, len(documents)))
        
        # 提取所有文本内容
        texts = [doc.content for doc in sampled_docs]
        full_text = "\n".join(texts)
        
        features = {}
        
        # 1. 分析句子长度
        sentences = self._split_sentences(full_text)
        if sentences:
            sentence_lengths = [len(s) for s in sentences]
            features['avg_sentence_length'] = sum(sentence_lengths) / len(sentence_lengths)
            features['sentence_length_variance'] = self._calculate_variance(sentence_lengths)
        else:
            features['avg_sentence_length'] = 20
            features['sentence_length_variance'] = 0
        
        # 2. 分析标点符号使用
        features['punctuation_freq'] = self._analyze_punctuation(full_text)
        
        # 3. 分析词汇特征
        features['vocabulary_richness'] = self._analyze_vocabulary(full_text)
        
        # 4. 提取常见短语
        features['common_phrases'] = self._extract_common_phrases(texts, top_n=10)
        
        # 5. 分析写作风格
        features['writing_style'] = self._analyze_writing_style(full_text, features)
        
        # 6. 提取句式模式
        features['common_patterns'] = self._extract_sentence_patterns(sentences, top_n=5)
        
        return features
    
    def generate_polish_style_prompt(self, kb_name: str, features: Dict[str, Any]) -> str:
        """基于特征生成润色风格提示词
        
        Args:
            kb_name: 知识库名称
            features: 文档特征
            
        Returns:
            润色风格提示词
        """
        style = features.get('writing_style', {})
        avg_length = features.get('avg_sentence_length', 20)
        punct_freq = features.get('punctuation_freq', {})
        
        prompt_parts = [
            f"【{kb_name}风格】",
            ""
        ]
        
        # 1. 句子长度风格
        if avg_length < 15:
            prompt_parts.append("- 使用简短精炼的句子，每句控制在15字左右")
        elif avg_length > 30:
            prompt_parts.append("- 使用较长的句子结构，注重细节描写和层次感")
        else:
            prompt_parts.append("- 保持句子长度适中，既不过于简短也不过于冗长")
        
        # 2. 对话风格
        if style.get('has_dialogue', False):
            prompt_parts.append("- 包含对话时，注重对话的生动性和人物性格展现")
        
        # 3. 描写风格
        if style.get('descriptive_level') == 'high':
            prompt_parts.append("- 注重细腻的场景和心理描写，营造氛围感")
        elif style.get('descriptive_level') == 'low':
            prompt_parts.append("- 以情节推进为主，描写简洁明快")
        
        # 4. 情感基调
        emotion_tone = style.get('emotion_tone', 'neutral')
        if emotion_tone == 'positive':
            prompt_parts.append("- 保持积极向上的情感基调")
        elif emotion_tone == 'melancholic':
            prompt_parts.append("- 保持含蓄深沉的情感表达")
        
        # 5. 标点符号使用偏好
        if punct_freq.get('ellipsis', 0) > 0.02:
            prompt_parts.append("- 适当使用省略号表达未尽之意")
        if punct_freq.get('exclamation', 0) > 0.03:
            prompt_parts.append("- 使用感叹号强化情感表达")
        
        # 6. 词汇特点
        vocab_richness = features.get('vocabulary_richness', 0)
        if vocab_richness > 0.7:
            prompt_parts.append("- 使用丰富多样的词汇，避免重复")
        elif vocab_richness < 0.4:
            prompt_parts.append("- 使用简洁常见的词汇，确保通俗易懂")
        
        # 7. 添加通用润色要求
        prompt_parts.extend([
            "",
            "【通用要求】",
            "- 保持原文的核心意思和情节发展",
            "- 优化语句通顺度和可读性",
            "- 保持与原文风格的一致性"
        ])
        
        return "\n".join(prompt_parts)
    
    def generate_prediction_prompt(self, kb_name: str, features: Dict[str, Any]) -> str:
        """基于特征生成预测提示词
        
        Args:
            kb_name: 知识库名称
            features: 文档特征
            
        Returns:
            预测提示词（注重创意启发而非简单模仿）
        """
        style = features.get('writing_style', {})
        common_patterns = features.get('common_patterns', [])
        avg_length = features.get('avg_sentence_length', 20)
        
        prompt_parts = [
            f"【{kb_name}创意剧情预测】",
            "",
            "你的核心任务：为创作者提供「新颖、有张力、出人意料但合理」的剧情思路。",
            ""
        ]
        
        # ===== 第一部分：创意引导原则 =====
        prompt_parts.extend([
            "【创意引导原则】",
            "1. 🎭 制造意外转折：在读者预期之外，但事后细想符合逻辑",
            "2. 💥 增强戏剧冲突：挖掘人物矛盾、目标障碍、价值观碰撞",
            "3. 🔍 深挖隐藏线索：发现文本中未明说的伏笔、动机、潜台词",
            "4. 🎯 强化人物动机：让角色行为源于深层欲望、恐惧或秘密",
            "5. 🌊 营造情感张力：通过对比、反差、延迟满足增强感染力",
            "6. 🧩 埋设悬念种子：为后续情节留下钩子，引发读者好奇",
            ""
        ])
        
        # ===== 第二部分：创意技巧工具箱 =====
        prompt_parts.extend([
            "【创意技巧工具箱】",
            "• 视角转换：切换到次要角色或对立方的视角",
            "• 时间跳跃：闪回关键记忆，或快进到关键时刻",
            "• 情绪反转：从高潮到低谷，或从绝望到希望",
            "• 信息不对称：让角色知道读者不知道的，或反之",
            "• 道具/细节：用看似无关的小物件触发大事件",
            "• 环境干预：天气、场所、意外事件打断原计划",
            "• 对话暗流：表面平静的对话下暗藏锋芒",
            ""
        ])
        
        # ===== 第三部分：风格适配 =====
        prompt_parts.append("【风格适配要求】")
        
        # 叙事视角
        narrative_perspective = style.get('narrative_perspective', 'third')
        if narrative_perspective == 'first':
            prompt_parts.append("✓ 第一人称叙述：深入主角内心，展现主观感受与误判")
        else:
            prompt_parts.append("✓ 第三人称叙述：可展现多角色视角，揭示更多信息层次")
        
        # 节奏控制
        pacing = style.get('pacing', 'medium')
        if pacing == 'fast':
            prompt_parts.append("✓ 快节奏：用突发事件、快速对话、连环动作推进")
        elif pacing == 'slow':
            prompt_parts.append("✓ 慢节奏：用细腻心理、环境描写、情绪铺垫营造氛围")
        else:
            prompt_parts.append("✓ 适中节奏：张弛有度，在关键处加速或减速")
        
        # 句子长度风格
        if avg_length < 15:
            prompt_parts.append("✓ 短句风格：用干脆利落的句子制造紧张感")
        elif avg_length > 30:
            prompt_parts.append("✓ 长句风格：用复杂句式展现层次感和思考深度")
        else:
            prompt_parts.append("✓ 句式灵活：根据情节需要调整长短")
        
        # 对话使用
        if style.get('has_dialogue', False):
            prompt_parts.append("✓ 善用对话：让对话推动情节、揭示性格、制造冲突")
        
        # 情感基调
        emotion_tone = style.get('emotion_tone', 'neutral')
        if emotion_tone == 'positive':
            prompt_parts.append("✓ 基调偏向：在积极中埋设隐忧，增加戏剧张力")
        elif emotion_tone == 'melancholic':
            prompt_parts.append("✓ 基调偏向：在忧郁中寻找希望火光，形成反差")
        else:
            prompt_parts.append("✓ 情感灵活：根据剧情需要调配情绪色彩")
        
        prompt_parts.append("")
        
        # ===== 第四部分：句式参考（可选） =====
        if common_patterns:
            prompt_parts.append("【句式节奏参考】")
            for pattern in common_patterns[:3]:
                prompt_parts.append(f"• {pattern}（可创造性变化）")
            prompt_parts.append("")
        
        # ===== 第五部分：核心输出要求 =====
        prompt_parts.extend([
            "【核心输出要求】",
            "✦ 优先级排序：创意新颖度 > 戏剧张力 > 风格契合度 > 语言流畅度",
            "✦ 思考路径：",
            "  1) 分析当前情境的潜在冲突点和转折可能",
            "  2) 识别最意想不到但又暗藏伏笔的发展方向",
            "  3) 选择能最大化情感冲击和悬念的表现方式",
            "  4) 用符合风格的语言将创意具象化",
            "✦ 输出形式：两行完整的后续文本，每行独立成句",
            "✦ 避免陷阱：",
            "  × 平庸延续：机械性地沿着最显而易见的路线发展",
            "  × 生硬转折：为了意外而意外，缺乏铺垫和逻辑",
            "  × 风格断裂：过度追求创意而偏离作品整体基调",
            "  × 信息过载：在两行内塞入过多新元素导致混乱",
            ""
        ])
        
        # ===== 第六部分：创意启发示例 =====
        prompt_parts.extend([
            "【创意启发示例】",
            "若原文是角色A向B告白 →",
            "  • 传统续写：B回应接受/拒绝",
            "  • 创意思路：C突然出现打断/A自己说到一半突然停下/B的反应完全出乎A意料",
            "",
            "若原文是角色准备行动 →",
            "  • 传统续写：按计划执行",
            "  • 创意思路：发现计划致命漏洞/内心突然动摇/意外发现改变一切的信息",
            ""
        ])
        
        prompt_parts.append("现在，请基于上述原则，为创作者生成令人眼前一亮的后续两行剧情。")
        
        return "\n".join(prompt_parts)
    
    def _get_default_features(self) -> Dict[str, Any]:
        """获取默认特征（当知识库为空时使用）"""
        return {
            'avg_sentence_length': 20,
            'sentence_length_variance': 0,
            'punctuation_freq': {},
            'vocabulary_richness': 0.5,
            'common_phrases': [],
            'writing_style': {
                'has_dialogue': False,
                'descriptive_level': 'medium',
                'emotion_tone': 'neutral',
                'pacing': 'medium',
                'narrative_perspective': 'third',
                'dialogue_ratio': 0,
                'scene_change_frequency': 'medium'
            },
            'common_patterns': []
        }
    
    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        if not text:
            return []
        
        # 按照中文句子结束标记分割
        sentences = re.split(r'[。！？\n]+', text)
        
        # 过滤空句子和太短的句子
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 3]
        
        return sentences
    
    def _calculate_variance(self, numbers: List[float]) -> float:
        """计算方差"""
        if not numbers:
            return 0
        
        mean = sum(numbers) / len(numbers)
        variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
        return variance
    
    def _analyze_punctuation(self, text: str) -> Dict[str, float]:
        """分析标点符号使用频率"""
        if not text:
            return {}
        
        total_chars = len(text)
        if total_chars == 0:
            return {}
        
        return {
            'comma': text.count('，') / total_chars,
            'period': text.count('。') / total_chars,
            'exclamation': text.count('！') / total_chars,
            'question': text.count('？') / total_chars,
            'ellipsis': text.count('…') / total_chars,
            'colon': text.count('：') / total_chars,
            'semicolon': text.count('；') / total_chars,
        }
    
    def _analyze_vocabulary(self, text: str) -> float:
        """分析词汇丰富度（不同词汇数/总词汇数）"""
        if not text:
            return 0.5
        
        # 简单的中文分词（按标点和空格分割）
        words = re.findall(r'[\u4e00-\u9fff]+', text)
        
        if not words:
            return 0.5
        
        unique_words = len(set(words))
        total_words = len(words)
        
        return unique_words / total_words if total_words > 0 else 0.5
    
    def _extract_common_phrases(self, texts: List[str], top_n: int = 10) -> List[str]:
        """提取常见短语（2-4字）"""
        if not texts:
            return []
        
        # 提取所有2-4字的短语
        phrase_counter = Counter()
        
        for text in texts:
            # 移除标点符号
            clean_text = re.sub(r'[^\u4e00-\u9fff]', '', text)
            
            # 提取2-4字短语
            for length in [2, 3, 4]:
                for i in range(len(clean_text) - length + 1):
                    phrase = clean_text[i:i+length]
                    if len(phrase) == length:
                        phrase_counter[phrase] += 1
        
        # 过滤出现次数太少的短语
        min_count = 2
        common_phrases = [phrase for phrase, count in phrase_counter.most_common(top_n * 2) if count >= min_count]
        
        return common_phrases[:top_n]
    
    def _analyze_writing_style(self, text: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """分析写作风格"""
        style = {}
        
        # 1. 是否包含对话
        style['has_dialogue'] = '「' in text or '『' in text or '"' in text or '"' in text
        
        # 2. 对话占比
        dialogue_chars = text.count('「') + text.count('『') + text.count('"')
        total_chars = len(text)
        style['dialogue_ratio'] = dialogue_chars / total_chars if total_chars > 0 else 0
        
        # 3. 描写程度（基于形容词和副词的使用）
        descriptive_words = ['的', '地', '得', '很', '十分', '非常', '极其']
        descriptive_count = sum(text.count(word) for word in descriptive_words)
        descriptive_ratio = descriptive_count / total_chars if total_chars > 0 else 0
        
        if descriptive_ratio > 0.05:
            style['descriptive_level'] = 'high'
        elif descriptive_ratio < 0.02:
            style['descriptive_level'] = 'low'
        else:
            style['descriptive_level'] = 'medium'
        
        # 4. 情感基调（简单关键词检测）
        positive_words = ['笑', '高兴', '快乐', '开心', '喜悦', '温暖', '美好']
        negative_words = ['哭', '悲伤', '难过', '痛苦', '失望', '冷']
        
        positive_count = sum(text.count(word) for word in positive_words)
        negative_count = sum(text.count(word) for word in negative_words)
        
        if positive_count > negative_count * 1.5:
            style['emotion_tone'] = 'positive'
        elif negative_count > positive_count * 1.5:
            style['emotion_tone'] = 'melancholic'
        else:
            style['emotion_tone'] = 'neutral'
        
        # 5. 节奏快慢（基于句子长度和动词密度）
        avg_length = features.get('avg_sentence_length', 20)
        action_words = ['走', '跑', '说', '看', '拿', '打', '推', '拉']
        action_count = sum(text.count(word) for word in action_words)
        action_ratio = action_count / total_chars if total_chars > 0 else 0
        
        if avg_length < 15 and action_ratio > 0.01:
            style['pacing'] = 'fast'
        elif avg_length > 30 or action_ratio < 0.005:
            style['pacing'] = 'slow'
        else:
            style['pacing'] = 'medium'
        
        # 6. 叙事视角（简单检测）
        first_person_words = ['我', '咱', '俺']
        first_person_count = sum(text.count(word) for word in first_person_words)
        
        if first_person_count / total_chars > 0.01:
            style['narrative_perspective'] = 'first'
        else:
            style['narrative_perspective'] = 'third'
        
        # 7. 场景转换频率（基于段落数和时间/地点词汇）
        paragraphs = text.split('\n\n')
        scene_markers = ['此时', '这时', '突然', '后来', '接着', '然后', '于是']
        scene_marker_count = sum(text.count(word) for word in scene_markers)
        
        if len(paragraphs) > 10 and scene_marker_count > 5:
            style['scene_change_frequency'] = 'high'
        elif len(paragraphs) < 3 and scene_marker_count < 2:
            style['scene_change_frequency'] = 'low'
        else:
            style['scene_change_frequency'] = 'medium'
        
        return style
    
    def _extract_sentence_patterns(self, sentences: List[str], top_n: int = 5) -> List[str]:
        """提取常见句式模式"""
        if not sentences:
            return []
        
        patterns = []
        
        # 提取一些常见的句式特征
        for sentence in sentences[:50]:  # 只分析前50个句子
            # 1. 疑问句
            if '？' in sentence or '吗' in sentence[-2:] or '呢' in sentence[-2:]:
                patterns.append('疑问句式')
            
            # 2. 感叹句
            if '！' in sentence:
                patterns.append('感叹句式')
            
            # 3. 转折句
            if any(word in sentence for word in ['但是', '然而', '可是', '不过']):
                patterns.append('转折句式')
            
            # 4. 因果句
            if any(word in sentence for word in ['因为', '所以', '因此', '由于']):
                patterns.append('因果句式')
            
            # 5. 递进句
            if any(word in sentence for word in ['而且', '并且', '不仅', '甚至']):
                patterns.append('递进句式')
        
        # 统计并返回最常见的模式
        pattern_counter = Counter(patterns)
        return [pattern for pattern, _ in pattern_counter.most_common(top_n)]

