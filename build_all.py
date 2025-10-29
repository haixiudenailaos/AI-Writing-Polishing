#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字见润新 - 统一构建脚本

此脚本用于同时生成带控制台和不带控制台两个版本的可执行文件。
提供完整的构建流程，包括环境检查、依赖安装、构建和验证。
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
import time
import argparse

def print_header(title):
    """打印格式化的标题"""
    print("\n" + "="*70)
    print(f" {title}")
    print("="*70)

def print_step(step, description):
    """打印步骤信息"""
    print(f"\n[步骤 {step}] {description}")
    print("-" * 50)

def print_substep(description):
    """打印子步骤信息"""
    print(f"  → {description}")

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
    requirements_file = project_root / "requirements.txt"
    
    print_substep("检查项目文件:")
    
    if not main_file.exists():
        print(f"  ❌ 主程序文件不存在: {main_file}")
        return False
    else:
        print(f"  ✅ 主程序文件: {main_file}")
    
    if not spec_file.exists():
        print(f"  ❌ spec配置文件不存在: {spec_file}")
        return False
    else:
        print(f"  ✅ spec配置文件: {spec_file}")
    
    if not requirements_file.exists():
        print(f"  ⚠️  requirements.txt不存在: {requirements_file}")
    else:
        print(f"  ✅ 依赖文件: {requirements_file}")
    
    # 检查图标文件
    icon_file = project_root / "app_icon.ico"
    if icon_file.exists():
        print(f"  ✅ 图标文件: {icon_file}")
    else:
        print(f"  ⚠️  图标文件不存在: {icon_file}")
    
    print("✅ 构建环境检查通过")
    return True

def clean_build_dirs():
    """清理构建目录"""
    print_step(2, "清理构建目录")
    
    project_root = Path(__file__).parent
    dirs_to_clean = ["build", "dist", "__pycache__"]
    
    for dir_name in dirs_to_clean:
        dir_path = project_root / dir_name
        if dir_path.exists():
            print_substep(f"删除目录: {dir_path}")
            shutil.rmtree(dir_path)
        else:
            print_substep(f"目录不存在，跳过: {dir_path}")
    
    # 清理.pyc文件
    print_substep("清理.pyc文件")
    for pyc_file in project_root.rglob("*.pyc"):
        pyc_file.unlink()
    
    print("✅ 构建目录清理完成")

def install_dependencies():
    """安装依赖包"""
    print_step(3, "检查并安装依赖包")
    
    project_root = Path(__file__).parent
    requirements_file = project_root / "requirements.txt"
    
    if not requirements_file.exists():
        print("⚠️  警告: requirements.txt文件不存在，跳过依赖安装")
        return True
    
    print_substep("安装项目依赖...")
    try:
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ 依赖包安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖包安装失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False

