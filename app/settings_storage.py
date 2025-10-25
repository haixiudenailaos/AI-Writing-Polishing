"""设置文件存储模块

提供JSON配置文件的读写功能，支持安全的配置数据存储和访问。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from pathlib import Path


class SettingsStorage:
    """设置文件存储管理器
    
    使用JSON格式存储应用配置，包括API密钥、润色风格等敏感信息。
    """
    
    def __init__(self, config_dir: Optional[str] = None) -> None:
        """初始化设置存储
        
        Args:
            config_dir: 配置目录路径，默认为 app_data
        """
        if config_dir is None:
            # 默认使用项目根目录下的 app_data 文件夹
            project_root = Path(__file__).parent.parent
            config_dir = project_root / "app_data"
        
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "app_config.json"
        
        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def read(self) -> Dict[str, Any]:
        """读取配置文件
        
        Returns:
            配置数据字典，如果文件不存在则返回空字典
            
        Raises:
            OSError: 文件读取失败
            json.JSONDecodeError: JSON解析失败
        """
        if not self.config_file.exists():
            return {}
        
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise RuntimeError(f"读取配置文件失败: {e}") from e
    
    def write(self, data: Dict[str, Any]) -> None:
        """写入配置文件
        
        Args:
            data: 要写入的配置数据
            
        Raises:
            OSError: 文件写入失败
        """
        try:
            # 确保目录存在
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # 写入配置文件
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            # 设置文件权限（仅当前用户可访问）
            if os.name != 'nt':  # Unix/Linux系统
                os.chmod(self.config_file, 0o600)
                
        except OSError as e:
            raise RuntimeError(f"写入配置文件失败: {e}") from e
    
    def backup(self, suffix: str = ".backup") -> Path:
        """备份当前配置文件
        
        Args:
            suffix: 备份文件后缀
            
        Returns:
            备份文件路径
            
        Raises:
            OSError: 备份失败
        """
        if not self.config_file.exists():
            raise RuntimeError("配置文件不存在，无法备份")
        
        backup_file = self.config_file.with_suffix(self.config_file.suffix + suffix)
        
        try:
            import shutil
            shutil.copy2(self.config_file, backup_file)
            return backup_file
        except OSError as e:
            raise RuntimeError(f"备份配置文件失败: {e}") from e
    
    def restore(self, backup_file: Path) -> None:
        """从备份文件恢复配置
        
        Args:
            backup_file: 备份文件路径
            
        Raises:
            OSError: 恢复失败
        """
        if not backup_file.exists():
            raise RuntimeError(f"备份文件不存在: {backup_file}")
        
        try:
            import shutil
            shutil.copy2(backup_file, self.config_file)
        except OSError as e:
            raise RuntimeError(f"恢复配置文件失败: {e}") from e
    
    def exists(self) -> bool:
        """检查配置文件是否存在
        
        Returns:
            配置文件是否存在
        """
        return self.config_file.exists()
    
    def get_config_path(self) -> Path:
        """获取配置文件路径
        
        Returns:
            配置文件路径
        """
        return self.config_file
    
    def clear(self) -> None:
        """清空配置文件
        
        Raises:
            OSError: 删除失败
        """
        try:
            if self.config_file.exists():
                self.config_file.unlink()
        except OSError as e:
            raise RuntimeError(f"清空配置文件失败: {e}") from e