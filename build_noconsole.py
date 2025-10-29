#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字见润新 - 无控制台版本打包脚本

此脚本用于生成不显示控制台窗口的可执行文件版本，适合最终用户使用。
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
import time

def print_header(title):
    """打印格式化的标题"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def print_step(step, description):
    """打印步骤信息"""
    print(f"\n[步骤 {step}] {description}")
    print("-" * 40)

def check_requirements():
    """检查构建环境"""
    print_step(1, "检查构建环境")
    
    # 检查Python版本
    python_version = sys.version_info
    print(f"Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version < (3, 8):
        print("❌ 错误: 需要Python 3.8或更高版本")
        return False
    
    # 检查PyInstaller
    try:
        import PyInstaller
        print(f"✅ PyInstaller版本: {PyInstaller.__version__}")
    except ImportError:
        print("❌ 错误: 未安装PyInstaller")
        print("请运行: pip install pyinstaller")
        return False
    
    # 检查项目文件
    project_root = Path(__file__).parent
    main_file = project_root / "app" / "main.py"
    spec_file = project_root / "novel_polish.spec"
    
    if not main_file.exists():
        print(f"❌ 错误: 主程序文件不存在: {main_file}")
        return False
    
    if not spec_file.exists():
        print(f"❌ 错误: spec配置文件不存在: {spec_file}")
        return False
    
    print("✅ 构建环境检查通过")
    return True

def clean_build_dirs():
    """清理构建目录"""
    print_step(2, "清理构建目录")
    
    project_root = Path(__file__).parent
    dirs_to_clean = ["build", "dist"]
    
    for dir_name in dirs_to_clean:
        dir_path = project_root / dir_name
        if dir_path.exists():
            print(f"🗑️  删除目录: {dir_path}")
            shutil.rmtree(dir_path)
        else:
            print(f"📁 目录不存在，跳过: {dir_path}")
    
    print("✅ 构建目录清理完成")

def install_dependencies():
    """安装依赖包"""
    print_step(3, "检查并安装依赖包")
    
    project_root = Path(__file__).parent
    requirements_file = project_root / "requirements.txt"
    
    if not requirements_file.exists():
        print("⚠️  警告: requirements.txt文件不存在")
        return True
    
    print("📦 安装项目依赖...")
    try:
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ 依赖包安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖包安装失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False

def build_noconsole_version():
    """构建无控制台版本"""
    print_step(4, "构建无控制台版本")
    
    project_root = Path(__file__).parent
    main_file = project_root / "app" / "main.py"
    
    print("🔨 开始PyInstaller构建...")
    print(f"主程序文件: {main_file}")
    
    # 构建命令 - 直接使用PyInstaller命令行参数
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=字见润新",  # 应用名称
        "--onefile",  # 单文件模式
        "--noconsole",  # 不显示控制台
        "--clean",  # 清理缓存
        "--noconfirm",  # 不询问覆盖
        f"--icon={project_root / 'app_icon.ico'}" if (project_root / 'app_icon.ico').exists() else "",
        
        # 添加数据文件
        f"--add-data={project_root / 'app_icon.ico'};." if (project_root / 'app_icon.ico').exists() else "",
        f"--add-data={project_root / '.env'};." if (project_root / '.env').exists() else "",
        
        # 隐藏导入
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui", 
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PySide6.QtNetwork",
        "--hidden-import=requests",
        "--hidden-import=dotenv",
        "--hidden-import=docx",
        "--hidden-import=bs4",
        "--hidden-import=ebooklib",
        "--hidden-import=xml.etree.ElementTree",
        "--hidden-import=sqlite3",
        "--hidden-import=json",
        "--hidden-import=pathlib",
        "--hidden-import=threading",
        "--hidden-import=queue",
        "--hidden-import=asyncio",
        "--hidden-import=concurrent.futures",
        
        # 应用模块
        "--hidden-import=app",
        "--hidden-import=app.api_client",
        "--hidden-import=app.auto_export_manager",
        "--hidden-import=app.auto_save_manager",
        "--hidden-import=app.config_manager",
        "--hidden-import=app.config_migration",
        "--hidden-import=app.document_handler",
        "--hidden-import=app.knowledge_base",
        "--hidden-import=app.request_queue_manager",
        "--hidden-import=app.settings_storage",
        "--hidden-import=app.style_manager",
        "--hidden-import=app.text_processor",
        "--hidden-import=app.widgets",
        "--hidden-import=app.processors",
        
        # 排除不需要的模块
        "--exclude-module=tkinter",
        "--exclude-module=matplotlib",
        "--exclude-module=numpy",
        "--exclude-module=pandas",
        "--exclude-module=scipy",
        "--exclude-module=IPython",
        "--exclude-module=jupyter",
        "--exclude-module=pytest",
        "--exclude-module=unittest",
        
        str(main_file)
    ]
    
    # 过滤空字符串参数
    cmd = [arg for arg in cmd if arg]
    
    print(f"执行命令: {' '.join(cmd[:5])}... (共{len(cmd)}个参数)")
    
    try:
        # 记录开始时间
        start_time = time.time()
        
        # 执行构建
        result = subprocess.run(
            cmd, 
            cwd=str(project_root),
            check=True, 
            capture_output=True, 
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        # 计算构建时间
        build_time = time.time() - start_time
        
        print(f"✅ 构建成功! 耗时: {build_time:.1f}秒")
        
        # 显示构建输出的关键信息
        if result.stdout:
            lines = result.stdout.split('\n')
            for line in lines:
                if any(keyword in line.lower() for keyword in ['warning', 'error', 'missing', 'failed']):
                    print(f"⚠️  {line}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        print(f"错误输出: {e.stderr}")
        if e.stdout:
            print(f"标准输出: {e.stdout}")
        return False

def verify_build():
    """验证构建结果"""
    print_step(5, "验证构建结果")
    
    project_root = Path(__file__).parent
    dist_dir = project_root / "dist"
    
    if not dist_dir.exists():
        print("❌ 错误: dist目录不存在")
        return False
    
    # 查找生成的可执行文件
    exe_files = list(dist_dir.glob("*.exe"))
    noconsole_exe = None
    
    for exe_file in exe_files:
        if "字见润新.exe" == exe_file.name:
            noconsole_exe = exe_file
            break
    
    if not noconsole_exe:
        print("❌ 错误: 未找到无控制台版本的可执行文件")
        print(f"dist目录内容: {list(dist_dir.iterdir())}")
        return False
    
    # 检查文件大小
    file_size = noconsole_exe.stat().st_size / (1024 * 1024)  # MB
    print(f"📁 可执行文件: {noconsole_exe.name}")
    print(f"📏 文件大小: {file_size:.1f} MB")
    
    if file_size < 10:
        print("⚠️  警告: 文件大小异常小，可能缺少依赖")
    
    # 检查图标
    icon_file = project_root / "app_icon.ico"
    if icon_file.exists():
        print("✅ 图标文件已包含")
    else:
        print("⚠️  警告: 图标文件不存在")
    
    print("✅ 构建验证完成")
    return True

def show_results():
    """显示构建结果"""
    print_header("构建完成")
    
    project_root = Path(__file__).parent
    dist_dir = project_root / "dist"
    
    if dist_dir.exists():
        print("📦 生成的文件:")
        for item in dist_dir.iterdir():
            if item.is_file():
                size = item.stat().st_size / (1024 * 1024)
                print(f"  📄 {item.name} ({size:.1f} MB)")
        
        print(f"\n📂 输出目录: {dist_dir.absolute()}")
        
        # 查找无控制台版本
        noconsole_exe = dist_dir / "字见润新.exe"
        
        if noconsole_exe.exists():
            print(f"\n🎯 无控制台版本: {noconsole_exe.name}")
            print("💡 此版本不会显示控制台窗口，适合最终用户使用")
            print("⚠️  注意: 如果程序出现问题，建议使用带控制台版本进行调试")
            print(f"🚀 运行命令: {noconsole_exe.absolute()}")
    else:
        print("❌ 构建失败，未生成输出文件")

def main():
    """主函数"""
    print_header("字见润新 - 无控制台版本构建")
    print("🎯 目标: 生成不显示控制台窗口的可执行文件")
    print("💡 用途: 最终用户使用的正式版本")
    
    try:
        # 检查构建环境
        if not check_requirements():
            return 1
        
        # 清理构建目录
        clean_build_dirs()
        
        # 安装依赖
        if not install_dependencies():
            return 1
        
        # 执行构建
        if not build_noconsole_version():
            return 1
        
        # 验证构建结果
        if not verify_build():
            return 1
        
        # 显示结果
        show_results()
        
        print("\n🎉 无控制台版本构建成功!")
        print("\n💡 提示:")
        print("  - 此版本适合最终用户使用")
        print("  - 如需调试，请使用带控制台版本")
        print("  - 建议在干净环境中测试程序功能")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  构建被用户中断")
        return 1
    except Exception as e:
        print(f"\n❌ 构建过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)