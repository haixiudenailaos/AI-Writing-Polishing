"""
知识库引用文件修复脚本

这个脚本用于修复已创建的知识库引用文件，添加缺失的kb_type字段。
运行此脚本可以让已有的知识库在UI中正确显示。

使用方法：
    python fix_existing_knowledge_bases.py
"""

import json
from pathlib import Path


def fix_knowledge_base_references():
    """修复知识库引用文件"""
    storage_dir = Path("app_data/knowledge_bases")
    
    if not storage_dir.exists():
        print("知识库存储目录不存在，无需修复")
        return
    
    fixed_count = 0
    skipped_count = 0
    error_count = 0
    
    print(f"开始扫描知识库引用文件: {storage_dir}")
    print("-" * 60)
    
    for kb_file in storage_dir.glob("*.json"):
        try:
            # 读取文件
            with open(kb_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查是否是引用文件
            if "kb_file_path" not in data:
                print(f"跳过: {kb_file.name} (不是引用文件)")
                skipped_count += 1
                continue
            
            # 检查是否已经有kb_type字段
            if "kb_type" in data:
                print(f"跳过: {kb_file.name} (已有kb_type字段: {data['kb_type']})")
                skipped_count += 1
                continue
            
            # 尝试从实际知识库文件读取kb_type
            kb_file_path = Path(data['kb_file_path'])
            if not kb_file_path.exists():
                print(f"警告: {kb_file.name} - 实际知识库文件不存在: {kb_file_path}")
                error_count += 1
                continue
            
            try:
                with open(kb_file_path, 'r', encoding='utf-8') as f:
                    kb_data = json.load(f)
                
                # 获取kb_type（默认为history以保持兼容性）
                kb_type = kb_data.get('kb_type', 'history')
                
                # 添加kb_type到引用文件
                data['kb_type'] = kb_type
                
                # 保存更新后的引用文件
                with open(kb_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                print(f"✓ 修复: {kb_file.name}")
                print(f"  - 知识库名称: {data.get('name', '未知')}")
                print(f"  - 添加kb_type: {kb_type}")
                fixed_count += 1
                
            except Exception as e:
                print(f"错误: {kb_file.name} - 读取实际知识库文件失败: {e}")
                error_count += 1
                
        except Exception as e:
            print(f"错误: {kb_file.name} - {e}")
            error_count += 1
    
    print("-" * 60)
    print(f"修复完成:")
    print(f"  - 已修复: {fixed_count} 个")
    print(f"  - 已跳过: {skipped_count} 个")
    print(f"  - 失败: {error_count} 个")
    
    if fixed_count > 0:
        print("\n✓ 知识库引用文件已修复，现在可以在UI中正确显示了！")
    else:
        print("\n无需修复或没有找到需要修复的文件。")


def scan_workspace_knowledge_bases(workspace_dir: str = None):
    """扫描工作目录中的知识库文件"""
    if not workspace_dir:
        print("\n提示: 如果你的知识库文件保存在工作目录中（以.knowledge_base_开头的JSON文件），")
        print("      应用程序现在会自动扫描并显示它们。")
        return
    
    workspace_path = Path(workspace_dir)
    if not workspace_path.exists():
        print(f"\n工作目录不存在: {workspace_dir}")
        return
    
    print(f"\n扫描工作目录中的知识库文件: {workspace_dir}")
    print("-" * 60)
    
    kb_files = list(workspace_path.glob(".knowledge_base_*.json"))
    
    if not kb_files:
        print("未找到知识库文件")
        return
    
    for kb_file in kb_files:
        try:
            with open(kb_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            kb_name = data.get('name', '未知')
            kb_type = data.get('kb_type', 'history')
            doc_count = len(data.get('documents', []))
            
            type_label = {
                'history': '历史文本',
                'setting': '大纲/人设'
            }.get(kb_type, kb_type)
            
            print(f"✓ 发现知识库: {kb_name}")
            print(f"  - 类型: {type_label}")
            print(f"  - 文档数: {doc_count}")
            print(f"  - 文件: {kb_file.name}")
            
        except Exception as e:
            print(f"错误: 读取 {kb_file.name} 失败 - {e}")
    
    print("-" * 60)
    print(f"共发现 {len(kb_files)} 个知识库文件")


if __name__ == "__main__":
    print("=" * 60)
    print("知识库引用文件修复脚本")
    print("=" * 60)
    
    # 修复默认存储目录中的引用文件
    fix_knowledge_base_references()
    
    # 提示用户关于工作目录扫描
    scan_workspace_knowledge_bases()
    
    print("\n" + "=" * 60)
    print("说明：")
    print("1. 应用程序现在会自动扫描工作目录中的知识库文件")
    print("2. 知识库类型（历史/大纲/人设）会正确识别和显示")
    print("3. 如需查看工作目录中的知识库，请在应用中打开对应文件夹")
    print("=" * 60)



