"""配置管理模块

提供应用配置的统一管理，包括API配置、润色风格、系统设置等。
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional
from pathlib import Path

from app.settings_storage import SettingsStorage


@dataclass
class APIConfig:
    """API配置数据结构"""
    api_key: str = ""
    base_url: str = "https://api.siliconflow.cn/v1/chat/completions"
    model: str = "deepseek-ai/DeepSeek-V3.2-Exp"
    timeout: int = 45
    
    # 向量化API配置
    embedding_api_key: str = ""  # 阿里云API密钥
    embedding_model: str = "text-embedding-v4"  # 向量模型


@dataclass
class PolishStyle:
    """润色风格数据结构"""
    id: str
    name: str
    prompt: str
    is_preset: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportConfig:
    """导出配置数据结构"""
    export_directory: str = ""  # 导出目录路径
    auto_export_enabled: bool = False  # 是否启用实时导出
    export_filename: str = "字见润新.txt"  # 导出文件名


@dataclass
class WorkspaceConfig:
    """工作区配置数据结构"""
    last_opened_folder: str = ""  # 上次打开的文件夹路径
    prediction_enabled: bool = False  # 剧情预测功能是否启用（默认关闭）


@dataclass
class AppConfig:
    """应用配置数据结构"""
    api_config: APIConfig = field(default_factory=APIConfig)
    polish_styles: List[PolishStyle] = field(default_factory=list)
    selected_styles: List[str] = field(default_factory=lambda: ["standard"])
    theme: str = "dark"
    version: str = "2.0.0"
    export_config: ExportConfig = field(default_factory=ExportConfig)  # 导出配置
    workspace_config: WorkspaceConfig = field(default_factory=WorkspaceConfig)  # 工作区配置


class ConfigManager:
    """配置管理器
    
    负责应用配置的加载、保存、迁移和验证。
    """
    
    # 预设润色风格定义
    PRESET_STYLES = {
        "professional_screenwriter": PolishStyle(
            id="professional_screenwriter",
            name="专业编剧",
            prompt="""你是一位资深影视编剧，请对以下文本进行专业的戏剧性润色。润色时需注重以下方面：

1. **戏剧张力**：增强情节的戏剧冲突和悬念，让每一句话都推动故事发展。
2. **人物塑造**：
   - 对话要符合角色身份、性格和背景，体现人物的独特性。
   - 通过语言展现人物的内心世界和情感变化。
   - 注意人物关系的层次和微妙变化。
3. **视觉化表达**：
   - 将抽象描述转化为具体的视觉画面。
   - 运用电影化的叙事技巧，如蒙太奇、特写等概念。
   - 注重场景的氛围营造和细节描写。
4. **节奏控制**：
   - 调整句式长短，营造紧张或舒缓的节奏。
   - 合理运用停顿、重复等技巧增强戏剧效果。
5. **专业标准**：
   - 符合影视剧本的格式和表达习惯。
   - 语言简洁有力，避免冗余的文学性修饰。
   - 确保内容适合视听媒体的表现形式。

请保持原文的核心情节和人物关系，输出润色后的完整文本。""",
            is_preset=True,
            parameters={"temperature": 0.7}
        ),
        "game_copywriter": PolishStyle(
            id="game_copywriter",
            name="游戏文案",
            prompt="""你是一位专业游戏文案策划，请对以下文本进行游戏化润色。润色时需注重以下方面：

1. **沉浸式叙事**：
   - 营造引人入胜的游戏世界观和氛围。
   - 使用第二人称或适合游戏体验的叙述视角。
   - 增强玩家的代入感和参与感。
2. **角色设定**：
   - 突出角色的职业特色、技能背景和性格特点。
   - 使用符合游戏世界观的专业术语和设定。
   - 体现角色在游戏中的作用和重要性。
3. **任务导向**：
   - 明确任务目标和奖励机制。
   - 增加紧迫感和挑战性的表达。
   - 合理设置悬念和线索引导。
4. **互动性表达**：
   - 使用引导性和激励性的语言。
   - 适当加入选择分支的暗示。
   - 体现玩家行为对故事发展的影响。
5. **游戏化元素**：
   - 融入等级、技能、装备等游戏概念。
   - 使用符合游戏类型的专业词汇。
   - 保持与游戏机制的一致性。

请保持原文的核心内容，输出适合游戏环境的润色文本。""",
            is_preset=True,
            parameters={"temperature": 0.6}
        ),
        "xiaohongshu_expert": PolishStyle(
            id="xiaohongshu_expert",
            name="小红书达人",
            prompt="""你是一位小红书平台的资深内容创作者，请对以下文本进行小红书风格的润色。润色时需注重以下方面：

