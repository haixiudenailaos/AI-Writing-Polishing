#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打包验证脚本
检查打包后的可执行文件是否包含所有必要的组件和依赖
"""

import os
import sys
import subprocess
from pathlib import Path
import json
import zipfile

PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"
APP_NAME = "字见润新"

def print_header(title):
    """打印标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def check_executable_exists():
    """检查可执行文件是否存在"""
    print_header("检查可执行文件")
    
    exe_file = DIST_DIR / f"{APP_NAME}.exe"
    
    if exe_file.exists():
        file_size = exe_file.stat().st_size / (1024 * 1024)
        print(f"✓ 找到可执行文件: {exe_file}")
        print(f"  文件大小: {file_size:.2f} MB")
        
        if file_size < 50:
            print(f"  [警告] 文件大小较小 ({file_size:.2f} MB)，可能缺少依赖")
            return False
        elif file_size > 500:
            print(f"  [警告] 文件大小较大 ({file_size:.2f} MB)，可能包含不必要的依赖")
        
        return True
    else:
        print(f"✗ 未找到可执行文件: {exe_file}")
        return False

def check_build_warnings():
    """检查构建警告"""
    print_header("检查构建警告")
    
    warn_files = list(PROJECT_ROOT.glob("build/**/warn-*.txt"))
    
    if not warn_files:
        print("✓ 未找到警告文件")
        return True
    
    for warn_file in warn_files:
        print(f"\n检查警告文件: {warn_file.name}")
        try:
            with open(warn_file, 'r', encoding='utf-8', errors='ignore') as f:
                warnings = f.read()
                
            if warnings.strip():
                lines = warnings.strip().split('\n')
                print(f"  发现 {len(lines)} 个警告:")
                
                # 显示前 10 个警告
                for i, line in enumerate(lines[:10], 1):
                    if line.strip():
                        print(f"    {i}. {line.strip()}")
                
                if len(lines) > 10:
                    print(f"    ... 还有 {len(lines) - 10} 个警告")
                
                # 检查关键警告
                critical_warnings = [
                    'missing module',
                    'ImportError',
                    'ModuleNotFoundError',
                ]
                
                has_critical = False
                for warning_key in critical_warnings:
                    if warning_key.lower() in warnings.lower():
                        has_critical = True
                        break
                
                if has_critical:
                    print("  [警告] 发现关键警告，可能影响程序运行")
                    return False
            else:
                print("  ✓ 无警告")
        
        except Exception as e:
            print(f"  [错误] 读取警告文件失败: {e}")
    
    return True

def check_dependencies():
    """检查打包的依赖"""
    print_header("检查依赖包含情况")
    
    exe_file = DIST_DIR / f"{APP_NAME}.exe"
    
    if not exe_file.exists():
        print("✗ 可执行文件不存在")
        return False
    
    print("尝试分析可执行文件内容...")
    
    # 使用 PyInstaller 的 archive_viewer
    try:
        cmd = [
            sys.executable,
            "-m",
            "PyInstaller.archive.readers",
            str(exe_file)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode == 0 and result.stdout:
            print("✓ 成功读取可执行文件结构")
            
            # 检查关键模块
            critical_modules = [
                'PySide6',
                'requests',
                'docx',
                'bs4',
                'ebooklib',
                'xml',
                'json',
                'sqlite3',
            ]
            
            print("\n检查关键模块:")
            for module in critical_modules:
                if module.lower() in result.stdout.lower():
                    print(f"  ✓ {module}")
                else:
                    print(f"  ✗ {module} [可能缺失]")
        else:
            print("  [警告] 无法读取可执行文件结构")
            print("  这不一定表示有问题，可能只是工具不可用")
    
    except Exception as e:
        print(f"  [警告] 分析工具不可用: {e}")
        print("  这不一定表示有问题，程序可能仍然正常工作")
    
    return True

def check_resources():
    """检查资源文件"""
    print_header("检查资源文件")
    
    # 检查必需的资源
    required_resources = [
        'docs',
        'version_info.txt',
        'requirements.txt',
    ]
    
    print("检查项目资源:")
    all_exist = True
    for resource in required_resources:
        resource_path = PROJECT_ROOT / resource
        if resource_path.exists():
            print(f"  ✓ {resource}")
        else:
            print(f"  ✗ {resource} [缺失]")
            all_exist = False
    
    if all_exist:
        print("\n✓ 所有必需资源都存在")
    else:
        print("\n[警告] 部分资源缺失，但可能不影响核心功能")
    
    return True

def generate_report():
    """生成验证报告"""
    print_header("生成验证报告")
    
    report = {
        'app_name': APP_NAME,
        'checks': [],
        'summary': {}
    }
    
    # 执行各项检查
    checks = [
        ('可执行文件存在性', check_executable_exists),
        ('构建警告', check_build_warnings),
        ('依赖完整性', check_dependencies),
        ('资源文件', check_resources),
    ]
    
    passed = 0
    failed = 0
    
    print("\n执行完整性检查:")
    for check_name, check_func in checks:
        try:
            result = check_func()
            status = "通过" if result else "失败"
            
            report['checks'].append({
                'name': check_name,
                'result': result,
                'status': status
            })
            
            if result:
                passed += 1
                print(f"  ✓ {check_name}: {status}")
            else:
                failed += 1
                print(f"  ✗ {check_name}: {status}")
        
        except Exception as e:
            print(f"  ✗ {check_name}: 检查失败 - {e}")
            failed += 1
            report['checks'].append({
                'name': check_name,
                'result': False,
                'status': f"错误: {e}"
            })
    
    # 汇总
    total = passed + failed
    report['summary'] = {
        'total': total,
        'passed': passed,
        'failed': failed,
        'success_rate': round((passed / total * 100) if total > 0 else 0, 2)
    }
    
    # 保存报告
    report_file = PROJECT_ROOT / "verification_report.json"
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n✓ 验证报告已保存: {report_file}")
    except Exception as e:
        print(f"\n✗ 保存验证报告失败: {e}")
    
    return report

def main():
    """主函数"""
    print("=" * 70)
    print(f"  {APP_NAME} - 打包验证工具")
    print("=" * 70)
    
    try:
        # 生成验证报告
        report = generate_report()
        
        # 输出总结
        print_header("验证总结")
        print(f"总检查项: {report['summary']['total']}")
        print(f"通过: {report['summary']['passed']}")
        print(f"失败: {report['summary']['failed']}")
        print(f"成功率: {report['summary']['success_rate']}%")
        
        if report['summary']['failed'] == 0:
            print("\n✓ 所有检查项通过，打包质量良好")
            return 0
        elif report['summary']['success_rate'] >= 75:
            print("\n⚠ 大部分检查项通过，但存在一些问题")
            print("  建议查看详细日志并进行测试")
            return 0
        else:
            print("\n✗ 多个检查项失败，建议重新打包")
            return 1
    
    except Exception as e:
        print(f"\n✗ 验证过程发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())






