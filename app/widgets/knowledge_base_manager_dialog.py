"""
知识库管理对话框
提供历史知识库、大纲、人设三种知识库的创建和管理功能
"""

from typing import Dict, Optional, List
from pathlib import Path
from PySide6 import QtWidgets, QtCore, QtGui
from app.knowledge_base import KnowledgeBaseManager, KnowledgeBase


class KnowledgeBaseItemWidget(QtWidgets.QWidget):
    """知识库列表项组件"""
    
    # 信号定义
    activate_clicked = QtCore.Signal(str)  # kb_id
    delete_clicked = QtCore.Signal(str)  # kb_id
    
    def __init__(self, kb_info: Dict, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.kb_info = kb_info
        self.kb_id = kb_info['id']
        self.is_active = is_active
        
        self._setup_ui()
        
    def _setup_ui(self):
        """设置UI"""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # 激活状态指示器
        self.active_indicator = QtWidgets.QLabel("✓" if self.is_active else "")
        self.active_indicator.setObjectName("ActiveIndicator")
        self.active_indicator.setFixedWidth(20)
        self.active_indicator.setAlignment(QtCore.Qt.AlignCenter)
        font = self.active_indicator.font()
        font.setPointSize(14)
        font.setBold(True)
        self.active_indicator.setFont(font)
        layout.addWidget(self.active_indicator)
        
        # 知识库信息
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setSpacing(4)
        
        # 名称
        name_label = QtWidgets.QLabel(self.kb_info['name'])
        name_label.setObjectName("KBNameLabel")
        font = name_label.font()
        font.setPointSize(11)
        font.setBold(True)
        name_label.setFont(font)
        info_layout.addWidget(name_label)
        
        # 详细信息
        details = f"文档数量: {self.kb_info.get('total_documents', 0)} | 路径: {self.kb_info.get('root_path', '未知')}"
        details_label = QtWidgets.QLabel(details)
        details_label.setObjectName("KBDetailsLabel")
        font = details_label.font()
        font.setPointSize(9)
        details_label.setFont(font)
        info_layout.addWidget(details_label)
        
        layout.addLayout(info_layout, 1)
        
        # 操作按钮
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(8)
        
        # 激活/取消激活按钮
        self.activate_button = QtWidgets.QPushButton("取消激活" if self.is_active else "激活")
        self.activate_button.setObjectName("ActivateButton")
        self.activate_button.setFixedWidth(80)
        self.activate_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        # 通过属性标记当前是否为激活状态，用于样式切换
        self.activate_button.setProperty("active", self.is_active)
        self.activate_button.style().unpolish(self.activate_button)
        self.activate_button.style().polish(self.activate_button)
        self.activate_button.clicked.connect(lambda: self.activate_clicked.emit(self.kb_id))
        button_layout.addWidget(self.activate_button)
        
        # 删除按钮
        delete_button = QtWidgets.QPushButton("删除")
        delete_button.setObjectName("DeleteButton")
        delete_button.setFixedWidth(60)
        delete_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        delete_button.clicked.connect(lambda: self.delete_clicked.emit(self.kb_id))
        button_layout.addWidget(delete_button)
        
        layout.addLayout(button_layout)
    
    def set_active(self, is_active: bool):
        """设置激活状态"""
        self.is_active = is_active
        self.active_indicator.setText("✓" if is_active else "")
        self.activate_button.setText("取消激活" if is_active else "激活")
        self.activate_button.setProperty("active", is_active)
        # 刷新按钮样式以应用基于属性的样式规则
        self.activate_button.style().unpolish(self.activate_button)
        self.activate_button.style().polish(self.activate_button)


class KnowledgeBaseTypeDialog(QtWidgets.QDialog):
    """单个类型的知识库管理对话框"""
    
    def __init__(self, kb_type: str, kb_manager: KnowledgeBaseManager, 
                 active_kb_ids: Optional[List[str]] = None, workspace_dir: Optional[str] = None, parent=None):
        """
        Args:
            kb_type: 知识库类型 - "history"(历史知识库), "outline"(大纲), "character"(人设)
            kb_manager: 知识库管理器
            active_kb_ids: 当前激活的知识库ID列表（支持多个）
            workspace_dir: 工作目录路径（用于存储知识库文件）
            parent: 父窗口
        """
        super().__init__(parent)
        self.kb_type = kb_type
        self.kb_manager = kb_manager
        self.active_kb_ids = active_kb_ids or []  # 支持多个激活的知识库
        self.workspace_dir = workspace_dir
        self._current_theme = {}
        
        # 设置窗口标题
        type_names = {
            "history": "历史知识库",
            "outline": "大纲知识库", 
            "character": "人设知识库"
        }
        self.setWindowTitle(f"{type_names.get(kb_type, '知识库')}管理")
        self.setModal(True)
        self.resize(900, 700)
        
        self._setup_ui()
        self._load_knowledge_bases()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 顶部：标题和构建按钮
        header_layout = QtWidgets.QHBoxLayout()
        
        # 标题
        type_descriptions = {
            "history": "历史知识库 - 存储已写作的历史章节，用于剧情预测参考",
            "outline": "大纲知识库 - 存储作品大纲、剧情规划等内容",
            "character": "人设知识库 - 存储角色设定、性格特征、背景故事等"
        }
        title_label = QtWidgets.QLabel(type_descriptions.get(self.kb_type, "知识库管理"))
        title_label.setObjectName("DialogTitle")
        title_label.setWordWrap(True)
        font = title_label.font()
        font.setPointSize(12)
        font.setBold(True)
        title_label.setFont(font)
        header_layout.addWidget(title_label, 1)
        
        # 构建知识库按钮
        create_button = QtWidgets.QPushButton("+ 构建新知识库")
        create_button.setObjectName("CreateKBButton")
        create_button.setFixedHeight(36)
        create_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        create_button.clicked.connect(self._on_create_knowledge_base)
        header_layout.addWidget(create_button)
        
        layout.addLayout(header_layout)
        
        # 分隔线
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        separator.setObjectName("Separator")
        layout.addWidget(separator)
        
        # 知识库列表区域
        list_group = QtWidgets.QGroupBox("已创建的知识库")
        list_group.setObjectName("KBListGroup")
        list_layout = QtWidgets.QVBoxLayout(list_group)
        
        # 使用滚动区域
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setObjectName("KBScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        # 知识库列表容器
        self.kb_list_widget = QtWidgets.QWidget()
        self.kb_list_layout = QtWidgets.QVBoxLayout(self.kb_list_widget)
        self.kb_list_layout.setContentsMargins(0, 0, 0, 0)
        self.kb_list_layout.setSpacing(8)
        self.kb_list_layout.addStretch()
        
        scroll_area.setWidget(self.kb_list_widget)
        list_layout.addWidget(scroll_area)
        
        layout.addWidget(list_group, 1)
        
        # 底部按钮
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QtWidgets.QPushButton("关闭")
        close_button.setObjectName("CloseButton")
        close_button.setFixedSize(100, 36)
        close_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def _load_knowledge_bases(self):
        """加载知识库列表"""
        # 清空现有列表
        while self.kb_list_layout.count() > 1:  # 保留最后的stretch
            item = self.kb_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 根据类型映射到存储的kb_type
        # 历史知识库 -> "history"
        # 大纲知识库 -> "setting" (存储类型使用setting)
        # 人设知识库 -> "setting" (存储类型使用setting)
        storage_type = "history" if self.kb_type == "history" else "setting"
        
        # 获取该类型的所有知识库（传入workspace_dir以扫描工作目录）
        kb_list = self.kb_manager.list_knowledge_bases(kb_type=storage_type, workspace_dir=self.workspace_dir)
        
        # 如果是setting类型，需要进一步根据名称或元数据区分大纲和人设
        if self.kb_type in ["outline", "character"]:
            filtered_list = []
            for kb_info in kb_list:
                # 通过元数据或名称判断具体类型
                metadata = kb_info.get('metadata', {})
                sub_type = metadata.get('sub_type', '')
                
                # 如果有sub_type元数据，使用它
                if sub_type:
                    if sub_type == self.kb_type:
                        filtered_list.append(kb_info)
                else:
                    # 兼容旧数据：通过名称关键词判断
                    name = kb_info['name'].lower()
                    if self.kb_type == "outline" and any(kw in name for kw in ['大纲', 'outline', '剧情']):
                        filtered_list.append(kb_info)
                    elif self.kb_type == "character" and any(kw in name for kw in ['人设', 'character', '角色', '人物']):
                        filtered_list.append(kb_info)
            kb_list = filtered_list
        
        if not kb_list:
            # 显示空状态
            empty_label = QtWidgets.QLabel(f"暂无{self._get_type_name()}，点击「构建新知识库」按钮创建")
            empty_label.setObjectName("EmptyLabel")
            empty_label.setAlignment(QtCore.Qt.AlignCenter)
            font = empty_label.font()
            font.setPointSize(10)
            empty_label.setFont(font)
            self.kb_list_layout.insertWidget(0, empty_label)
            return
        
        # 添加知识库项
        for kb_info in kb_list:
            is_active = (kb_info['id'] in self.active_kb_ids)  # 检查是否在激活列表中
            item_widget = KnowledgeBaseItemWidget(kb_info, is_active, self)
            item_widget.setObjectName("KBItemWidget")
            
            # 连接信号
            item_widget.activate_clicked.connect(self._on_activate_kb)
            item_widget.delete_clicked.connect(self._on_delete_kb)
            
            self.kb_list_layout.insertWidget(self.kb_list_layout.count() - 1, item_widget)
    
    def _get_type_name(self):
        """获取类型显示名称"""
        type_names = {
            "history": "历史知识库",
            "outline": "大纲知识库",
            "character": "人设知识库"
        }
        return type_names.get(self.kb_type, "知识库")
    
    def _on_create_knowledge_base(self):
        """创建知识库"""
        # 检查是否有工作目录
        if not self.workspace_dir:
            QtWidgets.QMessageBox.warning(
                self,
                "未打开工作目录",
                "请先在主窗口打开一个工作文件夹，知识库文件将存储在该目录下。"
            )
            return
        
        # 显示文件选择对话框（支持多选）
        file_paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            f"选择{self._get_type_name()}源文件",
            self.workspace_dir,  # 从工作目录开始选择
            "所有支持的文件 (*.txt *.md *.docx *.doc *.pdf *.rtf *.odt *.html *.htm *.epub);;所有文件 (*.*)"
        )
        
        if not file_paths:
            return
        
        # 输入知识库名称（默认使用第一个文件的名称）
        default_name = Path(file_paths[0]).stem if file_paths else "新知识库"
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "输入知识库名称",
            f"{self._get_type_name()}名称 (已选择 {len(file_paths)} 个文件):",
            QtWidgets.QLineEdit.Normal,
            default_name
        )
        
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        # 检查API配置
        from app.config_manager import ConfigManager
        config_manager = ConfigManager()
        api_config = config_manager.get_api_config()
        
        if not api_config.embedding_api_key:
            QtWidgets.QMessageBox.warning(
                self,
                "配置缺失",
                "请先在设置中配置阿里云向量化API密钥。"
            )
            return
        
        # 设置向量化客户端
        self.kb_manager.set_embedding_client(
            api_config.embedding_api_key,
            api_config.embedding_model
        )
        
        # 测试连接
        success, message = self.kb_manager.test_embedding_connection()
        if not success:
            reply = QtWidgets.QMessageBox.question(
                self,
                "API连接测试失败",
                f"{message}\n\n是否仍要继续创建知识库？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return
        
        # 创建进度对话框
        from app.widgets.knowledge_base_dialog import KnowledgeBaseProgressDialog
        progress_dialog = KnowledgeBaseProgressDialog(self)
        if hasattr(self, '_current_theme'):
            progress_dialog.set_theme(self._current_theme)
        
        # 在后台线程创建知识库
        from PySide6.QtCore import QThread
        
        class KBCreationWorker(QThread):
            def __init__(self, kb_manager, name, files, workspace_dir, dialog, kb_type, sub_type):
                super().__init__()
                self.kb_manager = kb_manager
                self.name = name
                self.files = files
                self.workspace_dir = workspace_dir
                self.dialog = dialog
                self.kb_type = kb_type
                self.sub_type = sub_type
                self.result = None
            
            def run(self):
                # 确定存储类型
                storage_type = "history" if self.kb_type == "history" else "setting"
                
                # 创建知识库，并在metadata中存储sub_type
                self.result = self.kb_manager.create_knowledge_base_from_files(
                    name=self.name,
                    file_paths=self.files,
                    storage_dir=self.workspace_dir,
                    chunk_size=800,
                    progress_callback=self.dialog.update_progress,
                    error_callback=self.dialog.log,
                    generate_prompts=True,
                    kb_type=storage_type
                )
                
                # 如果创建成功，更新metadata添加sub_type
                if self.result and self.sub_type:
                    self.result.metadata['sub_type'] = self.sub_type
                    # 重新保存以更新metadata
                    try:
                        self.kb_manager._save_knowledge_base(self.result, self.workspace_dir)
                    except Exception as e:
                        print(f"[WARN] 更新知识库元数据失败: {e}")
        
        worker = KBCreationWorker(
            self.kb_manager, 
            name, 
            file_paths,  # 传递文件列表而不是文件夹
            self.workspace_dir,  # 传递工作目录
            progress_dialog,
            self.kb_type,
            self.kb_type  # sub_type
        )
        worker.finished.connect(lambda: self._on_kb_creation_finished(worker, progress_dialog))
        worker.start()
        
        progress_dialog.exec()
    
    def _on_kb_creation_finished(self, worker, dialog):
        """知识库创建完成"""
        if worker.result:
            dialog.set_completed(success=True)
            
            # 生成定制化提示词
            self._generate_kb_prompts(worker.result, dialog)
            
            # 刷新列表
            self._load_knowledge_bases()
            
            QtWidgets.QMessageBox.information(
                self,
                "成功",
                f"{self._get_type_name()}创建成功！"
            )
        else:
            dialog.set_completed(success=False)
            QtWidgets.QMessageBox.critical(
                self,
                "失败",
                f"{self._get_type_name()}创建失败，请查看日志了解详情。"
            )
    
    def _generate_kb_prompts(self, kb: KnowledgeBase, progress_dialog=None):
        """为知识库生成定制化提示词
        
        注意：只为历史知识库生成提示词，大纲和人设知识库不需要生成
        """
        try:
            # 只为历史知识库生成提示词
            if kb.kb_type != "history":
                if progress_dialog:
                    progress_dialog.log("✓ 大纲/人设知识库不需要生成提示词")
                return
            
            if progress_dialog:
                progress_dialog.log("正在为历史知识库生成定制化提示词...")
            
            from app.prompt_generator import PromptGenerator
            from app.style_manager import StyleManager
            from app.config_manager import ConfigManager
            from app.config_manager import PolishStyle
            
            prompt_generator = PromptGenerator()
            config_manager = ConfigManager()
            style_manager = StyleManager(config_manager)
            
            # 1. 提取文档特征
            if progress_dialog:
                progress_dialog.log("正在分析文档特征...")
            
            features = prompt_generator.extract_features_from_documents(
                kb.documents, 
                sample_size=min(50, len(kb.documents))
            )
            
            # 2. 生成预测提示词
            if progress_dialog:
                progress_dialog.log("正在生成预测提示词...")
            
            prediction_prompt = prompt_generator.generate_prediction_prompt(kb.name, features)
            prediction_style_id = f"kb_{kb.id}_prediction"
            
            # 3. 创建并添加自定义风格
            prediction_style = PolishStyle(
                id=prediction_style_id,
                name=f"{kb.name} - 预测风格",
                prompt=prediction_prompt,
                is_preset=False,
                parameters={}
            )
            
            prediction_style_added = style_manager.add_custom_style(prediction_style)
            
            if prediction_style_added:
                # 4. 更新知识库的提示词ID
                self.kb_manager.update_kb_prompt_ids(
                    kb.id,
                    prediction_style_id=prediction_style_id
                )
                kb.prediction_style_id = prediction_style_id
                
                if progress_dialog:
                    progress_dialog.log("✓ 定制化提示词生成成功")
            else:
                if progress_dialog:
                    progress_dialog.log("⚠ 提示词风格添加失败（可能已存在）")
        
        except Exception as e:
            if progress_dialog:
                progress_dialog.log(f"⚠ 提示词生成失败: {str(e)}")
            print(f"[ERROR] 生成知识库提示词失败: {e}")
    
    def _on_activate_kb(self, kb_id: str):
        """激活/取消激活知识库（支持多选）"""
        if kb_id in self.active_kb_ids:
            # 取消激活
            self.active_kb_ids.remove(kb_id)
        else:
            # 激活新的知识库
            self.active_kb_ids.append(kb_id)
        
        # 刷新列表
        self._load_knowledge_bases()
    
    def _on_delete_kb(self, kb_id: str):
        """删除知识库"""
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除这个{self._get_type_name()}吗？\n\n此操作无法撤销。",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            success = self.kb_manager.delete_knowledge_base(kb_id)
            if success:
                # 如果删除的是激活的知识库，从激活列表中移除
                if kb_id in self.active_kb_ids:
                    self.active_kb_ids.remove(kb_id)
                
                # 刷新列表
                self._load_knowledge_bases()
                
                QtWidgets.QMessageBox.information(
                    self,
                    "成功",
                    f"{self._get_type_name()}已删除。"
                )
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "失败",
                    f"删除{self._get_type_name()}失败。"
                )
    
    def get_active_kb_ids(self) -> List[str]:
        """获取当前激活的知识库ID列表"""
        return self.active_kb_ids
    
    def set_theme(self, theme: Dict[str, str]):
        """设置主题"""
        self._current_theme = theme
        self._apply_theme()
    
    def _apply_theme(self):
        """应用主题"""
        if not self._current_theme:
            return
        
        accent = self._current_theme.get('accent', '#007acc')
        
        style_sheet = f"""
        QDialog {{
            background-color: {self._current_theme.get('editorBackground', '#1e1e1e')};
            color: {self._current_theme.get('editorForeground', '#d4d4d4')};
        }}
        
        #DialogTitle {{
            color: {self._current_theme.get('titleBarForeground', '#ffffff')};
        }}
        
        #CreateKBButton {{
            background-color: {accent};
            border: 1px solid {accent};
            border-radius: 4px;
            color: {self._current_theme.get('buttonForeground', '#ffffff')};
            padding: 8px 16px;
            font-weight: bold;
        }}
        
        #CreateKBButton:hover {{
            background-color: {self._current_theme.get('buttonHoverBackground', '#1177bb')};
        }}
        
        #Separator {{
            background-color: {self._current_theme.get('borderColor', '#3e3e42')};
        }}
        
        QGroupBox {{
            border: 1px solid {self._current_theme.get('borderColor', '#3e3e42')};
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
            font-weight: bold;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }}
        
        #KBScrollArea {{
            border: none;
            background-color: transparent;
        }}
        
        #KBItemWidget {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            border: 1px solid {self._current_theme.get('borderColor', '#3e3e42')};
            border-radius: 4px;
        }}
        
        #KBItemWidget:hover {{
            background-color: {self._current_theme.get('listHoverBackground', '#2a2d2e')};
        }}
        
        #ActiveIndicator {{
            color: {accent};
        }}
        
        #KBNameLabel {{
            color: {self._current_theme.get('editorForeground', '#d4d4d4')};
        }}
        
        #KBDetailsLabel {{
            color: {self._current_theme.get('descriptionForeground', '#858585')};
        }}
        
        #ActivateButton {{
            border-radius: 3px;
            padding: 4px 8px;
        }}

        /* 未激活 → 显示“激活”时使用积极绿色，强调动作 */
        #ActivateButton[active="false"] {{
            background-color: #4CAF50;
            border: 1px solid #4CAF50;
            color: #ffffff;
        }}
        #ActivateButton[active="false"]:hover {{
            background-color: #43A047;
        }}

        /* 已激活 → 显示“取消激活”时用中性样式，避免过度吸引注意 */
        #ActivateButton[active="true"] {{
            background-color: transparent;
            border: 1px solid {self._current_theme.get('borderColor', '#3e3e42')};
            color: {self._current_theme.get('editorForeground', '#d4d4d4')};
        }}
        #ActivateButton[active="true"]:hover {{
            background-color: {self._current_theme.get('listHoverBackground', '#2a2d2e')};
        }}
        
        #DeleteButton {{
            background-color: #d13438;
            border: 1px solid #d13438;
            border-radius: 3px;
            color: #ffffff;
            padding: 4px 8px;
        }}
        
        #DeleteButton:hover {{
            background-color: #a4262c;
            color: #ffffff;
        }}
        
        #EmptyLabel {{
            color: {self._current_theme.get('descriptionForeground', '#858585')};
        }}
        
        QPushButton {{
            background-color: {self._current_theme.get('buttonBackground', '#0e639c')};
            border: 1px solid {self._current_theme.get('buttonBorder', '#0e639c')};
            border-radius: 3px;
            color: {self._current_theme.get('buttonForeground', '#ffffff')};
            padding: 6px 14px;
        }}
        
        QPushButton:hover {{
            background-color: {self._current_theme.get('buttonHoverBackground', '#1177bb')};
        }}
        
        QPushButton:pressed {{
            background-color: {self._current_theme.get('buttonPressedBackground', '#0d5a8f')};
        }}
        """
        
        self.setStyleSheet(style_sheet)