1. **吸睛标题化**：
   - 使用数字、符号和关键词突出重点。
   - 适当运用疑问句、感叹句增加互动性。
   - 融入热门话题和流行元素。
2. **生活化表达**：
   - 使用亲切自然的口语化表达。
   - 分享个人体验和真实感受。
   - 增加生活场景的具体描述。
3. **视觉化内容**：
   - 描述适合拍照分享的场景和细节。
   - 使用颜色、质感等视觉化词汇。
   - 突出美感和时尚元素。
4. **互动引导**：
   - 适当使用提问引发评论互动。
   - 加入"姐妹们"、"宝贝们"等亲密称呼。
   - 鼓励点赞、收藏、分享的行为。
5. **实用价值**：
   - 提供具体的建议和干货内容。
   - 分享使用心得和注意事项。
   - 突出性价比和实用性。
6. **格式优化**：
   - 适当使用emoji表情符号。
   - 合理分段，提高可读性。
   - 使用"✨"、"💕"等装饰符号。

请保持原文的核心信息，输出符合小红书平台风格的润色文本。""",
            is_preset=True,
            parameters={"temperature": 0.8}
        ),
        "corporate_pr": PolishStyle(
            id="corporate_pr",
            name="大厂外宣",
            prompt="""你是一位大型企业的资深公关文案专家，请对以下文本进行企业对外宣传的专业润色。润色时需注重以下方面：

1. **品牌形象**：
   - 体现企业的专业性、权威性和可信度。
   - 使用正式、规范的商务语言。
   - 突出企业的核心价值观和使命愿景。
2. **战略高度**：
   - 从行业发展和市场趋势的角度阐述。
   - 体现企业的前瞻性和领导地位。
   - 强调创新能力和技术实力。
3. **数据支撑**：
   - 适当引用具体数据和成果。
   - 使用量化指标证明企业实力。
   - 体现市场表现和用户认可。
4. **社会责任**：
   - 强调企业的社会价值和贡献。
   - 体现可持续发展理念。
   - 展现企业的责任担当。
5. **国际视野**：
   - 使用国际化的表达方式。
   - 体现全球化布局和合作。
   - 符合国际商务沟通标准。
6. **媒体友好**：
   - 结构清晰，便于媒体引用。
   - 突出新闻价值和传播亮点。
   - 避免过度营销化的表达。

请保持原文的核心信息，输出符合大型企业对外宣传标准的专业文本。""",
            is_preset=True,
            parameters={"temperature": 0.4}
        ),
        "political_rigorous": PolishStyle(
            id="political_rigorous",
            name="政治严谨",
            prompt="""你是一位资深政务文件撰写专家，请对以下文本进行政治严谨的润色。润色时需注重以下方面：

1. **政治正确性**：
   - 确保表达符合主流价值观和政策导向。
   - 使用准确、规范的政治术语。
   - 避免可能引起争议或误解的表达。
2. **权威性表达**：
   - 使用庄重、正式的公文语言。
   - 体现政府部门的权威性和公信力。
   - 符合官方文件的表达习惯。
3. **逻辑严密**：
   - 确保论述逻辑清晰、条理分明。
   - 使用准确的因果关系表达。
   - 避免模糊或歧义的表述。
4. **数据准确**：
   - 确保所有数据和事实的准确性。
   - 使用权威来源的信息。
   - 避免夸大或不实的表达。
5. **格式规范**：
   - 符合公文写作的格式要求。
   - 使用标准的政务用语和句式。
   - 保持文体的一致性和规范性。
6. **社会影响**：
   - 考虑文本的社会影响和传播效果。
   - 体现正面的价值导向。
   - 避免可能造成负面影响的表达。
7. **时效性**：
   - 确保内容与当前政策保持一致。
   - 体现时代特色和发展要求。
   - 避免过时或不合时宜的表达。

