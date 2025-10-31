# -*- mode: python ; coding: utf-8 -*-
"""
字见润新 PyInstaller 配置文件
支持生成带控制台和不带控制台两个版本
"""

import os
import sys
from pathlib import Path

# 项目根目录
project_root = Path(SPECPATH)
app_dir = project_root / 'app'

# 收集所有Python文件
def collect_app_files():
    """收集app目录下的所有Python文件"""
    files = []
    for py_file in app_dir.rglob('*.py'):
        if py_file.name != '__pycache__':
            rel_path = py_file.relative_to(project_root)
            files.append((str(py_file), str(rel_path.parent)))
    return files

# 收集数据文件
datas = [
    # 图标文件
    ('app_icon.ico', '.'),
    # 如果有.env文件，也包含进去
]

# 检查并添加.env文件
env_file = project_root / '.env'
if env_file.exists():
    datas.append(('.env', '.'))

# 隐藏导入 - 确保所有模块都被包含
hiddenimports = [
    # PySide6 相关
    'PySide6.QtCore',
    'PySide6.QtGui', 
    'PySide6.QtWidgets',
    'PySide6.QtNetwork',
    
    # 应用模块
    'app',
    'app.api_client',
    'app.auto_export_manager',
    'app.auto_save_manager',
    'app.config_manager',
    'app.config_migration',
    'app.document_handler',
    'app.knowledge_base',
    'app.prompt_generator',
    'app.request_queue_manager',
    'app.settings_storage',
    'app.style_manager',
    'app.text_processor',
    
    # widgets 子模块
    'app.widgets',
    'app.widgets.batch_polish_dialog',
    'app.widgets.design_system',
    'app.widgets.file_explorer',
    'app.widgets.knowledge_base_dialog',
    'app.widgets.loading_overlay',
    'app.widgets.output_list',
    'app.widgets.polish_result_panel',
    'app.widgets.prediction_toggle',
    'app.widgets.settings_dialog',
    'app.widgets.theme_manager',
    'app.widgets.ui_enhancer',
    
    # processors 子模块
    'app.processors',
    'app.processors.async_polish_processor',
    
    # 第三方依赖
    'requests',
    'requests.adapters',
    'requests.auth',
    'requests.cookies',
    'requests.exceptions',
    'requests.models',
    'requests.sessions',
    'requests.structures',
    'requests.utils',
    'urllib3',
    'urllib3.util',
    'urllib3.util.retry',
    'urllib3.poolmanager',
    'urllib3.connectionpool',
    
    # python-dotenv
    'dotenv',
    'dotenv.main',
    
    # python-docx
    'docx',
    'docx.api',
    'docx.document',
    'docx.shared',
    'docx.text',
    'docx.oxml',
    'docx.parts',
    'docx.styles',
    
    # ebooklib
    'ebooklib',
    'ebooklib.epub',
    
    # beautifulsoup4
    'bs4',
    'bs4.builder',
    'bs4.dammit',
    'bs4.element',
    
    # 标准库模块
    'json',
    'sqlite3',
    'xml',
    'xml.etree',
    'xml.etree.ElementTree',
    'pathlib',
    'threading',
    'queue',
    'asyncio',
    'concurrent',
    'concurrent.futures',
    'functools',
    'itertools',
    'uuid',
    'dataclasses',
    'typing',
    'enum',
    'datetime',
    'time',
    'os',
    'sys',
    'io',
    're',
    'base64',
    'hashlib',
    'hmac',
    'ssl',
    'socket',
    'http',
    'http.client',
    'urllib',
    'urllib.parse',
    'urllib.request',
    'zipfile',
    'tempfile',
    'shutil',
    'logging',
    'traceback',
    'inspect',
    'collections',
    'collections.abc',
    'weakref',
    'copy',
    'pickle',
]

# 排除的模块
excludes = [
    'tkinter',
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'IPython',
    'jupyter',
    'notebook',
    'pytest',
    'test',
    'tests',
    'unittest',
]

# 分析配置
a = Analysis(
    ['app/main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'] if (project_root / 'runtime_hook.py').exists() else [],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# 处理重复文件
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# 带控制台版本的EXE配置
exe_console = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='字见润新_控制台版',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 显示控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 暂时禁用图标，避免转换错误
)

# 不带控制台版本的EXE配置
exe_noconsole = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='字见润新',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 暂时禁用图标，避免转换错误
)