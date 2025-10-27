"""
配置迁移模块
负责从环境变量迁移到JSON配置文件
"""

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import asdict
from pathlib import Path

from config_manager import ConfigManager, APIConfig, PolishStyle
from settings_storage import SettingsStorage


class ConfigMigration:
    """配置迁移工具"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.storage = config_manager.storage
        
    def check_migration_needed(self) -> Dict[str, Any]:
        """检查是否需要迁移
        
        Returns:
            Dict包含迁移状态信息:
            - needs_migration: bool - 是否需要迁移
            - env_vars_found: List[str] - 找到的环境变量
            - config_exists: bool - 配置文件是否存在
            - migration_type: str - 迁移类型
        """
        # 检查环境变量
        env_vars = self._check_environment_variables()
        
        # 检查配置文件
        config_exists = self.storage.exists()
        
        # 判断迁移类型
        migration_type = "none"
        needs_migration = False
        
        if env_vars and not config_exists:
            # 首次迁移：从环境变量创建配置文件
            migration_type = "env_to_json"
            needs_migration = True
        elif env_vars and config_exists:
            # 检查配置文件中是否缺少环境变量中的值
            try:
                current_config = self.config_manager.get_config()
                if self._should_update_from_env(current_config, env_vars):
                    migration_type = "update_from_env"
                    needs_migration = True
            except Exception:
                migration_type = "env_to_json"
                needs_migration = True
        elif not env_vars and not config_exists:
            # 全新安装，无需迁移
            migration_type = "fresh_install"
        
        return {
            "needs_migration": needs_migration,
            "env_vars_found": list(env_vars.keys()),
            "config_exists": config_exists,
            "migration_type": migration_type,
            "env_values": env_vars
        }
    
    def _check_environment_variables(self) -> Dict[str, str]:
        """检查相关的环境变量"""
        env_vars = {}
        
        # 检查API相关环境变量
        api_key = os.getenv("AI_API_KEY")
        if api_key:
            env_vars["AI_API_KEY"] = api_key
        
        base_url = os.getenv("AI_BASE_URL")
        if base_url:
            env_vars["AI_BASE_URL"] = base_url
        
        model = os.getenv("AI_MODEL")
        if model:
            env_vars["AI_MODEL"] = model
        
        # 检查其他可能的环境变量
        timeout = os.getenv("AI_TIMEOUT")
        if timeout:
            env_vars["AI_TIMEOUT"] = timeout
        
        theme = os.getenv("APP_THEME")
        if theme:
            env_vars["APP_THEME"] = theme
        
        return env_vars
    
    def _should_update_from_env(self, current_config, env_vars: Dict[str, str]) -> bool:
        """检查是否应该从环境变量更新配置"""
        # 如果API密钥为空但环境变量中有，则需要更新
        if not current_config.api_config.api_key and env_vars.get("AI_API_KEY"):
            return True
        
        # 如果环境变量中的值与配置文件中的不同，可能需要更新
        # 这里采用保守策略，只在配置为默认值时才更新
        if (env_vars.get("AI_BASE_URL") and 
            current_config.api_config.base_url == "https://api.siliconflow.cn/v1/chat/completions"):
            return True
        
        return False
    
    def perform_migration(self, migration_info: Dict[str, Any], 
                         backup: bool = True) -> Dict[str, Any]:
        """执行配置迁移
        
        Args:
            migration_info: check_migration_needed()返回的信息
            backup: 是否备份现有配置
            
        Returns:
            Dict包含迁移结果:
            - success: bool - 迁移是否成功
            - message: str - 结果消息
            - backup_path: Optional[str] - 备份文件路径
            - migrated_values: Dict - 迁移的值
        """
        if not migration_info["needs_migration"]:
            return {
                "success": True,
                "message": "无需迁移",
                "backup_path": None,
                "migrated_values": {}
            }
        
        backup_path = None
        try:
            # 备份现有配置
            if backup and migration_info["config_exists"]:
                backup_path = self._create_backup()
            
            # 执行迁移
            migrated_values = self._migrate_from_environment(migration_info["env_values"])
            
            return {
                "success": True,
                "message": f"迁移成功，已迁移 {len(migrated_values)} 个配置项",
                "backup_path": backup_path,
                "migrated_values": migrated_values
            }
            
        except Exception as e:
            # 迁移失败，尝试恢复备份
            if backup_path:
                try:
                    self._restore_backup(backup_path)
                except Exception as restore_error:
                    return {
                        "success": False,
                        "message": f"迁移失败且备份恢复失败: {e}, 恢复错误: {restore_error}",
                        "backup_path": backup_path,
                        "migrated_values": {}
                    }
            
            return {
                "success": False,
                "message": f"迁移失败: {e}",
                "backup_path": backup_path,
                "migrated_values": {}
            }
    
    def _create_backup(self) -> str:
        """创建配置备份"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_suffix = f"migration_backup_{timestamp}"
        
        backup_path = self.storage.backup(backup_suffix)
        return backup_path
    
    def _restore_backup(self, backup_path: str) -> None:
        """恢复配置备份"""
        if os.path.exists(backup_path):
            # 读取备份文件
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # 恢复配置
            self.storage.write(backup_data)
    
    def _migrate_from_environment(self, env_vars: Dict[str, str]) -> Dict[str, Any]:
        """从环境变量迁移配置"""
        migrated_values = {}
        
        # 获取当前配置或创建默认配置
        try:
            current_config = self.config_manager.get_config()
        except Exception:
            current_config = self.config_manager._create_default_config()
        
        # 迁移API配置
        if "AI_API_KEY" in env_vars:
            current_config.api_config.api_key = env_vars["AI_API_KEY"]
            migrated_values["api_key"] = "已设置"
        
        if "AI_BASE_URL" in env_vars:
            current_config.api_config.base_url = env_vars["AI_BASE_URL"]
            migrated_values["base_url"] = env_vars["AI_BASE_URL"]
        
        if "AI_MODEL" in env_vars:
            current_config.api_config.model = env_vars["AI_MODEL"]
            migrated_values["model"] = env_vars["AI_MODEL"]
        
        if "AI_TIMEOUT" in env_vars:
            try:
                timeout = int(env_vars["AI_TIMEOUT"])
                current_config.api_config.timeout = timeout
                migrated_values["timeout"] = timeout
            except ValueError:
                pass
        
        # 迁移主题配置
        if "APP_THEME" in env_vars:
            theme = env_vars["APP_THEME"].lower()
            if theme in ["light", "dark"]:
                current_config.theme = theme
                migrated_values["theme"] = theme
        
        # 保存迁移后的配置
        self.config_manager._config = current_config
        self.config_manager.save_config()
        
        return migrated_values
    
    def cleanup_environment_variables(self, env_vars: List[str], 
                                    confirm: bool = False) -> Dict[str, Any]:
        """清理环境变量（可选）
        
        Args:
            env_vars: 要清理的环境变量列表
            confirm: 是否确认清理
            
        Returns:
            Dict包含清理结果
        """
        if not confirm:
            return {
                "success": False,
                "message": "需要确认才能清理环境变量",
                "cleaned_vars": []
            }
        
        cleaned_vars = []
        failed_vars = []
        
        for var_name in env_vars:
            try:
                if var_name in os.environ:
                    # 注意：在Python中删除环境变量只影响当前进程
                    # 要永久删除需要修改系统环境变量
                    del os.environ[var_name]
                    cleaned_vars.append(var_name)
            except Exception as e:
                failed_vars.append(f"{var_name}: {e}")
        
        message = f"已清理 {len(cleaned_vars)} 个环境变量"
        if failed_vars:
            message += f"，{len(failed_vars)} 个失败"
        
        return {
            "success": len(failed_vars) == 0,
            "message": message,
            "cleaned_vars": cleaned_vars,
            "failed_vars": failed_vars
        }
    
    def get_migration_report(self) -> str:
        """生成迁移报告"""
        migration_info = self.check_migration_needed()
        
        report = ["=== 配置迁移报告 ===\n"]
        
        # 基本信息
        report.append(f"配置文件存在: {'是' if migration_info['config_exists'] else '否'}")
        report.append(f"环境变量数量: {len(migration_info['env_vars_found'])}")
        report.append(f"迁移类型: {migration_info['migration_type']}")
        report.append(f"需要迁移: {'是' if migration_info['needs_migration'] else '否'}")
        
        # 环境变量详情
        if migration_info['env_vars_found']:
            report.append("\n发现的环境变量:")
            for var_name in migration_info['env_vars_found']:
                if var_name == "AI_API_KEY":
                    report.append(f"  - {var_name}: [已设置]")
                else:
                    value = migration_info['env_values'].get(var_name, "")
                    report.append(f"  - {var_name}: {value}")
        
        # 迁移建议
        report.append("\n迁移建议:")
        if migration_info['migration_type'] == "env_to_json":
            report.append("  建议执行迁移，将环境变量配置转移到JSON文件")
        elif migration_info['migration_type'] == "update_from_env":
            report.append("  建议更新配置文件中的部分设置")
        elif migration_info['migration_type'] == "fresh_install":
            report.append("  全新安装，无需迁移")
        else:
            report.append("  当前配置正常，无需迁移")
        
        return "\n".join(report)