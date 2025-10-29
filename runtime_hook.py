#!/usr/bin/env python3
"""
PyInstaller 运行时钩子
在打包后的应用启动时执行，确保正确初始化环境

关键功能：修复无控制台模式下的 stdout/stderr 问题
"""

import os
import sys
import io
from pathlib import Path


def fix_stdout_stderr():
    """
    ========== 关键修复：处理无控制台模式 ==========
    
    当 PyInstaller 使用 console=False 打包时：
    - sys.stdout 和 sys.stderr 可能为 None 或不可用
    - 任何 print() 或 sys.stdout.flush() 都会导致程序崩溃
    
    解决方案：
    1. 如果控制台可用，正常输出（调试版）
    2. 如果控制台不可用，重定向到日志文件或NUL设备（正式版）
    """
    try:
        # 检查 stdout/stderr 是否可用
        stdout_available = (
            sys.stdout is not None and 
            hasattr(sys.stdout, 'write') and
            hasattr(sys.stdout, 'flush')
        )
        
        stderr_available = (
            sys.stderr is not None and 
            hasattr(sys.stderr, 'write') and
            hasattr(sys.stderr, 'flush')
        )
        
        if not stdout_available or not stderr_available:
            # ========== 无控制台模式：重定向到日志文件 ==========
            # 获取日志目录
            if sys.platform == 'win32':
                app_data = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
            else:
                app_data = Path.home() / '.local' / 'share'
            
            log_dir = app_data / 'NovelPolish' / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建日志文件
            log_file = log_dir / 'app_output.log'
            
            try:
                # 重定向到日志文件
                log_stream = open(log_file, 'w', encoding='utf-8', errors='ignore')
                if not stdout_available:
                    sys.stdout = log_stream
                if not stderr_available:
                    sys.stderr = log_stream
            except:
                # 如果无法创建日志文件，使用 NUL 设备
                if sys.platform == 'win32':
                    null_device = open('NUL', 'w')
                else:
                    null_device = open('/dev/null', 'w')
                
                if not stdout_available:
                    sys.stdout = null_device
                if not stderr_available:
                    sys.stderr = null_device
        else:
            # ========== 控制台可用：包装以避免编码错误 ==========
            if sys.platform == 'win32':
                try:
                    # 包装 stdout，处理 Unicode 编码问题
                    if hasattr(sys.stdout, 'buffer'):
                        sys.stdout = io.TextIOWrapper(
                            sys.stdout.buffer,
                            encoding='utf-8',
                            errors='replace',
                            line_buffering=True
                        )
                    
                    # 包装 stderr
                    if hasattr(sys.stderr, 'buffer'):
                        sys.stderr = io.TextIOWrapper(
                            sys.stderr.buffer,
                            encoding='utf-8',
                            errors='replace',
                            line_buffering=True
                        )
                except:
                    # 包装失败，保持原样
                    pass
                    
    except Exception as e:
        # 最后的后备方案：使用内存流（丢弃所有输出）
        try:
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
        except:
            pass


def init_user_data_dir():
    """初始化用户数据目录"""
    try:
        # 获取用户数据目录（与 settings_storage.py 保持一致）
        if sys.platform == 'win32':
            # Windows: %APPDATA%\GuojiRunse
            base_dir = Path(os.getenv('APPDATA', ''))
            app_data_dir = base_dir / 'GuojiRunse'
        elif sys.platform == 'darwin':
            # macOS: ~/.guojirunse
            app_data_dir = Path.home() / '.guojirunse'
        else:
            # Linux: ~/.guojirunse
            app_data_dir = Path.home() / '.guojirunse'
        
        # 创建必要的目录
        dirs_to_create = [
            app_data_dir,
            app_data_dir / 'knowledge_bases',
            app_data_dir / 'exports',
            app_data_dir / 'backups',
        ]
        
        for dir_path in dirs_to_create:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # 设置环境变量，供应用使用
        os.environ['NOVEL_POLISHER_DATA_DIR'] = str(app_data_dir)
        
    except Exception as e:
        # 静默处理错误，不影响应用启动
        try:
            print(f"[Warning] Failed to initialize user data directory: {e}", file=sys.stderr)
        except:
            pass


def check_first_run():
    """检查是否首次运行"""
    try:
        app_data_dir = os.getenv('NOVEL_POLISHER_DATA_DIR')
        if app_data_dir:
            config_file = Path(app_data_dir) / 'app_config.json'
            if not config_file.exists():
                # 首次运行，设置标志
                os.environ['NOVEL_POLISHER_FIRST_RUN'] = '1'
            else:
                os.environ['NOVEL_POLISHER_FIRST_RUN'] = '0'
    except Exception:
        pass


def setup_environment():
    """设置应用环境"""
    try:
        # 确保当前工作目录正确
        if getattr(sys, 'frozen', False):
            # 打包后的应用
            app_dir = Path(sys._MEIPASS)  # type: ignore
        else:
            # 开发环境
            app_dir = Path(__file__).parent
        
        # 添加应用目录到Python路径
        if str(app_dir) not in sys.path:
            sys.path.insert(0, str(app_dir))
        
    except Exception as e:
        print(f"[Warning] Failed to setup environment: {e}", file=sys.stderr)


def preload_critical_modules():
    """预加载关键模块，确保打包后正常运行"""
    try:
        # 预加载异步处理相关的关键模块
        import threading
        import queue
        import logging
        import enum
        import time
        import traceback
        
        # 预加载Qt相关模块（关键：包含 Q_ARG 用于跨线程调用）
        from PySide6.QtCore import (
            QObject, Signal, QThread, QTimer, QMetaObject, Qt,
            Q_ARG  # 关键：用于 invokeMethod 跨线程调用
        )
        
        try:
            print("[Runtime Hook] Critical modules preloaded successfully")
        except:
            pass
        
    except Exception as e:
        try:
            print(f"[Warning] Failed to preload critical modules: {e}", file=sys.stderr)
        except:
            pass


# ========== 执行初始化（顺序很重要！）==========

# 0. 最优先：修复 stdout/stderr（必须在任何 print 之前）
fix_stdout_stderr()

try:
    print("[Runtime Hook] Initializing application environment...")
except:
    pass

# 1. 预加载关键模块
preload_critical_modules()

# 2. 初始化用户数据目录
init_user_data_dir()

# 3. 检查首次运行
check_first_run()

# 4. 设置环境
setup_environment()

try:
    print("[Runtime Hook] Initialization complete.")
except:
    pass

