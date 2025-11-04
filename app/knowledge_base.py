"""
知识库管理模块
负责文件扫描、向量化处理和存储
"""

import os
import json
import hashlib
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
import requests


@dataclass
class VectorDocument:
    """向量化文档"""
    id: str
    file_path: str
    content: str
    vector: List[float]
    metadata: Dict[str, Any]
    created_at: str


@dataclass
class KnowledgeBase:
    """知识库"""
    id: str
    name: str
    root_path: str
    documents: List[VectorDocument]
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]
    polish_style_id: Optional[str] = None  # 关联的润色风格提示词ID
    prediction_style_id: Optional[str] = None  # 关联的预测提示词ID
    kb_type: str = "history"  # 知识库类型："history"(历史文本) 或 "setting"(大纲/人设)


class VectorEmbeddingClient:
    """阿里云向量化客户端
    
    支持的模型：
    - text-embedding-v4: 阿里云通义千问嵌入模型，支持多语言，输出维度1024
    
    支持两种API调用方式：
    1. 兼容OpenAI格式（默认）：https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
    2. 原生DashScope API：https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding
    
    参考文档：
    - https://help.aliyun.com/zh/model-studio/developer-reference/text-embedding-v3-api
    """
    
    def __init__(self, api_key: str, model: str = "text-embedding-v4", use_native_api: bool = False):
        """
        初始化向量化客户端
        
        Args:
            api_key: 阿里云API密钥（DashScope API Key）
            model: 向量模型名称，默认 text-embedding-v4
            use_native_api: 是否使用原生DashScope API（默认使用兼容OpenAI格式）
        """
        self.api_key = api_key
        self.model = model
        self.use_native_api = use_native_api
        
        # 根据选择设置endpoint
        if use_native_api:
            self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
        else:
            # 兼容OpenAI格式的endpoint（推荐，更通用）
            self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
    
    def embed_text(self, text: str) -> List[float]:
        """
        对文本进行向量化
        
        Args:
            text: 待向量化的文本
            
        Returns:
            向量列表（1024维）
            
        Raises:
            ValueError: 文本为空
            RuntimeError: API调用失败
        """
        if not text or not text.strip():
            raise ValueError("文本内容不能为空")
        
        # 限制文本长度，避免超出模型限制（text-embedding-v4支持最长2048 tokens）
        if len(text) > 6000:  # 粗略估计，约2000个中文字符
            text = text[:6000]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 根据API类型构造不同的payload
        if self.use_native_api:
            # 原生DashScope API格式
            payload = {
                "model": self.model,
                "input": {
                    "texts": [text]
                }
            }
        else:
            # 兼容OpenAI格式
            payload = {
                "model": self.model,
                "input": text,
                "encoding_format": "float"
            }
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            # 详细的错误处理
            if response.status_code == 401:
                raise RuntimeError("API密钥认证失败，请检查阿里云DashScope API密钥是否正确")
            
            if response.status_code == 400:
                error_detail = response.json().get("message", response.text)
                raise RuntimeError(f"请求参数错误: {error_detail}")
            
            if response.status_code == 429:
                raise RuntimeError("API调用频率超限，请稍后重试")
            
            if not response.ok:
                raise RuntimeError(f"向量化请求失败: HTTP {response.status_code} - {response.text}")
            
            data = response.json()
            
            # 根据API类型解析不同的响应格式
            if self.use_native_api:
                # 原生API格式: {"output": {"embeddings": [{"embedding": [...], "text_index": 0}]}}
                if "output" not in data or "embeddings" not in data["output"]:
                    raise RuntimeError(f"向量化响应格式错误: {data}")
                
                embeddings = data["output"]["embeddings"]
                if not embeddings or len(embeddings) == 0:
                    raise RuntimeError("向量化结果为空")
                
                embedding = embeddings[0].get("embedding")
            else:
                # 兼容OpenAI格式: {"data": [{"embedding": [...]}]}
                if "data" not in data or not data["data"]:
                    raise RuntimeError(f"向量化响应格式错误: {data}")
                
                embedding = data["data"][0].get("embedding")
            
            if not embedding:
                raise RuntimeError("向量化结果为空")
            
            # 验证向量维度（text-embedding-v4应该是1024维）
            if len(embedding) != 1024:
                print(f"[WARN] 向量维度异常: 预期1024维，实际{len(embedding)}维")
            
            return embedding
            
        except requests.Timeout:
            raise RuntimeError("网络请求超时，请检查网络连接")
        except requests.RequestException as e:
            raise RuntimeError(f"网络请求失败: {str(e)}")
    
    def embed_batch(self, texts: List[str], 
                    progress_callback: Optional[Callable[[int, int, str], None]] = None,
                    batch_size: int = 10) -> List[List[float]]:
        """
        批量向量化文本（支持批量API调用以提高效率）
        
        Args:
            texts: 文本列表
            progress_callback: 进度回调函数 (current, total, message)
            batch_size: 每批处理的文本数量，阿里云API限制最大10个
            
        Returns:
            向量列表
        """
        vectors = []
        total = len(texts)
        
        # 按批次处理
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch_texts = texts[batch_start:batch_end]
            
            try:
                if progress_callback:
                    progress_callback(
                        batch_end, total, 
                        f"正在处理第 {batch_start + 1}-{batch_end}/{total} 个文本..."
                    )
                
                # 批量调用API
                batch_vectors = self._embed_batch_api(batch_texts)
                vectors.extend(batch_vectors)
                
            except Exception as e:
                if progress_callback:
                    progress_callback(batch_end, total, f"批次处理失败: {str(e)}，尝试逐个处理...")
                
                # 失败时逐个处理该批次
                for text in batch_texts:
                    try:
                        vector = self.embed_text(text)
                        vectors.append(vector)
                    except Exception as e2:
                        print(f"[ERROR] 单个文本向量化失败: {str(e2)}")
                        vectors.append([])  # 失败时添加空向量
        
        return vectors
    
    def _embed_batch_api(self, texts: List[str]) -> List[List[float]]:
        """
        批量API调用（text-embedding-v4支持批量输入）
        
        Args:
            texts: 文本列表
            
        Returns:
            向量列表
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 根据API类型构造不同的payload
        if self.use_native_api:
            # 原生DashScope API格式
            payload = {
                "model": self.model,
                "input": {
                    "texts": texts
                }
            }
        else:
            # 兼容OpenAI格式（支持列表输入）
            payload = {
                "model": self.model,
                "input": texts,
                "encoding_format": "float"
            }
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=60  # 批量请求需要更长超时
            )
            
            if not response.ok:
                raise RuntimeError(f"批量向量化失败: {response.status_code} {response.text}")
            
            data = response.json()
            
            # 根据API类型解析不同的响应格式
            vectors = []
            if self.use_native_api:
                # 原生API格式
                if "output" not in data or "embeddings" not in data["output"]:
                    raise RuntimeError("响应格式错误")
                
                embeddings = data["output"]["embeddings"]
                # 按text_index排序
                embeddings.sort(key=lambda x: x.get("text_index", 0))
                for item in embeddings:
                    embedding = item.get("embedding")
                    vectors.append(embedding if embedding else [])
            else:
                # 兼容OpenAI格式
                if "data" not in data:
                    raise RuntimeError("响应格式错误")
                
                for item in data["data"]:
                    embedding = item.get("embedding")
                    vectors.append(embedding if embedding else [])
            
            return vectors
            
        except Exception as e:
            raise RuntimeError(f"批量API调用失败: {str(e)}")


class RerankClient:
    """阿里云重排序客户端
    
    用于对检索结果进行重新排序，提升相关性
    
    支持的模型：
    - gte-rerank-v2: 通用文本重排序模型
    - qwen3-rerank: 通义千问3重排序模型
    
    参考文档：
    - https://help.aliyun.com/zh/model-studio/developer-reference/rerank-api
    """
    
    def __init__(self, api_key: str, model: str = "gte-rerank-v2"):
        """
        初始化重排序客户端
        
        Args:
            api_key: 阿里云API密钥（DashScope API Key）
            model: 重排序模型名称
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    
    def rerank(self, query: str, documents: List[str], top_n: int = 5) -> List[Dict[str, Any]]:
        """
        对文档列表进行重排序
        
        Args:
            query: 查询文本
            documents: 候选文档列表
            top_n: 返回前N个最相关的文档
            
        Returns:
            重排序后的文档列表，每个元素包含 {index, document, relevance_score}
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "input": {
                "query": query,
                "documents": documents
            },
            "parameters": {
                "return_documents": True,
                "top_n": min(top_n, len(documents))
            }
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 401:
                raise RuntimeError("API密钥认证失败")
            
            if not response.ok:
                raise RuntimeError(f"重排序请求失败: {response.status_code} {response.text}")
            
            data = response.json()
            
            # 解析响应
            if "output" not in data or "results" not in data["output"]:
                raise RuntimeError("重排序响应格式错误")
            
            results = data["output"]["results"]
            
            # 构造返回结果
            reranked = []
            for item in results:
                reranked.append({
                    "index": item.get("index"),
                    "document": item.get("document"),
                    "relevance_score": item.get("relevance_score", 0.0)
                })
            
            return reranked
            
        except requests.RequestException as e:
            raise RuntimeError(f"重排序网络请求失败: {str(e)}")


class KnowledgeBaseManager:
    """知识库管理器"""
    
    SUPPORTED_EXTENSIONS = {
        '.txt',      # 纯文本
        '.md',       # Markdown
        '.markdown', # Markdown
        '.docx',     # Word新格式
        '.doc',      # Word旧格式
        '.pdf',      # PDF文档
        '.rtf',      # RTF富文本
        '.odt',      # OpenDocument
        '.html',     # HTML
        '.htm',      # HTML
        '.epub'      # ePub电子书
    }
    
    def __init__(self, storage_dir: str = "app_data/knowledge_bases"):
        """
        初始化知识库管理器
        
        Args:
            storage_dir: 知识库存储目录
        """
        # 确保使用绝对路径，避免路径问题
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.embedding_client: Optional[VectorEmbeddingClient] = None
        
        # BM25索引缓存（知识库ID -> 索引数据）
        self._bm25_index_cache: Dict[str, Dict[str, Any]] = {}
        
        # 查询向量缓存（查询文本hash -> 向量）
        self._query_vector_cache: Dict[str, List[float]] = {}
    
    def set_embedding_client(self, api_key: str, model: str = "text-embedding-v4"):
        """设置向量化客户端"""
        self.embedding_client = VectorEmbeddingClient(api_key, model)
    
    def test_embedding_connection(self) -> tuple[bool, str]:
        """
        测试向量化API连接
        
        Returns:
            (是否成功, 消息)
        """
        if not self.embedding_client:
            return False, "未配置向量化客户端"
        
        try:
            # 使用简单的测试文本
            test_text = "测试向量化API连接"
            vector = self.embedding_client.embed_text(test_text)
            
            if vector and len(vector) == 1024:
                return True, f"连接成功！向量维度: {len(vector)}"
            else:
                return False, f"向量维度异常: {len(vector) if vector else 0}"
                
        except Exception as e:
            return False, f"连接失败: {str(e)}"
    
    def scan_folder(self, folder_path: str, 
                    progress_callback: Optional[Callable[[int, int, str], None]] = None) -> List[str]:
        """
        扫描文件夹，查找所有支持的文件
        
        Args:
            folder_path: 文件夹路径
            progress_callback: 进度回调函数
            
        Returns:
            文件路径列表
        """
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            raise ValueError(f"无效的文件夹路径: {folder_path}")
        
        files = []
        
        # 递归扫描
        for root, _, filenames in os.walk(folder):
            for filename in filenames:
                file_path = Path(root) / filename
                if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    files.append(str(file_path))
                    
                    if progress_callback:
                        progress_callback(
                            len(files), 0, 
                            f"已发现 {len(files)} 个文件..."
                        )
        
        return files
    
    def read_file_content(self, file_path: str) -> Optional[str]:
        """
        读取文件内容（使用统一的DocumentHandler）
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容，如果读取失败或内容无效则返回None
        """
        try:
            # 使用DocumentHandler统一处理所有文件格式
            from app.document_handler import DocumentHandler
            
            content = DocumentHandler.read_document(file_path)
            
            # 验证内容是否有效
            if not content or not content.strip():
                print(f"[WARN] 文件内容为空，跳过: {file_path}")
                return None
            
            # 检查是否为乱码（如果文本中无效字符过多）
            if self._is_garbled_text(content):
                print(f"[WARN] 文件内容疑似乱码，跳过: {file_path}")
                return None
            
            return content
                    
        except ImportError as e:
            print(f"[WARN] 缺少必要的库，无法读取: {file_path} - {e}")
            return None
        except ValueError as e:
            # 处理不支持的格式或转换建议
            print(f"[WARN] {e}")
            return None
        except Exception as e:
            print(f"[WARN] 读取文件失败，跳过: {file_path} - {e}")
            return None
    
    def _is_garbled_text(self, text: str, threshold: float = 0.3) -> bool:
        """
        检查文本是否为乱码
        
        Args:
            text: 待检查的文本
            threshold: 无效字符比例阈值（默认30%）
            
        Returns:
            如果疑似乱码则返回True
        """
        if not text or len(text) < 100:
            return False
        
        # 统计无效字符（非常见字符）
        invalid_count = 0
        sample_size = min(1000, len(text))  # 只检查前1000个字符
        sample_text = text[:sample_size]
        
        for char in sample_text:
            # 检查是否为有效字符（中文、英文、数字、常见标点等）
            code = ord(char)
            is_valid = (
                (0x4e00 <= code <= 0x9fff) or  # 中文
                (0x3000 <= code <= 0x303f) or  # 中文标点
                (0xff00 <= code <= 0xffef) or  # 全角字符
                (0x0020 <= code <= 0x007e) or  # ASCII可见字符
                char in '\n\r\t'                # 常见控制字符
            )
            
            if not is_valid:
                invalid_count += 1
        
        invalid_ratio = invalid_count / sample_size
        return invalid_ratio > threshold
    
    def create_knowledge_base(
        self, 
        name: str, 
        folder_path: str,
        chunk_size: int = 800,  # 增大分块大小以更好利用模型能力
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        error_callback: Optional[Callable[[str], None]] = None,
        generate_prompts: bool = True,  # 是否自动生成提示词
        kb_type: str = "history"  # 知识库类型："history"(历史文本) 或 "setting"(大纲/人设)
    ) -> Optional[KnowledgeBase]:
        """
        创建知识库
        
        Args:
            name: 知识库名称
            folder_path: 源文件夹路径
            chunk_size: 文本分块大小（字符数）
            progress_callback: 进度回调
            error_callback: 错误回调
            
        Returns:
            知识库对象，失败时返回None
        """
        if not self.embedding_client:
            if error_callback:
                error_callback("未配置向量化客户端，请先配置阿里云API密钥")
            return None
        
        try:
            # 1. 扫描文件
            if progress_callback:
                progress_callback(0, 100, "正在扫描文件夹...")
            
            files = self.scan_folder(folder_path, progress_callback)
            
            if not files:
                if error_callback:
                    error_callback("文件夹中没有找到支持的文件")
                return None
            
            # 2. 读取和分块
            if progress_callback:
                progress_callback(10, 100, f"正在读取 {len(files)} 个文件...")
            
            chunks = []
            chunk_metadata = []
            successful_files = 0
            skipped_files = 0
            
            for i, file_path in enumerate(files):
                content = self.read_file_content(file_path)
                
                # 如果文件读取失败或内容无效，跳过该文件
                if content is None:
                    skipped_files += 1
                    if progress_callback:
                        progress = 10 + int((i + 1) / len(files) * 30)
                        progress_callback(
                            progress, 100, 
                            f"已处理 {i + 1}/{len(files)} 个文件（跳过 {skipped_files} 个），生成 {len(chunks)} 个文本块"
                        )
                    continue
                
                # 分块
                file_chunks = self._chunk_text(content, chunk_size)
                
                if file_chunks:  # 只有成功分块的文件才计数
                    successful_files += 1
                    for j, chunk in enumerate(file_chunks):
                        chunks.append(chunk)
                        chunk_metadata.append({
                            'file_path': file_path,
                            'chunk_index': j,
                            'total_chunks': len(file_chunks)
                        })
                
                if progress_callback:
                    progress = 10 + int((i + 1) / len(files) * 30)
                    progress_callback(
                        progress, 100, 
                        f"已处理 {i + 1}/{len(files)} 个文件（成功 {successful_files}，跳过 {skipped_files}），生成 {len(chunks)} 个文本块"
                    )
            
            # 如果所有文件都无法读取，直接返回
            if not chunks:
                if error_callback:
                    error_callback(f"所有文件都无法读取或内容无效（共 {len(files)} 个文件），无法创建知识库")
                return None
            
            # 3. 向量化（使用批量处理提高效率）
            if progress_callback:
                progress_callback(40, 100, "正在进行向量化处理...")
            
            def vector_progress(current, total, message):
                """向量化进度回调"""
                progress = 40 + int(current / total * 50)
                if progress_callback:
                    progress_callback(progress, 100, message)
            
            try:
                # 使用批量API提高效率
                vectors = self.embedding_client.embed_batch(
                    chunks, 
                    progress_callback=vector_progress,
                    batch_size=10  # 每批10个文本块（阿里云API限制）
                )
                
                # 检查向量化结果
                failed_count = sum(1 for v in vectors if not v)
                if failed_count > 0:
                    if error_callback:
                        error_callback(f"有 {failed_count} 个文本块向量化失败，已跳过")
                
            except Exception as e:
                if error_callback:
                    error_callback(f"批量向量化失败: {str(e)}")
                return None
            
            # 4. 创建文档对象（过滤掉向量化失败的文档）
            documents = []
            skipped_count = 0
            for i, (chunk, vector, metadata) in enumerate(zip(chunks, vectors, chunk_metadata)):
                # 跳过向量化失败的文档
                if not vector:
                    skipped_count += 1
                    continue
                
                doc_id = self._generate_doc_id(chunk, metadata['file_path'])
                doc = VectorDocument(
                    id=doc_id,
                    file_path=metadata['file_path'],
                    content=chunk,
                    vector=vector,
                    metadata=metadata,
                    created_at=datetime.now().isoformat()
                )
                documents.append(doc)
            
            if skipped_count > 0:
                print(f"[WARN] 跳过了 {skipped_count} 个向量化失败的文档")
            
            if not documents:
                if error_callback:
                    error_callback("所有文档向量化失败，无法创建知识库")
                return None
            
            # 5. 创建知识库
            kb_id = self._generate_kb_id(name)
            kb = KnowledgeBase(
                id=kb_id,
                name=name,
                root_path=folder_path,
                documents=documents,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                metadata={
                    'total_files': len(files),
                    'successful_files': successful_files,
                    'skipped_files': skipped_files,
                    'total_chunks': len(chunks),
                    'chunk_size': chunk_size
                },
                polish_style_id=None,
                prediction_style_id=None,
                kb_type=kb_type
            )
            
            # 6. 如果启用了提示词生成，则生成并保存提示词ID
            if generate_prompts:
                try:
                    if progress_callback:
                        progress_callback(90, 100, "正在生成定制化提示词...")
                    
                    # 生成提示词（在保存知识库后调用，将在main.py中实现）
                    # 这里只预留接口，实际生成在外部完成
                    pass
                except Exception as e:
                    print(f"[WARN] 提示词生成失败: {e}")
                    # 提示词生成失败不影响知识库创建
            
            # 7. 保存知识库到用户选中的文件夹
            self._save_knowledge_base(kb, folder_path)
            
            if progress_callback:
                completion_msg = f"知识库创建完成！成功处理 {successful_files} 个文件"
                if skipped_files > 0:
                    completion_msg += f"，跳过 {skipped_files} 个无法读取或乱码的文件"
                progress_callback(100, 100, completion_msg)
            
            return kb
            
        except Exception as e:
            if error_callback:
                error_callback(f"创建知识库失败: {str(e)}")
            return None
    
    def create_knowledge_base_from_files(
        self, 
        name: str, 
        file_paths: List[str],
        storage_dir: str,
        chunk_size: int = 800,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        error_callback: Optional[Callable[[str], None]] = None,
        generate_prompts: bool = True,
        kb_type: str = "history"
    ) -> Optional[KnowledgeBase]:
        """
        从文件列表创建知识库（存储到指定目录）
        
        Args:
            name: 知识库名称
            file_paths: 源文件路径列表
            storage_dir: 知识库存储目录（工作目录）
            chunk_size: 文本分块大小（字符数）
            progress_callback: 进度回调
            error_callback: 错误回调
            generate_prompts: 是否自动生成提示词
            kb_type: 知识库类型
            
        Returns:
            知识库对象，失败时返回None
        """
        if not self.embedding_client:
            if error_callback:
                error_callback("未配置向量化客户端，请先配置阿里云API密钥")
            return None
        
        try:
            # 1. 验证文件
            if progress_callback:
                progress_callback(0, 100, f"正在验证 {len(file_paths)} 个文件...")
            
            valid_files = []
            for file_path in file_paths:
                path = Path(file_path)
                if path.exists() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    valid_files.append(file_path)
            
            if not valid_files:
                if error_callback:
                    error_callback("没有找到有效的文件")
                return None
            
            # 2. 读取和分块
            if progress_callback:
                progress_callback(10, 100, f"正在读取 {len(valid_files)} 个文件...")
            
            chunks = []
            chunk_metadata = []
            successful_files = 0
            skipped_files = 0
            
            for i, file_path in enumerate(valid_files):
                content = self.read_file_content(file_path)
                
                if content is None:
                    skipped_files += 1
                    if progress_callback:
                        progress = 10 + int((i + 1) / len(valid_files) * 30)
                        progress_callback(
                            progress, 100, 
                            f"已处理 {i + 1}/{len(valid_files)} 个文件（跳过 {skipped_files} 个），生成 {len(chunks)} 个文本块"
                        )
                    continue
                
                # 分块
                file_chunks = self._chunk_text(content, chunk_size)
                
                if file_chunks:
                    successful_files += 1
                    for j, chunk in enumerate(file_chunks):
                        chunks.append(chunk)
                        chunk_metadata.append({
                            'file_path': file_path,
                            'chunk_index': j,
                            'total_chunks': len(file_chunks)
                        })
                
                if progress_callback:
                    progress = 10 + int((i + 1) / len(valid_files) * 30)
                    progress_callback(
                        progress, 100, 
                        f"已处理 {i + 1}/{len(valid_files)} 个文件（成功 {successful_files}，跳过 {skipped_files}），生成 {len(chunks)} 个文本块"
                    )
            
            if not chunks:
                if error_callback:
                    error_callback(f"所有文件都无法读取或内容无效（共 {len(valid_files)} 个文件），无法创建知识库")
                return None
            
            # 3. 向量化
            if progress_callback:
                progress_callback(40, 100, "正在进行向量化处理...")
            
            def vector_progress(current, total, message):
                progress = 40 + int(current / total * 50)
                if progress_callback:
                    progress_callback(progress, 100, message)
            
            try:
                vectors = self.embedding_client.embed_batch(
                    chunks, 
                    progress_callback=vector_progress,
                    batch_size=10
                )
                
                failed_count = sum(1 for v in vectors if not v)
                if failed_count > 0:
                    if error_callback:
                        error_callback(f"有 {failed_count} 个文本块向量化失败，已跳过")
                
            except Exception as e:
                if error_callback:
                    error_callback(f"批量向量化失败: {str(e)}")
                return None
            
            # 4. 创建文档对象
            documents = []
            skipped_count = 0
            for i, (chunk, vector, metadata) in enumerate(zip(chunks, vectors, chunk_metadata)):
                if not vector:
                    skipped_count += 1
                    continue
                
                doc_id = self._generate_doc_id(chunk, metadata['file_path'])
                doc = VectorDocument(
                    id=doc_id,
                    file_path=metadata['file_path'],
                    content=chunk,
                    vector=vector,
                    metadata=metadata,
                    created_at=datetime.now().isoformat()
                )
                documents.append(doc)
            
            if skipped_count > 0:
                print(f"[WARN] 跳过了 {skipped_count} 个向量化失败的文档")
            
            if not documents:
                if error_callback:
                    error_callback("所有文档向量化失败，无法创建知识库")
                return None
            
            # 5. 创建知识库
            kb_id = self._generate_kb_id(name)
            kb = KnowledgeBase(
                id=kb_id,
                name=name,
                root_path=storage_dir,  # 存储目录设为工作目录
                documents=documents,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                metadata={
                    'total_files': len(valid_files),
                    'successful_files': successful_files,
                    'skipped_files': skipped_files,
                    'total_chunks': len(chunks),
                    'chunk_size': chunk_size,
                    'source_files': [str(Path(f).name) for f in valid_files]  # 记录源文件名
                },
                polish_style_id=None,
                prediction_style_id=None,
                kb_type=kb_type
            )
            
            # 6. 保存知识库到工作目录
            self._save_knowledge_base(kb, storage_dir)
            
            if progress_callback:
                completion_msg = f"知识库创建完成！成功处理 {successful_files} 个文件"
                if skipped_files > 0:
                    completion_msg += f"，跳过 {skipped_files} 个无法读取或乱码的文件"
                progress_callback(100, 100, completion_msg)
            
            return kb
            
        except Exception as e:
            if error_callback:
                error_callback(f"创建知识库失败: {str(e)}")
            return None
    
    def _chunk_text(self, text: str, chunk_size: int, overlap: int = 150) -> List[str]:
        """将文本分块（带重叠窗口）
        
        Args:
            text: 待分块的文本
            chunk_size: 分块大小（字符数）
            overlap: 重叠窗口大小（字符数），默认150字符，约为chunk_size的18%
        
        Returns:
            分块后的文本列表
        
        Note:
            重叠窗口可以避免重要语义在分块边界被截断，提升检索效果
        """
        if not text:
            return []
        
        # 如果文本太短，直接返回
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        lines = text.split('\n')
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            
            # 如果当前块加上这行会超过chunk_size，保存当前块
            if current_size + line_size > chunk_size and current_chunk:
                chunk_text = '\n'.join(current_chunk)
                chunks.append(chunk_text)
                
                # 计算需要保留的重叠内容
                if overlap > 0:
                    # 从当前块尾部保留overlap大小的内容
                    overlap_text = chunk_text[-overlap:] if len(chunk_text) > overlap else chunk_text
                    
                    # 将重叠内容按行分割，保留完整的行
                    overlap_lines = overlap_text.split('\n')
                    # 去掉第一个可能不完整的行
                    if len(overlap_lines) > 1:
                        overlap_lines = overlap_lines[1:]
                    
                    current_chunk = overlap_lines + [line]
                    current_size = sum(len(l) + 1 for l in current_chunk)
                else:
                    current_chunk = [line]
                    current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        # 添加最后一个块
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def _generate_doc_id(self, content: str, file_path: str) -> str:
        """生成文档ID"""
        hash_input = f"{content}{file_path}".encode('utf-8')
        return hashlib.md5(hash_input).hexdigest()
    
    def _generate_kb_id(self, name: str) -> str:
        """生成知识库ID"""
        timestamp = datetime.now().isoformat()
        hash_input = f"{name}{timestamp}".encode('utf-8')
        return hashlib.md5(hash_input).hexdigest()
    
    def _save_knowledge_base(self, kb: KnowledgeBase, target_folder: Optional[str] = None):
        """保存知识库到指定文件夹
        
        Args:
            kb: 知识库对象
            target_folder: 目标文件夹路径，如果为None则使用默认存储目录
        """
        try:
            if target_folder:
                # 保存到用户指定的文件夹
                target_path = Path(target_folder)
                kb_file = target_path / f".knowledge_base_{kb.name}.json"
            else:
                # 保存到默认存储目录（向后兼容）
                kb_file = self.storage_dir / f"{kb.id}.json"
            
            # 转换为字典
            kb_dict = asdict(kb)
            
            # 确保目标目录存在
            kb_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存到文件
            with open(kb_file, 'w', encoding='utf-8') as f:
                json.dump(kb_dict, f, ensure_ascii=False, indent=2)
            
            print(f"[INFO] 知识库已保存: {kb_file}")
            
            # 同时在默认目录保存一份引用（用于全局管理）
            if target_folder:
                reference_file = self.storage_dir / f"{kb.id}.json"
                self.storage_dir.mkdir(parents=True, exist_ok=True)
                
                # 保存引用信息（重要：必须包含kb_type以便UI正确识别）
                reference_data = {
                    "id": kb.id,
                    "name": kb.name,
                    "root_path": kb.root_path,
                    "kb_file_path": str(kb_file.resolve()),
                    "created_at": kb.created_at,
                    "updated_at": kb.updated_at,
                    "metadata": kb.metadata,
                    "kb_type": kb.kb_type  # 添加kb_type字段，确保UI能正确识别知识库类型
                }
                
                with open(reference_file, 'w', encoding='utf-8') as f:
                    json.dump(reference_data, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            raise RuntimeError(f"保存知识库失败: {str(e)}")
    
    def load_knowledge_base(self, kb_id: str) -> Optional[KnowledgeBase]:
        """加载知识库
        
        Args:
            kb_id: 知识库ID
            
        Returns:
            知识库对象，如果不存在则返回None
        """
        reference_file = self.storage_dir / f"{kb_id}.json"
        
        if not reference_file.exists():
            return None
        
        with open(reference_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查是否是引用文件
        if "kb_file_path" in data:
            # 这是一个引用，加载实际的知识库文件
            kb_file_path = Path(data["kb_file_path"])
            if not kb_file_path.exists():
                print(f"[WARN] 知识库文件不存在: {kb_file_path}")
                return None
            
            with open(kb_file_path, 'r', encoding='utf-8') as f:
                kb_dict = json.load(f)
        else:
            # 这是旧格式的知识库文件，直接加载
            kb_dict = data
        
        # 重构文档对象
        documents = [
            VectorDocument(**doc) for doc in kb_dict['documents']
        ]
        
        kb_dict['documents'] = documents
        return KnowledgeBase(**kb_dict)
    
    def list_knowledge_bases(self, kb_type: Optional[str] = None, workspace_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出所有知识库
        
        Args:
            kb_type: 过滤知识库类型（可选），"history"或"setting"，None表示返回所有
            workspace_dir: 工作目录路径（可选），如果提供则会扫描该目录中的知识库文件
            
        Returns:
            知识库列表
        """
        kb_list = []
        kb_ids_seen = set()  # 用于去重
        
        # 1. 扫描默认存储目录（引用文件）
        for kb_file in self.storage_dir.glob("*.json"):
            try:
                with open(kb_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 检查是否是引用文件
                if "kb_file_path" in data:
                    # 引用文件格式
                    actual_kb_path = Path(data.get('kb_file_path', ''))
                    
                    # 检查实际的知识库文件是否存在
                    if not actual_kb_path.exists():
                        print(f"[WARN] 知识库文件不存在: {actual_kb_path}，删除引用文件: {kb_file}")
                        try:
                            kb_file.unlink()  # 删除引用文件
                        except Exception as e:
                            print(f"[ERROR] 删除引用文件失败: {e}")
                        continue  # 跳过这个知识库
                    
                    kb_info = {
                        'id': data['id'],
                        'name': data['name'],
                        'created_at': data['created_at'],
                        'root_path': data.get('root_path', ''),
                        'kb_file_path': data.get('kb_file_path', ''),
                        'total_documents': data.get('metadata', {}).get('total_chunks', 0),
                        'kb_type': data.get('kb_type', 'history'),  # 默认为history保持向后兼容
                        'metadata': data.get('metadata', {})  # 包含完整的metadata（包括sub_type）
                    }
                else:
                    # 旧格式知识库文件（直接存储在默认目录）
                    # 这种情况下，kb_file本身就是知识库文件，已经存在
                    kb_info = {
                        'id': data['id'],
                        'name': data['name'],
                        'created_at': data['created_at'],
                        'root_path': data.get('root_path', ''),
                        'kb_file_path': str(kb_file),
                        'total_documents': len(data.get('documents', [])),
                        'kb_type': data.get('kb_type', 'history'),  # 默认为history保持向后兼容
                        'metadata': data.get('metadata', {})  # 包含完整的metadata
                    }
                
                # 根据类型过滤
                if kb_type is None or kb_info['kb_type'] == kb_type:
                    kb_list.append(kb_info)
                    kb_ids_seen.add(kb_info['id'])
                    
            except Exception as e:
                print(f"[WARN] 读取知识库文件失败 {kb_file}: {e}")
                continue
        
        # 2. 如果提供了工作目录，扫描工作目录中的.knowledge_base_*.json文件
        if workspace_dir:
            workspace_path = Path(workspace_dir)
            if workspace_path.exists() and workspace_path.is_dir():
                try:
                    for kb_file in workspace_path.glob(".knowledge_base_*.json"):
                        try:
                            with open(kb_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            
                            kb_id = data.get('id')
                            # 如果已经从默认目录读取过这个知识库，跳过
                            if kb_id and kb_id in kb_ids_seen:
                                continue
                            
                            # 从完整知识库文件中提取信息
                            kb_info = {
                                'id': data['id'],
                                'name': data['name'],
                                'created_at': data['created_at'],
                                'root_path': data.get('root_path', ''),
                                'kb_file_path': str(kb_file.resolve()),
                                'total_documents': len(data.get('documents', [])),
                                'kb_type': data.get('kb_type', 'history'),
                                'metadata': data.get('metadata', {})
                            }
                            
                            # 根据类型过滤
                            if kb_type is None or kb_info['kb_type'] == kb_type:
                                kb_list.append(kb_info)
                                kb_ids_seen.add(kb_info['id'])
                                print(f"[INFO] 从工作目录发现知识库: {kb_info['name']} (类型: {kb_info['kb_type']})")
                                
                        except Exception as e:
                            print(f"[WARN] 读取工作目录知识库文件失败 {kb_file}: {e}")
                            continue
                            
                except Exception as e:
                    print(f"[WARN] 扫描工作目录知识库失败: {e}")
        
        return kb_list
    
    def delete_knowledge_base(self, kb_id: str) -> bool:
        """删除知识库"""
        kb_file = self.storage_dir / f"{kb_id}.json"
        
        if kb_file.exists():
            kb_file.unlink()
            return True
        
        return False
    
    def update_kb_prompt_ids(self, kb_id: str, polish_style_id: Optional[str] = None, 
                             prediction_style_id: Optional[str] = None) -> bool:
        """更新知识库的提示词ID
        
        Args:
            kb_id: 知识库ID
            polish_style_id: 润色风格提示词ID（可选）
            prediction_style_id: 预测提示词ID（可选）
            
        Returns:
            是否更新成功
        """
        try:
            # 加载知识库
            kb = self.load_knowledge_base(kb_id)
            if not kb:
                return False
            
            # 更新提示词ID
            if polish_style_id is not None:
                kb.polish_style_id = polish_style_id
            if prediction_style_id is not None:
                kb.prediction_style_id = prediction_style_id
            
            kb.updated_at = datetime.now().isoformat()
            
            # 保存知识库
            self._save_knowledge_base(kb, None)
            
            return True
        except Exception as e:
            print(f"[ERROR] 更新知识库提示词ID失败: {e}")
            return False
    
    def _build_bm25_index(self, kb_id: str, documents: List[VectorDocument]) -> Dict[str, Any]:
        """构建BM25索引（用于加速检索）
        
        Args:
            kb_id: 知识库ID
            documents: 文档列表
            
        Returns:
            BM25索引数据
        """
        import math
        from collections import Counter
        
        # 分词函数
        def tokenize(text: str) -> List[str]:
            import re
            text = re.sub(r'[^\w\s]', '', text)
            return list(text.replace(' ', ''))
        
        # 计算文档频率和文档长度
        doc_freq = {}  # 词 -> 出现在多少文档中
        doc_tokens_list = []  # 每个文档的token列表
        doc_lengths = []  # 每个文档的长度
        
        for doc in documents:
            tokens = tokenize(doc.content)
            doc_tokens_list.append(tokens)
            doc_lengths.append(len(tokens))
            
            # 统计文档频率
            unique_tokens = set(tokens)
            for token in unique_tokens:
                doc_freq[token] = doc_freq.get(token, 0) + 1
        
        # 计算平均文档长度
        avg_doc_len = sum(doc_lengths) / len(documents) if documents else 0
        
        # 计算IDF
        N = len(documents)
        idf_dict = {}
        for term, df in doc_freq.items():
            idf_dict[term] = math.log((N - df + 0.5) / (df + 0.5) + 1)
        
        # 构建索引
        index = {
            'doc_tokens_list': doc_tokens_list,
            'doc_lengths': doc_lengths,
            'avg_doc_len': avg_doc_len,
            'idf_dict': idf_dict,
            'N': N,
            'documents': documents
        }
        
        return index
    
    def _bm25_search_with_index(self, query_text: str, index: Dict[str, Any], top_k: int = 10) -> List[Dict[str, Any]]:
        """使用索引进行BM25检索（快速版本）
        
        Args:
            query_text: 查询文本
            index: BM25索引
            top_k: 返回前k个结果
            
        Returns:
            BM25检索结果列表
        """
        from collections import Counter
        import re
        
        # 分词
        def tokenize(text: str) -> List[str]:
            text = re.sub(r'[^\w\s]', '', text)
            return list(text.replace(' ', ''))
        
        # 查询词
        query_tokens = tokenize(query_text)
        query_counter = Counter(query_tokens)
        
        # BM25参数
        k1 = 1.5
        b = 0.75
        
        # 从索引中获取数据
        doc_tokens_list = index['doc_tokens_list']
        doc_lengths = index['doc_lengths']
        avg_doc_len = index['avg_doc_len']
        idf_dict = index['idf_dict']
        documents = index['documents']
        
        # 计算分数
        scores = []
        for i, (doc, doc_tokens, doc_len) in enumerate(zip(documents, doc_tokens_list, doc_lengths)):
            doc_counter = Counter(doc_tokens)
            
            score = 0.0
            for term in query_counter:
                if term in doc_counter:
                    tf = doc_counter[term]
                    idf = idf_dict.get(term, 0)
                    
                    # BM25公式
                    numerator = tf * (k1 + 1)
                    denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
                    score += idf * (numerator / denominator)
            
            scores.append({
                'document': doc,
                'bm25_score': score
            })
        
        # 按BM25分数排序
        scores.sort(key=lambda x: x['bm25_score'], reverse=True)
        
        return scores[:top_k]
    
    def _bm25_search(self, query_text: str, documents: List[VectorDocument], top_k: int = 10, kb_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """BM25关键词检索（带缓存优化）
        
        Args:
            query_text: 查询文本
            documents: 文档列表
            top_k: 返回前k个结果
            kb_id: 知识库ID（用于缓存）
            
        Returns:
            BM25检索结果列表
        """
        if not documents:
            return []
        
        # 如果有知识库ID，使用缓存索引
        if kb_id:
            if kb_id not in self._bm25_index_cache:
                # 构建并缓存索引
                print(f"[INFO] 构建BM25索引，知识库: {kb_id}")
                self._bm25_index_cache[kb_id] = self._build_bm25_index(kb_id, documents)
            
            # 使用缓存的索引进行快速检索
            return self._bm25_search_with_index(query_text, self._bm25_index_cache[kb_id], top_k)
        
        # 没有kb_id时，使用临时索引
        temp_index = self._build_bm25_index("temp", documents)
        return self._bm25_search_with_index(query_text, temp_index, top_k)
    
    def _hybrid_search(
        self,
        query_text: str,
        kb: KnowledgeBase,
        vector_top_k: int = 20,
        bm25_top_k: int = 20,
        alpha: float = 0.7
    ) -> List[Dict[str, Any]]:
        """混合检索：结合向量检索和BM25检索（带并行优化）
        
        Args:
            query_text: 查询文本
            kb: 知识库
            vector_top_k: 向量检索返回数量
            bm25_top_k: BM25检索返回数量
            alpha: 向量检索权重（0-1），BM25权重为1-alpha
            
        Returns:
            融合后的检索结果
        """
        import concurrent.futures
        import hashlib
        
        if not self.embedding_client:
            raise RuntimeError("未配置向量化客户端")
        
        if not kb.documents:
            return []
        
        print(f"[INFO] 混合检索：向量检索权重={alpha:.2f}, BM25权重={1-alpha:.2f}")
        
        # 1. 获取查询向量（带缓存）
        query_hash = hashlib.md5(query_text.encode('utf-8')).hexdigest()
        if query_hash in self._query_vector_cache:
            query_vector = self._query_vector_cache[query_hash]
            print(f"[INFO] 使用缓存的查询向量")
        else:
            try:
                query_vector = self.embedding_client.embed_text(query_text)
                self._query_vector_cache[query_hash] = query_vector
                # 限制缓存大小
                if len(self._query_vector_cache) > 100:
                    # 删除最旧的缓存（简单的FIFO策略）
                    oldest_key = next(iter(self._query_vector_cache))
                    del self._query_vector_cache[oldest_key]
            except Exception as e:
                print(f"[WARN] 向量化失败，仅使用BM25检索: {str(e)}")
                return self._bm25_search(query_text, kb.documents, bm25_top_k, kb_id=kb.id)
        
        # 2. 并行执行向量检索和BM25检索
        vector_results = []
        bm25_results = []
        
        def vector_search():
            """向量检索任务"""
            results = []
            for doc in kb.documents:
                if not doc.vector:
                    continue
                similarity = self._cosine_similarity(query_vector, doc.vector)
                results.append({
                    'document': doc,
                    'vector_score': similarity
                })
            results.sort(key=lambda x: x['vector_score'], reverse=True)
            return results[:vector_top_k]
        
        def bm25_search():
            """BM25检索任务"""
            return self._bm25_search(query_text, kb.documents, bm25_top_k, kb_id=kb.id)
        
        # 使用线程池并行执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            vector_future = executor.submit(vector_search)
            bm25_future = executor.submit(bm25_search)
            
            vector_results = vector_future.result()
            bm25_results = bm25_future.result()
        
        print(f"[INFO] 向量检索返回: {len(vector_results)} 个，BM25检索返回: {len(bm25_results)} 个")
        
        # 3. 融合结果（使用RRF - Reciprocal Rank Fusion）
        # 为每个文档建立索引
        doc_scores = {}  # doc_id -> {vector_rank, bm25_rank, combined_score}
        
        # 记录向量检索排名
        for rank, item in enumerate(vector_results, 1):
            doc_id = item['document'].id
            doc_scores[doc_id] = {
                'document': item['document'],
                'vector_rank': rank,
                'vector_score': item['vector_score'],
                'bm25_rank': None,
                'bm25_score': 0.0
            }
        
        # 记录BM25检索排名
        for rank, item in enumerate(bm25_results, 1):
            doc_id = item['document'].id
            if doc_id in doc_scores:
                doc_scores[doc_id]['bm25_rank'] = rank
                doc_scores[doc_id]['bm25_score'] = item['bm25_score']
            else:
                doc_scores[doc_id] = {
                    'document': item['document'],
                    'vector_rank': None,
                    'vector_score': 0.0,
                    'bm25_rank': rank,
                    'bm25_score': item['bm25_score']
                }
        
        # 计算RRF分数（Reciprocal Rank Fusion）
        k = 60  # RRF参数
        for doc_id, info in doc_scores.items():
            rrf_score = 0.0
            
            # 向量检索贡献
            if info['vector_rank'] is not None:
                rrf_score += alpha / (k + info['vector_rank'])
            
            # BM25检索贡献
            if info['bm25_rank'] is not None:
                rrf_score += (1 - alpha) / (k + info['bm25_rank'])
            
            info['rrf_score'] = rrf_score
            # 用于显示的综合相似度分数
            info['similarity_score'] = alpha * info['vector_score'] + (1 - alpha) * (info['bm25_score'] / 10)
        
        # 按RRF分数排序
        hybrid_results = sorted(doc_scores.values(), key=lambda x: x['rrf_score'], reverse=True)
        
        # 转换为标准格式
        final_results = []
        for item in hybrid_results:
            final_results.append({
                'document': item['document'],
                'similarity_score': item['similarity_score'],
                'rrf_score': item['rrf_score'],
                'vector_score': item['vector_score'],
                'bm25_score': item['bm25_score']
            })
        
        print(f"[INFO] 混合检索完成：向量 {len(vector_results)} 个，BM25 {len(bm25_results)} 个，融合后 {len(final_results)} 个")
        
        return final_results
    
    def search_similar_documents(
        self, 
        query_text: str, 
        kb: KnowledgeBase, 
        top_k: int = 10,
        rerank_client: Optional[RerankClient] = None,
        final_top_n: int = 5,
        use_hybrid_search: bool = True,
        use_mmr: bool = True
    ) -> List[Dict[str, Any]]:
        """在知识库中搜索相似文档（支持混合检索和MMR多样性）
        
        Args:
            query_text: 查询文本
            kb: 知识库对象
            top_k: 候选文档数量（用于重排前）
            rerank_client: 重排序客户端（可选），如果提供则会对结果重排
            final_top_n: 重排后返回的最终文档数量
            use_hybrid_search: 是否使用混合检索（向量+BM25），默认True
            use_mmr: 是否使用MMR多样性重排，默认True
            
        Returns:
            相似文档列表，每个元素包含：
            - document: VectorDocument对象
            - similarity_score: 相似度分数
            - relevance_score: 重排相关性分数（仅在使用重排时）
        """
        if not self.embedding_client:
            raise RuntimeError("未配置向量化客户端")
        
        if not kb.documents:
            return []
        
        # 1. 获取查询向量（用于MMR）
        query_vector = None
        try:
            query_vector = self.embedding_client.embed_text(query_text)
        except Exception as e:
            print(f"[WARN] 查询向量化失败: {str(e)}")
            if not use_hybrid_search:
                raise RuntimeError(f"查询文本向量化失败: {str(e)}")
        
        # 2. 选择检索策略
        if use_hybrid_search:
            # 使用混合检索（向量 + BM25）
            # 从配置中获取alpha值
            alpha = 0.7  # 默认值
            try:
                # 尝试从配置管理器获取
                from app.config_manager import ConfigManager
                config_manager = ConfigManager()
                kb_config = config_manager.get_kb_config()
                alpha = kb_config.hybrid_search_alpha
                print(f"[INFO] 使用混合检索策略（向量 + BM25），alpha={alpha:.2f}（从配置读取）")
            except Exception:
                print(f"[INFO] 使用混合检索策略（向量 + BM25），alpha={alpha:.2f}（默认值）")
            
            top_candidates = self._hybrid_search(
                query_text=query_text,
                kb=kb,
                vector_top_k=top_k,
                bm25_top_k=top_k,
                alpha=alpha
            )
        else:
            # 仅使用向量检索（原有逻辑）
            print(f"[INFO] 使用纯向量检索策略")
            if not query_vector:
                raise RuntimeError("查询向量化失败且未启用混合检索")
            
            similarities = []
            for doc in kb.documents:
                if not doc.vector:
                    continue
                
                similarity = self._cosine_similarity(query_vector, doc.vector)
                similarities.append({
                    'document': doc,
                    'similarity_score': similarity
                })
            
            similarities.sort(key=lambda x: x['similarity_score'], reverse=True)
            top_candidates = similarities[:top_k]
        
        # 3. 如果启用MMR且有查询向量，进行多样性重排
        if use_mmr and query_vector and top_candidates and len(top_candidates) > final_top_n:
            print(f"[INFO] 启用MMR多样性重排")
            top_candidates = self._mmr_rerank(
                query_vector=query_vector,
                candidates=top_candidates,
                top_n=top_k,  # 先用MMR从top_k中选出多样化的子集
                lambda_param=0.7  # 70%相关性，30%多样性
            )
        
        # 4. 如果提供了重排客户端，进行语义重排
        if rerank_client and top_candidates:
            print(f"[INFO] 使用重排模型进行重排序，候选文档数: {len(top_candidates)}")
            try:
                # 提取候选文档的文本内容
                candidate_texts = [item['document'].content for item in top_candidates]
                
                print(f"[DEBUG] 准备调用重排API，查询文本长度: {len(query_text)}, 候选数: {len(candidate_texts)}")
                
                # 调用重排API（根据相关性分数过滤低质量结果）
                reranked_results = rerank_client.rerank(
                    query=query_text,
                    documents=candidate_texts,
                    top_n=final_top_n
                )
                
                print(f"[INFO] 重排完成，返回 {len(reranked_results)} 个结果")
                
                # 重构结果，保留重排后的顺序和分数
                final_results = []
                for rerank_item in reranked_results:
                    # 找到对应的原始文档
                    original_index = rerank_item['index']
                    original_item = top_candidates[original_index]
                    
                    # 添加重排相关性分数
                    result_item = {
                        'document': original_item['document'],
                        'similarity_score': original_item['similarity_score'],
                        'relevance_score': rerank_item['relevance_score']
                    }
                    
                    print(f"[DEBUG] 重排结果 {len(final_results)+1}: 相似度={original_item['similarity_score']:.4f}, 重排分数={rerank_item['relevance_score']:.4f}")
                    final_results.append(result_item)
                
                print(f"[INFO] 重排序成功应用，返回 {len(final_results)} 个文档")
                
                # 对重排结果也进行去重
                final_results = self._remove_duplicate_documents(final_results, similarity_threshold=0.85)
                
                # 应用时间序权重增强（离当前位置越近的文档权重越高）
                final_results = self._apply_recency_boost(final_results, kb)
                
                return final_results
                
            except Exception as e:
                # 重排失败时回退到向量检索结果
                print(f"[WARN] 重排序失败，回退到向量检索结果: {str(e)}")
                import traceback
                traceback.print_exc()
                fallback_results = top_candidates[:final_top_n]
                # 应用时间序权重增强
                fallback_results = self._apply_recency_boost(fallback_results, kb)
                return fallback_results
        else:
            if not rerank_client:
                print(f"[WARN] 重排客户端未初始化，仅使用向量检索")
            elif not top_candidates:
                print(f"[WARN] 没有候选文档，跳过重排")
        
        # 5. 如果没有重排客户端，直接返回向量检索的前final_top_n个
        print(f"[INFO] 仅使用向量检索，返回前 {min(final_top_n, len(top_candidates))} 个结果")
        results = top_candidates[:final_top_n]
        
        # 6. 对结果进行去重（无论是否使用重排）
        results = self._remove_duplicate_documents(results, similarity_threshold=0.85)
        
        # 7. 应用时间序权重增强（离当前位置越近的文档权重越高）
        results = self._apply_recency_boost(results, kb)
        
        return results
    
    def _mmr_rerank(
        self,
        query_vector: List[float],
        candidates: List[Dict[str, Any]],
        top_n: int = 5,
        lambda_param: float = 0.7
    ) -> List[Dict[str, Any]]:
        """最大边际相关性(MMR)重排序，平衡相关性和多样性
        
        Args:
            query_vector: 查询向量
            candidates: 候选文档列表
            top_n: 返回文档数量
            lambda_param: 平衡参数，越大越重视相关性，越小越重视多样性（0-1）
            
        Returns:
            MMR重排后的文档列表
        """
        if not candidates or len(candidates) <= 1:
            return candidates[:top_n]
        
        print(f"[INFO] MMR重排序：λ={lambda_param:.2f}（相关性权重），多样性权重={1-lambda_param:.2f}")
        
        # 已选择的文档
        selected = []
        # 未选择的候选文档
        remaining = candidates.copy()
        
        # 贪心算法：每次选择MMR分数最高的文档
        while len(selected) < top_n and remaining:
            mmr_scores = []
            
            for candidate in remaining:
                doc_vector = candidate['document'].vector
                if not doc_vector:
                    continue
                
                # 计算与查询的相似度（相关性）
                query_sim = self._cosine_similarity(query_vector, doc_vector)
                
                # 计算与已选文档的最大相似度（用于多样性）
                max_sim_to_selected = 0.0
                if selected:
                    for selected_item in selected:
                        selected_vector = selected_item['document'].vector
                        if selected_vector:
                            sim = self._cosine_similarity(doc_vector, selected_vector)
                            max_sim_to_selected = max(max_sim_to_selected, sim)
                
                # MMR分数 = λ * 相关性 - (1-λ) * 与已选文档的最大相似度
                mmr_score = lambda_param * query_sim - (1 - lambda_param) * max_sim_to_selected
                
                mmr_scores.append({
                    'candidate': candidate,
                    'mmr_score': mmr_score,
                    'relevance': query_sim,
                    'max_similarity': max_sim_to_selected
                })
            
            if not mmr_scores:
                break
            
            # 选择MMR分数最高的文档
            best = max(mmr_scores, key=lambda x: x['mmr_score'])
            selected.append(best['candidate'])
            remaining.remove(best['candidate'])
            
            print(f"[DEBUG] MMR选择文档 {len(selected)}: 相关性={best['relevance']:.3f}, "
                  f"与已选最大相似度={best['max_similarity']:.3f}, MMR分数={best['mmr_score']:.3f}")
        
        print(f"[INFO] MMR重排序完成：从 {len(candidates)} 个候选中选出 {len(selected)} 个多样化文档")
        
        return selected
    
    def _apply_recency_boost(
        self, 
        documents: List[Dict[str, Any]], 
        kb: KnowledgeBase,
        boost_strength: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """应用时间序权重增强（离当前位置越近的文档权重越高）
        
        策略说明：
        - 按照文档在知识库中的位置，越靠后（越新）的文档获得更高的权重加成
        - 这样能确保剧情预测更符合当前剧情发展趋势
        - 同时保持适度的boost_strength，确保向量检索仍能捕获远处的伏笔
        
        Args:
            documents: 检索到的文档列表，每个包含 'document' 和分数字段
            kb: 知识库对象
            boost_strength: 权重增强强度（0-1），如果为None则从配置读取
                - 0.0: 不增强，完全依赖相似度（适合发现远处伏笔）
                - 0.2: 温和增强，更多依赖原始相似度
                - 0.3: 适中增强（默认），平衡近期剧情和远处伏笔
                - 0.5: 强力增强，更偏重近期剧情
        
        Returns:
            权重调整后并重新排序的文档列表
        """
        if not documents or not kb.documents:
            return documents
        
        # 1. 从配置中获取boost_strength（如果未指定）
        if boost_strength is None:
            try:
                from app.config_manager import ConfigManager
                config_manager = ConfigManager()
                kb_config = config_manager.get_kb_config()
                boost_strength = kb_config.recency_boost_strength
                print(f"[INFO] 时间序权重增强强度从配置读取: {boost_strength}")
            except Exception:
                boost_strength = 0.3  # 默认值
                print(f"[INFO] 时间序权重增强强度使用默认值: {boost_strength}")
        
        # 如果boost_strength为0，直接返回不做增强
        if boost_strength <= 0:
            print(f"[INFO] 时间序权重增强已禁用（boost_strength={boost_strength}）")
            return documents
        
        # 2. 构建文档ID到索引位置的映射（索引越大，说明越新）
        doc_id_to_position = {doc.id: idx for idx, doc in enumerate(kb.documents)}
        total_docs = len(kb.documents)
        
        if total_docs == 0:
            return documents
        
        print(f"[INFO] 应用时间序权重增强（boost_strength={boost_strength}）")
        
        # 3. 为每个检索到的文档计算时间序权重加成
        boosted_documents = []
        for item in documents:
            doc = item['document']
            doc_id = doc.id
            
            # 获取文档在知识库中的位置
            if doc_id not in doc_id_to_position:
                # 如果文档不在知识库中（理论上不应该发生），保持原分数
                boosted_documents.append(item)
                continue
            
            position = doc_id_to_position[doc_id]
            
            # 计算归一化的位置权重（0到1，越新越接近1）
            # 使用指数衰减：越新的文档权重增长越快
            normalized_position = position / total_docs
            recency_weight = normalized_position ** 0.7  # 0.7次方使得权重分布更平滑
            
            # 获取原始分数（优先使用relevance_score，其次similarity_score）
            original_score = item.get('relevance_score', item.get('similarity_score', 0.0))
            
            # 计算最终分数：原分数 × (1 + 时间权重加成)
            # 时间权重加成 = recency_weight × boost_strength
            # 例如：最新的文档(recency_weight=1)，boost_strength=0.3时，分数会增加30%
            boosted_score = original_score * (1.0 + recency_weight * boost_strength)
            
            # 创建新的结果项
            boosted_item = item.copy()
            boosted_item['original_score'] = original_score
            boosted_item['recency_weight'] = recency_weight
            boosted_item['boosted_score'] = boosted_score
            
            # 更新主要分数字段（保持原有字段名）
            if 'relevance_score' in item:
                boosted_item['relevance_score'] = boosted_score
            if 'similarity_score' in item:
                boosted_item['similarity_score'] = boosted_score
            
            boosted_documents.append(boosted_item)
            
            print(f"[DEBUG] 文档位置={position}/{total_docs}, "
                  f"近期权重={recency_weight:.3f}, "
                  f"原分数={original_score:.4f}, "
                  f"增强后={boosted_score:.4f} (+{(boosted_score-original_score)/original_score*100:.1f}%)")
        
        # 4. 按照增强后的分数重新排序
        # 优先使用relevance_score，其次使用similarity_score
        boosted_documents.sort(
            key=lambda x: x.get('relevance_score', x.get('similarity_score', 0.0)),
            reverse=True
        )
        
        print(f"[INFO] 时间序权重增强完成，文档顺序已更新")
        
        return boosted_documents
    
    def _remove_duplicate_documents(self, documents: List[Dict[str, Any]], similarity_threshold: float = 0.85) -> List[Dict[str, Any]]:
        """去除重复或高度相似的文档
        
        Args:
            documents: 文档列表，每个包含 'document' 和分数
            similarity_threshold: 文本相似度阈值，超过此值视为重复（默认0.85）
            
        Returns:
            去重后的文档列表
        """
        if not documents or len(documents) <= 1:
            return documents
        
        def text_similarity(text1: str, text2: str) -> float:
            """计算两段文本的字符级相似度（Jaccard相似度）"""
            # 转换为字符集合
            set1 = set(text1)
            set2 = set(text2)
            
            if not set1 or not set2:
                return 0.0
            
            # Jaccard相似度
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            
            return intersection / union if union > 0 else 0.0
        
        # 保留不重复的文档
        unique_docs = [documents[0]]  # 第一个文档总是保留（相关度最高）
        
        for doc in documents[1:]:
            is_duplicate = False
            current_content = doc['document'].content
            
            # 与已保留的文档比较
            for unique_doc in unique_docs:
                unique_content = unique_doc['document'].content
                
                # 计算文本相似度
                sim = text_similarity(current_content, unique_content)
                
                if sim >= similarity_threshold:
                    is_duplicate = True
                    print(f"[INFO] 去重：发现重复文档（相似度={sim:.2f}），已跳过")
                    break
            
            if not is_duplicate:
                unique_docs.append(doc)
        
        if len(unique_docs) < len(documents):
            print(f"[INFO] 去重完成：原始 {len(documents)} 个文档，去重后 {len(unique_docs)} 个")
        
        return unique_docs
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量的余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            余弦相似度（-1到1之间）
        """
        if len(vec1) != len(vec2):
            raise ValueError("向量维度不匹配")
        
        # 计算点积
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # 计算向量的模
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        # 避免除零
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def get_document_with_context(
        self,
        doc: VectorDocument,
        kb: KnowledgeBase,
        context_lines_before: int = 4,
        context_lines_after: int = 4
    ) -> Dict[str, Any]:
        """获取文档及其上下文
        
        Args:
            doc: 目标文档
            kb: 知识库对象
            context_lines_before: 上文行数（默认4行，已优化以提供更多上下文）
            context_lines_after: 下文行数（默认4行，已优化以提供更多上下文）
            
        Returns:
            包含文档及上下文的字典：
            - content: 文档内容
            - context_before: 上文内容（列表）
            - context_after: 下文内容（列表）
            - file_path: 文件路径
            - full_context: 完整上下文（包含当前文档）
        """
        # 获取同一文件的所有文档块（按chunk_index排序）
        file_path = doc.metadata.get('file_path')
        chunk_index = doc.metadata.get('chunk_index', 0)
        
        # 查找同一文件的所有文档块
        same_file_docs = [
            d for d in kb.documents 
            if d.metadata.get('file_path') == file_path
        ]
        
        # 按chunk_index排序
        same_file_docs.sort(key=lambda d: d.metadata.get('chunk_index', 0))
        
        # 找到当前文档的位置
        current_index = -1
        for i, d in enumerate(same_file_docs):
            if d.id == doc.id:
                current_index = i
                break
        
        if current_index == -1:
            # 找不到当前文档，返回基本信息
            return {
                'content': doc.content,
                'context_before': [],
                'context_after': [],
                'file_path': file_path,
                'full_context': doc.content
            }
        
        # 提取上文
        start_index = max(0, current_index - context_lines_before)
        context_before = [
            same_file_docs[i].content 
            for i in range(start_index, current_index)
        ]
        
        # 提取下文
        end_index = min(len(same_file_docs), current_index + context_lines_after + 1)
        context_after = [
            same_file_docs[i].content 
            for i in range(current_index + 1, end_index)
        ]
        
        # 构建完整上下文
        full_context_parts = context_before + [doc.content] + context_after
        full_context = '\n'.join(full_context_parts)
        
        return {
            'content': doc.content,
            'context_before': context_before,
            'context_after': context_after,
            'file_path': file_path,
            'full_context': full_context
        }