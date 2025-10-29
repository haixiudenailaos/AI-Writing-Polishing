"""
润色风格管理器
负责管理预设和自定义润色风格，支持多选组合
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import json
from app.config_manager import PolishStyle, ConfigManager


@dataclass
class StyleCombination:
    """风格组合"""
    name: str
    description: str
    style_ids: List[str]
    is_custom: bool = True


class StyleManager:
    """润色风格管理器"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._style_combinations: Dict[str, StyleCombination] = {}
        self._load_style_combinations()
    
    def get_preset_styles(self) -> List[PolishStyle]:
        """获取预设风格列表"""
        config = self.config_manager.get_config()
        return [style for style in config.polish_styles if style.is_preset]
    
    def get_custom_styles(self) -> List[PolishStyle]:
        """获取自定义风格列表"""
        config = self.config_manager.get_config()
        return [style for style in config.polish_styles if not style.is_preset]
    
    def get_all_styles(self) -> List[PolishStyle]:
        """获取所有风格（预设+自定义）"""
        preset = self.get_preset_styles()
        custom = self.get_custom_styles()
        return preset + custom
    
    def get_style_by_id(self, style_id: str) -> Optional[PolishStyle]:
        """根据ID获取风格"""
        all_styles = self.get_all_styles()
        for style in all_styles:
            if style.id == style_id:
                return style
        return None
    
    def get_selected_styles(self) -> List[PolishStyle]:
        """获取当前选中的风格列表"""
        config = self.config_manager.get_config()
        selected_ids = config.selected_styles
        
        selected_styles = []
        for style_id in selected_ids:
            style = self.get_style_by_id(style_id)
            if style:
                selected_styles.append(style)
        
        return selected_styles
    
    def set_selected_styles(self, style_ids: List[str]) -> bool:
        """设置选中的风格"""
        try:
            # 验证所有风格ID是否存在
            all_style_ids = [style.id for style in self.get_all_styles()]
            for style_id in style_ids:
                if style_id not in all_style_ids:
                    return False
            
            # 更新配置
            self.config_manager.update_selected_styles(style_ids)
            return True
        except Exception:
            return False
    
    def add_custom_style(self, style: PolishStyle) -> bool:
        """添加自定义风格"""
        try:
            # 检查ID是否已存在
            if self.get_style_by_id(style.id):
                return False
            
            # 使用ConfigManager的方法添加自定义风格
            self.config_manager.add_custom_style(style.name, style.prompt, style.parameters)
            return True
        except Exception:
            return False
    
    def update_custom_style(self, style: PolishStyle) -> bool:
        """更新自定义风格"""
        try:
            # 使用ConfigManager的方法更新自定义风格
            return self.config_manager.update_custom_style(
                style.id, style.name, style.prompt, style.parameters
            )
        except Exception:
            return False
    
    def delete_custom_style(self, style_id: str) -> bool:
        """删除自定义风格"""
        try:
            # 使用ConfigManager的方法删除自定义风格
            return self.config_manager.remove_custom_style(style_id)
        except Exception:
            return False
    
    def create_style_combination(self, name: str, description: str, style_ids: List[str]) -> bool:
        """创建风格组合"""
        try:
            # 验证所有风格ID是否存在
            all_style_ids = [style.id for style in self.get_all_styles()]
            for style_id in style_ids:
                if style_id not in all_style_ids:
                    return False
            
            combination_id = f"combo_{len(self._style_combinations)}"
            combination = StyleCombination(
                name=name,
                description=description,
                style_ids=style_ids
            )
            
            self._style_combinations[combination_id] = combination
            self._save_style_combinations()
            return True
        except Exception:
            return False
    
    def get_style_combinations(self) -> Dict[str, StyleCombination]:
        """获取所有风格组合"""
        return self._style_combinations.copy()
    
    def apply_style_combination(self, combination_id: str) -> bool:
        """应用风格组合"""
        if combination_id not in self._style_combinations:
            return False
        
        combination = self._style_combinations[combination_id]
        return self.set_selected_styles(combination.style_ids)
    
    def delete_style_combination(self, combination_id: str) -> bool:
        """删除风格组合"""
        try:
            if combination_id in self._style_combinations:
                del self._style_combinations[combination_id]
                self._save_style_combinations()
                return True
            return False
        except Exception:
            return False
    
    def get_combined_prompt(self, selected_styles: Optional[List[PolishStyle]] = None) -> str:
        """获取组合后的润色提示词"""
        if selected_styles is None:
            selected_styles = self.get_selected_styles()
        
        if not selected_styles:
            return "请润色以下文本，保持原意的同时提升表达质量。"
        
        # 组合多个风格的提示词
        style_descriptions = []
        for style in selected_styles:
            if style.prompt:
                style_descriptions.append(f"{style.name}：{style.prompt}")
        
        if style_descriptions:
            combined_description = "；".join(style_descriptions)
            return f"请按照以下风格要求润色文本：{combined_description}。保持原意的同时提升表达质量。"
        else:
            return "请润色以下文本，保持原意的同时提升表达质量。"
    
    def validate_style_selection(self, style_ids: List[str]) -> Dict[str, Any]:
        """验证风格选择的有效性"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        all_style_ids = [style.id for style in self.get_all_styles()]
        
        # 检查无效的风格ID
        invalid_ids = [sid for sid in style_ids if sid not in all_style_ids]
        if invalid_ids:
            result["valid"] = False
            result["errors"].append(f"无效的风格ID: {', '.join(invalid_ids)}")
        
        # 检查是否选择了太多风格
        if len(style_ids) > 5:
            result["warnings"].append("选择的风格过多，可能影响润色效果")
        
        # 检查风格兼容性（如果有冲突的风格）
        selected_styles = [self.get_style_by_id(sid) for sid in style_ids if sid in all_style_ids]
        style_names = [style.name for style in selected_styles if style]
        
        # 检查可能的冲突组合
        conflicting_pairs = [
            ("简洁", "详细"),
            ("正式", "口语化"),
            ("古典", "现代")
        ]
        
        for name1, name2 in conflicting_pairs:
            if name1 in style_names and name2 in style_names:
                result["warnings"].append(f"'{name1}'和'{name2}'风格可能存在冲突")
        
        return result
    
    def _load_style_combinations(self):
        """加载风格组合"""
        try:
            combinations_file = self.config_manager.settings_storage.get_config_path().parent / "style_combinations.json"
            if combinations_file.exists():
                with open(combinations_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for combo_id, combo_data in data.items():
                        self._style_combinations[combo_id] = StyleCombination(**combo_data)
        except Exception:
            # 如果加载失败，使用空字典
            self._style_combinations = {}
    
    def _save_style_combinations(self):
        """保存风格组合"""
        try:
            combinations_file = self.config_manager.settings_storage.get_config_path().parent / "style_combinations.json"
            combinations_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {}
            for combo_id, combination in self._style_combinations.items():
                data[combo_id] = asdict(combination)
            
            with open(combinations_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 静默处理保存错误
    
    def export_styles(self, file_path: str, include_preset: bool = False) -> bool:
        """导出风格配置"""
        try:
            export_data = {
                "custom_styles": [asdict(style) for style in self.get_custom_styles()],
                "style_combinations": {k: asdict(v) for k, v in self._style_combinations.items()}
            }
            
            if include_preset:
                export_data["preset_styles"] = [asdict(style) for style in self.get_preset_styles()]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception:
            return False
    
    def import_styles(self, file_path: str, overwrite_existing: bool = False) -> Dict[str, Any]:
        """导入风格配置"""
        result = {
            "success": False,
            "imported_styles": 0,
            "imported_combinations": 0,
            "errors": []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 导入自定义风格
            if "custom_styles" in data:
                for style_data in data["custom_styles"]:
                    try:
                        style = PolishStyle(**style_data)
                        if overwrite_existing or not self.get_style_by_id(style.id):
                            if overwrite_existing and self.get_style_by_id(style.id):
                                self.update_custom_style(style)
                            else:
                                self.add_custom_style(style)
                            result["imported_styles"] += 1
                    except Exception as e:
                        result["errors"].append(f"导入风格失败: {str(e)}")
            
            # 导入风格组合
            if "style_combinations" in data:
                for combo_id, combo_data in data["style_combinations"].items():
                    try:
                        combination = StyleCombination(**combo_data)
                        if overwrite_existing or combo_id not in self._style_combinations:
                            self._style_combinations[combo_id] = combination
                            result["imported_combinations"] += 1
                    except Exception as e:
                        result["errors"].append(f"导入组合失败: {str(e)}")
                
                self._save_style_combinations()
            
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(f"文件读取失败: {str(e)}")
        
        return result