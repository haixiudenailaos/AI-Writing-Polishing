"""
文件资源管理器组件
类似VSCode的树形文件浏览器
"""

from typing import Dict, Optional
from pathlib import Path
from PySide6 import QtWidgets, QtCore, QtGui


class FileExplorerWidget(QtWidgets.QWidget):
    """文件资源管理器组件"""
    
    # 信号定义
    fileSelected = QtCore.Signal(str)  # 文件被选中
    fileOpened = QtCore.Signal(str)  # 文件被打开
    folderSelected = QtCore.Signal(str)  # 文件夹被选中
    newFileRequested = QtCore.Signal(str)  # 请求创建新文件（传递文件夹路径）
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_theme = {}
        self._root_path: Optional[Path] = None
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """设置UI布局"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建标题栏
        header = QtWidgets.QFrame()
        header.setObjectName("FileExplorerHeader")
        header.setFixedHeight(32)
        
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)
        
        title_label = QtWidgets.QLabel("文件资源管理器")
        title_label.setObjectName("FileExplorerTitle")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # 折叠按钮
        self.collapse_button = QtWidgets.QPushButton("−")
        self.collapse_button.setObjectName("CollapseButton")
        self.collapse_button.setFixedSize(24, 24)
        self.collapse_button.setToolTip("折叠全部")
        header_layout.addWidget(self.collapse_button)
        
        # 刷新按钮
        self.refresh_button = QtWidgets.QPushButton("↻")
        self.refresh_button.setObjectName("RefreshButton")
        self.refresh_button.setFixedSize(24, 24)
        self.refresh_button.setToolTip("刷新")
        header_layout.addWidget(self.refresh_button)
        
        layout.addWidget(header)
        
        # 创建树形视图
        self.tree_view = QtWidgets.QTreeView()
        self.tree_view.setObjectName("FileTree")
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setAnimated(True)
        self.tree_view.setIndentation(16)
        self.tree_view.setExpandsOnDoubleClick(False)
        
        # 创建文件系统模型
        self.file_model = QtWidgets.QFileSystemModel()
        self.file_model.setRootPath("")
        
        # 设置过滤器：只显示文件夹和所有支持的文件格式
        self.file_model.setNameFilters([
            "*.txt",      # 纯文本
            "*.md",       # Markdown
            "*.markdown", # Markdown
            "*.docx",     # Word新格式
            "*.doc",      # Word旧格式
            "*.pdf",      # PDF文档
            "*.rtf",      # RTF富文本
            "*.odt",      # OpenDocument
            "*.html",     # HTML
            "*.htm",      # HTML
            "*.epub"      # ePub电子书
        ])
        self.file_model.setNameFilterDisables(False)
        
        self.tree_view.setModel(self.file_model)
        
        # 隐藏不需要的列
        for i in range(1, self.file_model.columnCount()):
            self.tree_view.hideColumn(i)
        
        layout.addWidget(self.tree_view)
        
        # 空状态提示
        self.empty_label = QtWidgets.QLabel("尚未导入文件夹\n\n点击上方按钮导入")
        self.empty_label.setObjectName("EmptyLabel")
        self.empty_label.setAlignment(QtCore.Qt.AlignCenter)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)
        
        # 默认显示空状态
        self.tree_view.hide()
    
    def _connect_signals(self):
        """连接信号"""
        self.tree_view.clicked.connect(self._on_item_clicked)
        self.tree_view.doubleClicked.connect(self._on_item_double_clicked)
        self.collapse_button.clicked.connect(self._collapse_all)
        self.refresh_button.clicked.connect(self._refresh)
        
        # 启用右键菜单
        self.tree_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._show_context_menu)
    
    def load_folder(self, folder_path: str):
        """加载文件夹"""
        path = Path(folder_path)
        if not path.exists() or not path.is_dir():
            QtWidgets.QMessageBox.warning(
                self, "错误", f"无效的文件夹路径: {folder_path}"
            )
            return
        
        self._root_path = path
        root_index = self.file_model.setRootPath(str(path))
        self.tree_view.setRootIndex(root_index)
        
        # 显示树形视图，隐藏空状态
        self.empty_label.hide()
        self.tree_view.show()
        
        # 展开根目录
        self.tree_view.expand(root_index)
    
    def _on_item_clicked(self, index: QtCore.QModelIndex):
        """处理项目点击"""
        file_path = self.file_model.filePath(index)
        
        if self.file_model.isDir(index):
            self.folderSelected.emit(file_path)
        else:
            self.fileSelected.emit(file_path)
    
    def _on_item_double_clicked(self, index: QtCore.QModelIndex):
        """处理项目双击"""
        if not self.file_model.isDir(index):
            file_path = self.file_model.filePath(index)
            self.fileOpened.emit(file_path)
    
    def _collapse_all(self):
        """折叠所有项"""
        self.tree_view.collapseAll()
    
    def _refresh(self):
        """刷新文件列表"""
        if self._root_path:
            self.load_folder(str(self._root_path))
    
    def _show_context_menu(self, position: QtCore.QPoint):
        """显示右键菜单"""
        index = self.tree_view.indexAt(position)
        
        # 创建菜单
        menu = QtWidgets.QMenu(self)
        
        # 根据点击位置决定菜单内容
        if index.isValid():
            file_path = self.file_model.filePath(index)
            path = Path(file_path)
            
            if path.is_dir():
                # 点击的是文件夹
                new_file_action = menu.addAction("📄 新建文本文件")
                new_file_action.triggered.connect(lambda: self._create_new_file(str(path)))
                
                new_docx_action = menu.addAction("📝 新建Word文档")
                new_docx_action.triggered.connect(lambda: self._create_new_docx(str(path)))
                
                menu.addSeparator()
                
                refresh_action = menu.addAction("↻ 刷新")
                refresh_action.triggered.connect(self._refresh)
            else:
                # 点击的是文件
                open_action = menu.addAction("打开")
                open_action.triggered.connect(lambda: self.fileOpened.emit(str(path)))
                
                menu.addSeparator()
                
                reveal_action = menu.addAction("在文件夹中显示")
                reveal_action.triggered.connect(lambda: self._reveal_in_folder(str(path)))
        else:
            # 点击空白处
            if self._root_path:
                new_file_action = menu.addAction("📄 新建文本文件")
                new_file_action.triggered.connect(lambda: self._create_new_file(str(self._root_path)))
                
                new_docx_action = menu.addAction("📝 新建Word文档")
                new_docx_action.triggered.connect(lambda: self._create_new_docx(str(self._root_path)))
                
                menu.addSeparator()
                
                refresh_action = menu.addAction("↻ 刷新")
                refresh_action.triggered.connect(self._refresh)
        
        # 显示菜单
        menu.exec(self.tree_view.viewport().mapToGlobal(position))
    
    def _create_new_file(self, folder_path: str):
        """创建新文本文件"""
        # 弹出对话框询问文件名
        file_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "新建文本文件",
            "请输入文件名（不含扩展名）:",
            QtWidgets.QLineEdit.Normal,
            "新建文档"
        )
        
        if ok and file_name:
            # 添加.txt扩展名
            file_path = str(Path(folder_path) / f"{file_name}.txt")
            
            # 发送信号，让主窗口处理创建
            self.newFileRequested.emit(file_path)
    
    def _create_new_docx(self, folder_path: str):
        """创建新Word文档"""
        # 弹出对话框询问文件名
        file_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "新建Word文档",
            "请输入文件名（不含扩展名）:",
            QtWidgets.QLineEdit.Normal,
            "新建文档"
        )
        
        if ok and file_name:
            # 添加.docx扩展名
            file_path = str(Path(folder_path) / f"{file_name}.docx")
            
            # 发送信号，让主窗口处理创建
            self.newFileRequested.emit(file_path)
    
    def _reveal_in_folder(self, file_path: str):
        """在文件管理器中显示文件"""
        import subprocess
        import sys
        
        if sys.platform == 'win32':
            # Windows
            subprocess.run(['explorer', '/select,', file_path])
        elif sys.platform == 'darwin':
            # macOS
            subprocess.run(['open', '-R', file_path])
        else:
            # Linux
            folder = str(Path(file_path).parent)
            subprocess.run(['xdg-open', folder])
    
    def get_current_folder(self) -> Optional[str]:
        """获取当前选中的文件夹路径"""
        index = self.tree_view.currentIndex()
        if not index.isValid():
            return str(self._root_path) if self._root_path else None
        
        file_path = self.file_model.filePath(index)
        path = Path(file_path)
        
        if path.is_dir():
            return str(path)
        else:
            return str(path.parent)
    
    def get_root_path(self) -> Optional[str]:
        """获取工作空间根目录路径"""
        return str(self._root_path) if self._root_path else None
    
    def set_theme(self, theme: Dict[str, str]):
        """设置主题"""
        self._current_theme = theme
        self._apply_theme()
    
    def _apply_theme(self):
        """应用主题"""
        if not self._current_theme:
            return
        
        style_sheet = f"""
        #FileExplorerHeader {{
            background-color: {self._current_theme.get('sidebarBackground', '#252526')};
            border-bottom: 1px solid {self._current_theme.get('borderColor', '#3e3e42')};
        }}
        
        #FileExplorerTitle {{
            color: {self._current_theme.get('sidebarForeground', '#cccccc')};
            font-weight: bold;
            font-size: 11px;
            text-transform: uppercase;
        }}
        
        #FileTree {{
            background-color: {self._current_theme.get('sidebarBackground', '#252526')};
            color: {self._current_theme.get('sidebarForeground', '#cccccc')};
            border: none;
            outline: none;
        }}
        
        #FileTree::item {{
            padding: 3px;
            border-radius: 2px;
        }}
        
        #FileTree::item:hover {{
            background-color: {self._current_theme.get('listHoverBackground', '#2a2d2e')};
        }}
        
        #FileTree::item:selected {{
            background-color: {self._current_theme.get('listActiveSelectionBackground', '#37373d')};
            color: {self._current_theme.get('listActiveSelectionForeground', '#ffffff')};
        }}
        
        #CollapseButton, #RefreshButton {{
            background-color: transparent;
            border: none;
            color: {self._current_theme.get('sidebarForeground', '#cccccc')};
            font-size: 14px;
            border-radius: 3px;
        }}
        
        #CollapseButton:hover, #RefreshButton:hover {{
            background-color: {self._current_theme.get('listHoverBackground', '#2a2d2e')};
        }}
        
        #EmptyLabel {{
            color: {self._current_theme.get('descriptionForeground', '#717171')};
            font-size: 12px;
        }}
        """
        
        self.setStyleSheet(style_sheet)
