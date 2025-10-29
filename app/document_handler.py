"""
文档处理器
支持读写多种格式文档（txt, docx等）
"""

import os
import zipfile
from typing import Optional
from pathlib import Path
from xml.sax.saxutils import escape


class DocumentHandler:
    """文档处理器 - 支持多种格式"""
    
    @staticmethod
    def read_document(file_path: str) -> Optional[str]:
        """读取文档内容
        
        Args:
            file_path: 文件路径
        
        Returns:
            文档内容文本，失败返回None
        """
        try:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.txt':
                return DocumentHandler._read_txt(file_path)
            elif file_ext == '.docx':
                return DocumentHandler._read_docx(file_path)
            elif file_ext == '.doc':
                # .doc格式需要特殊处理，暂不支持
                raise ValueError("暂不支持 .doc 格式，请转换为 .docx 格式")
            else:
                # 默认当作文本文件读取
                return DocumentHandler._read_txt(file_path)
        
        except Exception as e:
            print(f"[ERROR] 读取文档失败: {e}")
            return None
    
    @staticmethod
    def write_document(file_path: str, content: str) -> bool:
        """写入文档内容
        
        Args:
            file_path: 文件路径
            content: 要写入的内容
        
        Returns:
            成功返回True，失败返回False
        """
        try:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.txt':
                return DocumentHandler._write_txt(file_path, content)
            elif file_ext == '.docx':
                return DocumentHandler._write_docx(file_path, content)
            else:
                # 默认当作文本文件写入
                return DocumentHandler._write_txt(file_path, content)
        
        except Exception as e:
            print(f"[ERROR] 写入文档失败: {e}")
            return False
    
    @staticmethod
    def _read_txt(file_path: str) -> str:
        """读取文本文件"""
        # 尝试多种编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        
        # 如果所有编码都失败，使用二进制模式读取并尝试解码
        with open(file_path, 'rb') as f:
            data = f.read()
            # 尝试检测编码
            try:
                return data.decode('utf-8')
            except:
                return data.decode('gbk', errors='ignore')
    
    @staticmethod
    def _write_txt(file_path: str, content: str) -> bool:
        """写入文本文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"[ERROR] 写入txt文件失败: {e}")
            return False
    
    @staticmethod
    def _read_docx(file_path: str) -> str:
        """读取Word文档（.docx）"""
        try:
            from docx import Document
            
            doc = Document(file_path)
            
            # 提取所有段落文本
            paragraphs = []
            for para in doc.paragraphs:
                paragraphs.append(para.text)
            
            # 用换行符连接
            return '\n'.join(paragraphs)
        
        except ImportError:
            raise ImportError("需要安装 python-docx: pip install python-docx")
        except Exception as e:
            print(f"[ERROR] 读取docx文件失败: {e}")
            raise
    
    @staticmethod
    def _write_docx(file_path: str, content: str) -> bool:
        """写入Word文档（.docx）"""
        try:
            from docx import Document
            from docx.shared import Pt, RGBColor
            from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
            
            doc = Document()
            
            # 设置默认字体和样式
            style = doc.styles['Normal']
            font = style.font
            font.name = '宋体'
            font.size = Pt(12)
            
            # 按段落分割内容
            paragraphs = content.split('\n')
            
            for para_text in paragraphs:
                if para_text.strip():  # 跳过空行
                    para = doc.add_paragraph(para_text)
                    # 设置段落格式
                    para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                    para_format = para.paragraph_format
                    para_format.line_spacing = 1.5  # 1.5倍行距
                else:
                    # 空行也添加，保持格式
                    doc.add_paragraph()
            
            # 保存文档
            doc.save(file_path)
            return True
        
        except ImportError:
            raise ImportError("需要安装 python-docx: pip install python-docx")
        except Exception as e:
            # 当 python-docx 的默认模板缺失时，尝试使用最小可用的 docx 结构写入
            err_msg = str(e)
            if "Package not found" in err_msg and "templates" in err_msg:
                try:
                    return DocumentHandler._write_docx_minimal_zip(file_path, content)
                except Exception as zip_e:
                    print(f"[ERROR] 通过最小ZIP写入docx仍失败: {zip_e}")
                    return False
            
            print(f"[ERROR] 写入docx文件失败: {e}")
            return False

    @staticmethod
    def _write_docx_minimal_zip(file_path: str, content: str) -> bool:
        """不依赖 python-docx 默认模板，使用最小Office Open XML结构写入docx。
        仅保留基本段落，适用于应急回退，尽量小改动保证功能可用。
        """
        # 基本的Content_Types定义
        content_types_xml = (
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
        )

        # 包级关系，指向word/document.xml
        rels_xml = (
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
        )

        # 将文本按段落输出为w:p/w:r/w:t结构
        paragraphs_xml_parts = []
        for line in content.split("\n"):
            if line.strip():
                paragraphs_xml_parts.append(
                    f"<w:p><w:r><w:t>{escape(line)}</w:t></w:r></w:p>"
                )
            else:
                paragraphs_xml_parts.append("<w:p/>")

        paragraphs_xml = "\n    ".join(paragraphs_xml_parts)

        # 最小文档结构
        document_xml = (
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {paragraphs_xml}
    <w:sectPr/>
  </w:body>
</w:document>
"""
        )

        # 写入zip为docx
        # 确保输出目录存在
        out_dir = os.path.dirname(file_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types_xml)
            zf.writestr("_rels/.rels", rels_xml)
            zf.writestr("word/document.xml", document_xml)

        return True
    
    @staticmethod
    def create_new_document(file_path: str, template_content: str = "") -> bool:
        """创建新文档
        
        Args:
            file_path: 文件路径
            template_content: 模板内容（可选）
        
        Returns:
            成功返回True，失败返回False
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 如果没有模板内容，使用默认模板
            if not template_content:
                template_content = "# 新建文档\n\n开始您的创作..."
            
            return DocumentHandler.write_document(file_path, template_content)
        
        except Exception as e:
            print(f"[ERROR] 创建新文档失败: {e}")
            return False
    
    @staticmethod
    def get_supported_formats() -> list:
        """获取支持的文件格式"""
        return ['.txt', '.docx']
    
    @staticmethod
    def is_supported(file_path: str) -> bool:
        """检查文件格式是否支持"""
        ext = Path(file_path).suffix.lower()
        return ext in DocumentHandler.get_supported_formats()

