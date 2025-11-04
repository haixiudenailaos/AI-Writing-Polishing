"""
文件格式转换工具
支持批量转换各种文档格式
"""

import os
from typing import List, Tuple, Optional
from pathlib import Path
from app.document_handler import DocumentHandler


class FormatConverter:
    """文件格式转换器"""
    
    @staticmethod
    def convert_file(
        input_file: str,
        output_file: str,
        progress_callback: Optional[callable] = None
    ) -> Tuple[bool, str]:
        """
        转换单个文件格式
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径
            progress_callback: 进度回调函数
            
        Returns:
            (是否成功, 消息)
        """
        try:
            # 检查输入文件是否存在
            if not os.path.exists(input_file):
                return False, f"输入文件不存在: {input_file}"
            
            # 检查输入格式是否支持
            if not DocumentHandler.is_supported(input_file):
                input_ext = Path(input_file).suffix
                return False, f"不支持的输入格式: {input_ext}"
            
            # 检查输出格式是否支持
            if not DocumentHandler.is_supported(output_file):
                output_ext = Path(output_file).suffix
                return False, f"不支持的输出格式: {output_ext}"
            
            if progress_callback:
                progress_callback(f"正在读取: {Path(input_file).name}")
            
            # 读取输入文件
            content = DocumentHandler.read_document(input_file)
            if content is None:
                return False, f"无法读取文件: {input_file}"
            
            if progress_callback:
                progress_callback(f"正在转换...")
            
            # 写入输出文件
            success = DocumentHandler.write_document(output_file, content)
            if not success:
                return False, f"无法写入文件: {output_file}"
            
            if progress_callback:
                progress_callback(f"转换完成: {Path(output_file).name}")
            
            input_desc = DocumentHandler.get_format_description(Path(input_file).suffix)
            output_desc = DocumentHandler.get_format_description(Path(output_file).suffix)
            
            return True, f"成功将 {input_desc} 转换为 {output_desc}"
            
        except Exception as e:
            return False, f"转换失败: {str(e)}"
    
    @staticmethod
    def batch_convert(
        input_files: List[str],
        output_dir: str,
        output_format: str,
        progress_callback: Optional[callable] = None
    ) -> Tuple[int, int, List[str]]:
        """
        批量转换文件格式
        
        Args:
            input_files: 输入文件列表
            output_dir: 输出目录
            output_format: 输出格式（如'.pdf'）
            progress_callback: 进度回调函数 (current, total, message)
            
        Returns:
            (成功数量, 失败数量, 错误消息列表)
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        success_count = 0
        fail_count = 0
        errors = []
        
        total = len(input_files)
        
        for i, input_file in enumerate(input_files):
            try:
                # 生成输出文件名
                input_name = Path(input_file).stem
                output_file = os.path.join(output_dir, f"{input_name}{output_format}")
                
                if progress_callback:
                    progress_callback(i + 1, total, f"正在转换: {Path(input_file).name}")
                
                # 转换文件
                success, message = FormatConverter.convert_file(input_file, output_file)
                
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(f"{Path(input_file).name}: {message}")
                    
            except Exception as e:
                fail_count += 1
                errors.append(f"{Path(input_file).name}: {str(e)}")
        
        return success_count, fail_count, errors
    
    @staticmethod
    def detect_format(file_path: str) -> Tuple[bool, str]:
        """
        检测文件格式是否支持
        
        Args:
            file_path: 文件路径
            
        Returns:
            (是否支持, 格式描述)
        """
        ext = Path(file_path).suffix.lower()
        
        if DocumentHandler.is_supported(file_path):
            desc = DocumentHandler.get_format_description(ext)
            return True, desc
        else:
            return False, f"不支持的格式: {ext}"
    
    @staticmethod
    def suggest_conversion(file_path: str) -> Optional[str]:
        """
        为不支持的文件建议转换格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            建议的转换格式（如'.docx'），如果已支持则返回None
        """
        ext = Path(file_path).suffix.lower()
        
        # 如果已经支持，无需转换
        if DocumentHandler.is_supported(file_path):
            return None
        
        # 为不支持的格式提供建议
        suggestions = {
            '.pages': '.docx',  # Apple Pages
            '.numbers': '.txt', # Apple Numbers
            '.key': '.pdf',     # Apple Keynote
            '.wps': '.docx',    # WPS文档
            '.et': '.txt',      # WPS表格
            '.dps': '.pdf',     # WPS演示
            '.xls': '.txt',     # Excel
            '.xlsx': '.txt',    # Excel
            '.ppt': '.pdf',     # PowerPoint
            '.pptx': '.pdf',    # PowerPoint
        }
        
        return suggestions.get(ext, '.txt')  # 默认建议转txt
    
    @staticmethod
    def get_conversion_map() -> dict:
        """
        获取支持的转换格式映射
        
        Returns:
            {输入格式: [可转换的输出格式列表]}
        """
        # 所有支持的格式都可以互相转换
        supported_formats = DocumentHandler.get_supported_formats()
        
        conversion_map = {}
        for fmt in supported_formats:
            # 每个格式可以转换为其他所有格式
            conversion_map[fmt] = [f for f in supported_formats if f != fmt]
        
        return conversion_map