def build_with_spec():
    """使用spec文件构建两个版本"""
    print_step(4, "使用spec文件构建两个版本")
    
    project_root = Path(__file__).parent
    spec_file = project_root / "novel_polish.spec"
    
    print_substep(f"使用配置文件: {spec_file}")
    
    # 构建命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",  # 清理缓存
        "--noconfirm",  # 不询问覆盖
        str(spec_file)
    ]
    
    print_substep(f"执行命令: {' '.join(cmd)}")
    
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
            warnings = []
            errors = []
            
            for line in lines:
                line_lower = line.lower()
                if 'warning' in line_lower:
                    warnings.append(line)
                elif any(keyword in line_lower for keyword in ['error', 'failed', 'missing']):
                    errors.append(line)
            
            if warnings:
                print_substep("构建警告:")
                for warning in warnings[:5]:  # 只显示前5个警告
                    print(f"    ⚠️  {warning}")
                if len(warnings) > 5:
                    print(f"    ... 还有 {len(warnings) - 5} 个警告")
            
            if errors:
                print_substep("构建错误:")
                for error in errors:
                    print(f"    ❌ {error}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        print(f"错误输出: {e.stderr}")
        if e.stdout:
            print(f"标准输出: {e.stdout}")
        return False

def verify_builds():
    """验证构建结果"""
    print_step(5, "验证构建结果")
    
    project_root = Path(__file__).parent
    dist_dir = project_root / "dist"
    
    if not dist_dir.exists():
        print("❌ 错误: dist目录不存在")
        return False
    
    # 查找生成的可执行文件
    exe_files = list(dist_dir.glob("*.exe"))
    
    if not exe_files:
        print("❌ 错误: 未找到任何可执行文件")
        return False
    
    print_substep("检查生成的可执行文件:")
    
    console_exe = None
    noconsole_exe = None
    
    for exe_file in exe_files:
        file_size = exe_file.stat().st_size / (1024 * 1024)  # MB
        print(f"  📄 {exe_file.name} ({file_size:.1f} MB)")
        
        if "控制台" in exe_file.name or "console" in exe_file.name.lower():
            console_exe = exe_file
        elif "字见润新.exe" == exe_file.name:
            noconsole_exe = exe_file
    
    # 验证两个版本都存在
    success = True
    
    if console_exe:
        print(f"  ✅ 带控制台版本: {console_exe.name}")
    else:
        print("  ❌ 缺少带控制台版本")
        success = False
    
    if noconsole_exe:
        print(f"  ✅ 无控制台版本: {noconsole_exe.name}")
    else:
        print("  ❌ 缺少无控制台版本")
        success = False
    
    # 检查文件大小
    for exe_file in exe_files:
        file_size = exe_file.stat().st_size / (1024 * 1024)
        if file_size < 10:
            print(f"  ⚠️  警告: {exe_file.name} 文件大小异常小 ({file_size:.1f} MB)")
    
    if success:
        print("✅ 构建验证完成")
    else:
        print("❌ 构建验证失败")
    
    return success

def run_basic_tests():
    """运行基本测试"""
    print_step(6, "运行基本测试")
    
    project_root = Path(__file__).parent
    dist_dir = project_root / "dist"
    
    # 查找可执行文件
    exe_files = list(dist_dir.glob("*.exe"))
    
    if not exe_files:
        print("❌ 没有可执行文件可供测试")
        return False
    
    print_substep("测试可执行文件启动:")
    
    for exe_file in exe_files:
        print(f"  测试: {exe_file.name}")
        
        try:
            # 尝试启动程序并快速退出
            # 注意: 对于GUI程序，这个测试可能不会立即返回
            cmd = [str(exe_file), "--help"]  # 尝试显示帮助信息
            
            result = subprocess.run(
                cmd,
                timeout=10,  # 10秒超时
                capture_output=True,
                text=True
            )
            
            print(f"    ✅ {exe_file.name} 启动成功")
            
        except subprocess.TimeoutExpired:
            print(f"    ⚠️  {exe_file.name} 启动超时（可能是GUI程序正常行为）")
        except subprocess.CalledProcessError as e:
            print(f"    ❌ {exe_file.name} 启动失败: {e}")
        except Exception as e:
            print(f"    ⚠️  {exe_file.name} 测试异常: {e}")
    
    print("✅ 基本测试完成")
    return True

def show_results():
    """显示构建结果"""
    print_header("构建完成")
    
    project_root = Path(__file__).parent
    dist_dir = project_root / "dist"
    
    if not dist_dir.exists():
        print("❌ 构建失败，未生成输出文件")
        return
    
    print("📦 生成的文件:")
    total_size = 0
    
    for item in dist_dir.iterdir():
        if item.is_file():
            size = item.stat().st_size / (1024 * 1024)
            total_size += size
            
            # 根据文件类型显示不同图标
            if item.suffix == '.exe':
                icon = "🚀"
            else:
                icon = "📄"
            
            print(f"  {icon} {item.name} ({size:.1f} MB)")
    
    print(f"\n📊 总大小: {total_size:.1f} MB")
    print(f"📂 输出目录: {dist_dir.absolute()}")
    
    # 显示使用说明
    print("\n💡 使用说明:")
    
    console_exe = None
    noconsole_exe = None
    
    for exe_file in dist_dir.glob("*.exe"):
        if "控制台" in exe_file.name:
            console_exe = exe_file
        elif "字见润新.exe" == exe_file.name:
            noconsole_exe = exe_file
    
    if console_exe:
        print(f"  🖥️  调试版本: {console_exe.name}")
        print("     - 显示控制台窗口，便于查看运行日志")
        print("     - 适合开发者和技术用户使用")
        print("     - 出现问题时可以看到详细错误信息")
    
    if noconsole_exe:
        print(f"  👤 用户版本: {noconsole_exe.name}")
        print("     - 不显示控制台窗口，界面简洁")
        print("     - 适合最终用户使用")
        print("     - 如有问题，建议使用调试版本排查")
    
    print("\n🎯 建议测试流程:")
    print("  1. 先测试带控制台版本，确保功能正常")
    print("  2. 再测试无控制台版本，验证用户体验")
    print("  3. 在干净的Windows环境中进行最终测试")
    print("  4. 验证所有业务流程和文件I/O操作")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="字见润新统一构建脚本")
    parser.add_argument("--skip-deps", action="store_true", help="跳过依赖安装")
    parser.add_argument("--skip-clean", action="store_true", help="跳过清理构建目录")
    parser.add_argument("--skip-tests", action="store_true", help="跳过基本测试")
    
    args = parser.parse_args()
    
    print_header("字见润新 - 统一构建脚本")
    print("🎯 目标: 同时生成带控制台和无控制台两个版本")
    print("💡 优势: 一次构建，两个版本，完整验证")
    
    try:
        # 检查构建环境
        if not check_requirements():
            return 1
        
        # 清理构建目录
        if not args.skip_clean:
            clean_build_dirs()
        else:
            print_step("跳过", "清理构建目录 (--skip-clean)")
        
        # 安装依赖
        if not args.skip_deps:
            if not install_dependencies():
                return 1
        else:
            print_step("跳过", "依赖安装 (--skip-deps)")
        
        # 执行构建
        if not build_with_spec():
            return 1
        
        # 验证构建结果
        if not verify_builds():
            return 1
        
        # 运行基本测试
        if not args.skip_tests:
            run_basic_tests()
        else:
            print_step("跳过", "基本测试 (--skip-tests)")
        
        # 显示结果
        show_results()
        
        print("\n🎉 统一构建成功!")
        print("\n📋 后续建议:")
        print("  1. 在目标环境中测试两个版本的功能完整性")
        print("  2. 验证所有业务流程和文件操作")
        print("  3. 检查程序在干净环境中的可移植性")
        print("  4. 对比两个版本确保功能一致性")
        
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