请保持原文的核心内容和政策导向，输出符合政务文件标准的严谨文本。""",
            is_preset=True,
            parameters={"temperature": 0.3}
        )
    }
    
    def __init__(self, config_dir: Optional[str] = None) -> None:
        """初始化配置管理器
        
        Args:
            config_dir: 配置目录路径，默认为 app_data
        """
        self.storage = SettingsStorage(config_dir)
        self._config: Optional[AppConfig] = None
        
        # 加载配置
        self._load_config()
    
    def _load_config(self) -> None:
        """加载应用配置"""
        try:
            data = self.storage.read()
            if not data:
                # 首次运行，创建默认配置
                self._config = self._create_default_config()
                self.save_config()
                return
            
            # 解析配置数据
            self._config = self._parse_config_data(data)
            
            # 检查是否需要迁移
            if self._needs_migration():
                self._migrate_config()
            
            # 如果原始文件中 api_key 是 dict，保存回修正后的结构
            try:
                if isinstance(data.get("api_config", {}).get("api_key"), dict):
                    self.save_config()
            except Exception:
                pass
                
        except Exception as e:
            # 配置加载失败，使用默认配置
            print(f"配置加载失败，使用默认配置: {e}")
            self._config = self._create_default_config()
            self.save_config()
    
    def _create_default_config(self) -> AppConfig:
        """创建默认配置"""
        # 尝试从环境变量迁移
        api_config = APIConfig()
        if os.getenv("AI_API_KEY"):
            api_config.api_key = os.getenv("AI_API_KEY", "")
            api_config.base_url = os.getenv("AI_BASE_URL", api_config.base_url)
            api_config.model = os.getenv("AI_MODEL", api_config.model)
        
        # 加载预设风格
        preset_styles = list(self.PRESET_STYLES.values())
        
        return AppConfig(
            api_config=api_config,
            polish_styles=preset_styles,
            selected_styles=["professional_screenwriter"],
            theme="dark",
            version="2.1.0",
            export_config=ExportConfig(),
            workspace_config=WorkspaceConfig()
        )
    
    def _parse_config_data(self, data: Dict[str, Any]) -> AppConfig:
        """解析配置数据"""
        # 解析API配置（兼容历史错误的嵌套结构）
        api_data = data.get("api_config", {})
        api_key_value = api_data.get("api_key", "")
        if isinstance(api_key_value, dict):
            api_key_value = api_key_value.get("api_key", "")
        base_url_value = api_data.get("base_url", "https://api.siliconflow.cn/v1/chat/completions")
        model_value = api_data.get("model", "deepseek-ai/DeepSeek-V3.2-Exp")
        timeout_value = api_data.get("timeout", 45)
        
        # 向量化API配置
        embedding_api_key_value = api_data.get("embedding_api_key", "")
        embedding_model_value = api_data.get("embedding_model", "text-embedding-v4")

        # 类型规范化
        try:
            timeout_value = int(timeout_value)
        except Exception:
            timeout_value = 45

        api_config = APIConfig(
            api_key=str(api_key_value or ""),
            base_url=str(base_url_value or "https://api.siliconflow.cn/v1/chat/completions"),
            model=str(model_value or "deepseek-ai/DeepSeek-V3.2-Exp"),
            timeout=timeout_value,
            embedding_api_key=str(embedding_api_key_value or ""),
            embedding_model=str(embedding_model_value or "text-embedding-v4")
        )
        
        # 解析润色风格
        styles_data = data.get("polish_styles", {})
        polish_styles = []
        
        # 添加预设风格
        preset_style_ids = styles_data.get("preset_styles", ["professional_screenwriter", "game_copywriter", "xiaohongshu_expert", "corporate_pr", "political_rigorous"])
        for style_id in preset_style_ids:
            if style_id in self.PRESET_STYLES:
                polish_styles.append(self.PRESET_STYLES[style_id])
        
        # 添加自定义风格
        custom_styles_data = styles_data.get("custom_styles", [])
        for style_data in custom_styles_data:
            style = PolishStyle(
                id=style_data.get("id", str(uuid.uuid4())),
                name=style_data.get("name", "未命名风格"),
                prompt=style_data.get("prompt", ""),
                is_preset=False,
                parameters=style_data.get("parameters", {})
            )
            polish_styles.append(style)
        
        # 选中的风格
        selected_styles = styles_data.get("selected_styles", ["professional_screenwriter"])
        
        # 解析导出配置
        export_data = data.get("export_config", {})
        export_config = ExportConfig(
            export_directory=export_data.get("export_directory", ""),
            auto_export_enabled=export_data.get("auto_export_enabled", False),
            export_filename=export_data.get("export_filename", "字见润新.txt")
        )
        
        # 解析工作区配置
        workspace_data = data.get("workspace_config", {})
        workspace_config = WorkspaceConfig(
            last_opened_folder=workspace_data.get("last_opened_folder", "")
        )
        
        return AppConfig(
            api_config=api_config,
            polish_styles=polish_styles,
            selected_styles=selected_styles,
            theme=data.get("theme", "dark"),
            version=data.get("version", "2.0.0"),
            export_config=export_config,
            workspace_config=workspace_config
        )
    
    def _needs_migration(self) -> bool:
        """检查是否需要配置迁移"""
        if not self._config:
            return False
        
        # 检查版本号
        current_version = self._config.version
        if current_version not in ["2.0.0", "2.1.0"]:
            return True
        
        # 检查是否缺少预设风格
        preset_ids = {style.id for style in self._config.polish_styles if style.is_preset}
        required_presets = set(self.PRESET_STYLES.keys())
        if not required_presets.issubset(preset_ids):
            return True
        
        return False
    
    def _migrate_config(self) -> None:
        """迁移配置"""
        if not self._config:
            return
        
        # 备份当前配置
        try:
            self.storage.backup(".migration_backup")
        except Exception as e:
            print(f"备份配置失败: {e}")
        
        # 更新版本号
        self._config.version = "2.1.0"
        
        # 确保所有预设风格都存在
        existing_preset_ids = {style.id for style in self._config.polish_styles if style.is_preset}
        for preset_id, preset_style in self.PRESET_STYLES.items():
            if preset_id not in existing_preset_ids:
                self._config.polish_styles.append(preset_style)
        
        # 保存迁移后的配置
        self.save_config()
        print("配置迁移完成")
    
    def get_config(self) -> AppConfig:
        """获取当前配置"""
        if self._config is None:
            self._load_config()
        return self._config or self._create_default_config()
    
    def get_api_config(self) -> APIConfig:
        """获取API配置"""
        config = self.get_config()
        return config.api_config
    
    def save_config(self) -> None:
        """保存配置"""
        if not self._config:
            return
        
        # 转换为字典格式
        config_dict = self._config_to_dict(self._config)
        
        try:
            self.storage.write(config_dict)
        except Exception as e:
            raise RuntimeError(f"保存配置失败: {e}") from e
    
    def _config_to_dict(self, config: AppConfig) -> Dict[str, Any]:
        """将配置对象转换为字典"""
        # API配置
        api_config_dict = asdict(config.api_config)
        
        # 润色风格配置
        preset_styles = [style.id for style in config.polish_styles if style.is_preset]
        custom_styles = []
        for style in config.polish_styles:
            if not style.is_preset:
                custom_styles.append(asdict(style))
        
        polish_styles_dict = {
            "preset_styles": preset_styles,
            "custom_styles": custom_styles,
            "selected_styles": config.selected_styles
        }
        
        # 导出配置
        export_config_dict = asdict(config.export_config)
        
        # 工作区配置
        workspace_config_dict = asdict(config.workspace_config)
        
        return {
            "api_config": api_config_dict,
            "polish_styles": polish_styles_dict,
            "theme": config.theme,
            "version": config.version,
            "export_config": export_config_dict,
            "workspace_config": workspace_config_dict
        }
    
    def update_api_config(self, api_key: str, base_url: Optional[str] = None, 
                         model: Optional[str] = None, timeout: Optional[int] = None,
                         embedding_api_key: Optional[str] = None,
                         embedding_model: Optional[str] = None) -> None:
        """更新API配置"""
        config = self.get_config()
        config.api_config.api_key = api_key
        if base_url is not None:
            config.api_config.base_url = base_url
        if model is not None:
            config.api_config.model = model
        if timeout is not None:
            config.api_config.timeout = timeout
        if embedding_api_key is not None:
            config.api_config.embedding_api_key = embedding_api_key
        if embedding_model is not None:
            config.api_config.embedding_model = embedding_model
        
        self.save_config()
    
    def add_custom_style(self, name: str, prompt: str, parameters: Optional[Dict[str, Any]] = None) -> PolishStyle:
        """添加自定义风格"""
        config = self.get_config()
        
        style = PolishStyle(
            id=str(uuid.uuid4()),
            name=name,
            prompt=prompt,
            is_preset=False,
            parameters=parameters or {}
        )
        
        config.polish_styles.append(style)
        self.save_config()
        
        return style
    
    def update_custom_style(self, style_id: str, name: Optional[str] = None, 
                           prompt: Optional[str] = None, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """更新自定义风格"""
        config = self.get_config()
        
        for style in config.polish_styles:
            if style.id == style_id and not style.is_preset:
                if name is not None:
                    style.name = name
                if prompt is not None:
                    style.prompt = prompt
                if parameters is not None:
                    style.parameters = parameters
                
                self.save_config()
                return True
        
        return False
    
    def remove_custom_style(self, style_id: str) -> bool:
        """删除自定义风格"""
        config = self.get_config()
        
        for i, style in enumerate(config.polish_styles):
            if style.id == style_id and not style.is_preset:
                config.polish_styles.pop(i)
                
                # 从选中列表中移除
                if style_id in config.selected_styles:
                    config.selected_styles.remove(style_id)
                
                self.save_config()
                return True
        
        return False
    
    def update_selected_styles(self, style_ids: List[str]) -> None:
        """更新选中的风格"""
        config = self.get_config()
        
        # 验证风格ID是否存在
        available_ids = {style.id for style in config.polish_styles}
        valid_ids = [style_id for style_id in style_ids if style_id in available_ids]
        
        config.selected_styles = valid_ids or ["standard"]
        self.save_config()
    
    def get_selected_styles(self) -> List[PolishStyle]:
        """获取选中的风格"""
        config = self.get_config()
        
        selected_styles = []
        style_dict = {style.id: style for style in config.polish_styles}
        
        for style_id in config.selected_styles:
            if style_id in style_dict:
                selected_styles.append(style_dict[style_id])
        
        return selected_styles or [self.PRESET_STYLES["professional_screenwriter"]]
    
    def test_api_connection(self) -> bool:
        """测试API连接"""
        config = self.get_config()
        
        if not config.api_config.api_key:
            return False
        
        try:
            import requests
            
            headers = {
                "Authorization": f"Bearer {config.api_config.api_key}",
                "Content-Type": "application/json"
            }
            
            # 发送简单的测试请求
            payload = {
                "model": config.api_config.model,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1
            }
            
            response = requests.post(
                config.api_config.base_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            return response.status_code in (200, 400)  # 400也表示连接成功，只是请求格式问题
            
        except Exception:
            return False
    
    def backup_config(self, file_path: str) -> bool:
        """备份当前配置到用户选择的文件路径"""
        try:
            if not file_path:
                return False
            from pathlib import Path
            import json
            cfg = self.get_config()
            cfg_dict = self._config_to_dict(cfg)
            dest = Path(file_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(cfg_dict, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def restore_config(self, file_path: str) -> bool:
        """从备份文件恢复配置到应用内配置文件"""
        from pathlib import Path
        import json
        backup_path = None
        try:
            # 为当前配置创建自动备份，便于回滚
            try:
                backup_path = self.storage.backup(".manual_restore_backup")
            except Exception:
                backup_path = None
            
            src = Path(file_path)
            if not src.exists():
                return False
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 解析并规范数据结构
            new_cfg = self._parse_config_data(data)
            self._config = new_cfg
            self.save_config()
            return True
        except Exception:
            # 回滚到恢复前的备份
            try:
                if backup_path:
                    self.storage.restore(Path(backup_path))
            except Exception:
                pass
            return False
    
    @property
    def settings_storage(self) -> SettingsStorage:
        """兼容属性：提供对底层存储的访问（与旧代码一致）。"""
        return self.storage
    
    def reset_config(self) -> None:
        """重置当前配置为默认值，并尝试备份以便回滚"""
        backup_path = None
        try:
            try:
                backup_path = self.storage.backup(".reset_backup")
            except Exception:
                backup_path = None
            self._config = self._create_default_config()
            self.save_config()
        except Exception as e:
            try:
                if backup_path:
                    self.storage.restore(Path(backup_path))
            except Exception:
                pass
            raise e
    
    def reset_to_defaults(self) -> bool:
        """兼容旧接口：重置为默认配置并备份当前配置"""
        try:
            self.reset_config()
            return True
        except Exception:
            return False
    
    def get_export_config(self) -> ExportConfig:
        """获取导出配置"""
        config = self.get_config()
        return config.export_config
    
    def update_export_config(self, export_directory: Optional[str] = None,
                            auto_export_enabled: Optional[bool] = None,
                            export_filename: Optional[str] = None) -> None:
        """更新导出配置
        
        Args:
            export_directory: 导出目录路径
            auto_export_enabled: 是否启用实时导出
            export_filename: 导出文件名
        """
        config = self.get_config()
        if export_directory is not None:
            config.export_config.export_directory = export_directory
        if auto_export_enabled is not None:
            config.export_config.auto_export_enabled = auto_export_enabled
        if export_filename is not None:
            config.export_config.export_filename = export_filename
        
        self.save_config()
    
    def get_workspace_config(self) -> WorkspaceConfig:
        """获取工作区配置"""
        config = self.get_config()
        return config.workspace_config
    
    def update_last_opened_folder(self, folder_path: str) -> None:
        """更新上次打开的文件夹路径
        
        Args:
            folder_path: 文件夹路径
        """
        config = self.get_config()
        config.workspace_config.last_opened_folder = folder_path
        self.save_config()
    
    def update_workspace_config(self, workspace_config: WorkspaceConfig) -> None:
        """更新工作区配置
        
        Args:
            workspace_config: 工作区配置对象
        """
        config = self.get_config()
        config.workspace_config = workspace_config
        self.save_config()