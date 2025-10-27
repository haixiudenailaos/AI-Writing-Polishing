"""
VSCode风格的设置对话框
包括API配置和风格管理功能
"""

from typing import Dict, List, Optional, Any
from PyQt5 import QtWidgets, QtCore, QtGui
from config_manager import ConfigManager, PolishStyle, APIConfig
from style_manager import StyleManager
from api_client import AIClient
from config_migration import ConfigMigration


class ElidedLabel(QtWidgets.QLabel):
    def __init__(self, max_chars: int = 250, parent=None):
        super().__init__(parent)
        self.max_chars = max_chars
        self.full_text = ""
        self._current_theme = None
        self.setWordWrap(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        # 缩小20%再缩小30%: 60->48->34, 100->80->56，确保行间距1.2-1.5倍字体高度
        self.setMinimumHeight(34)
        self.setMaximumHeight(56)

    def set_full_text(self, text: str):
        self.full_text = text or ""
        self.setToolTip(self.full_text)
        display_text = self._elide_text(self.full_text)
        super().setText(display_text)
        self.update()

    def _elide_text(self, text: str) -> str:
        if not text:
            return ""
        if len(text) <= self.max_chars:
            return text
        return text[: self.max_chars].rstrip() + "..."

    def paintEvent(self, event: QtGui.QPaintEvent):
        super().paintEvent(event)
        # Smooth fade overlay on the right when truncated
        if len(self.full_text) > self.max_chars:
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            w = self.width()
            h = self.height()
            # 缩小渐变宽度以适应缩小的界面
            fade_width = max(18, int(w * 0.05))
            gradient = QtGui.QLinearGradient(w - fade_width, 0, w, 0)
            
            # 使用主题背景色或默认背景色
            if self._current_theme:
                bg_color = self._current_theme.get('inputBackground', '#3c3c3c')
                bg = QtGui.QColor(bg_color)
            else:
                bg = self.palette().color(self.backgroundRole())
            
            end_color = QtGui.QColor(bg)
            end_color.setAlpha(220)
            start_color = QtGui.QColor(bg)
            start_color.setAlpha(0)
            gradient.setColorAt(0.0, start_color)
            gradient.setColorAt(1.0, end_color)
            painter.fillRect(QtCore.QRect(w - fade_width, 0, fade_width, h), QtGui.QBrush(gradient))
            painter.end()

    def set_theme(self, theme: Dict[str, str]):
        """设置主题"""
        self._current_theme = theme
        self._apply_theme()
    
    def _apply_theme(self):
        """应用主题"""
        if not self._current_theme:
            return
        
        # 应用主题样式
        style_sheet = f"""
        QLabel {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            border: 1px solid {self._current_theme.get('inputBorder', '#5a5a5a')};
            border-radius: 3px;
            padding: 6px;
            color: {self._current_theme.get('inputForeground', '#ffffff')};
        }}
        """
        
        self.setStyleSheet(style_sheet)
        self.update()


class SettingsDialog(QtWidgets.QDialog):
    """VSCode风格的设置对话框"""
    
    # 信号定义
    configChanged = QtCore.pyqtSignal()
    
    def __init__(self, config_manager: ConfigManager, style_manager: StyleManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.style_manager = style_manager
        self.migration = ConfigMigration(config_manager)
        self._current_theme = {}
        
        self.setWindowTitle("设置")
        self.setModal(True)
        # 再次缩小：640x336 -> 560x300
        self.resize(560, 300)
        
        # 创建UI
        self._setup_ui()
        self._load_current_config()
        self._connect_signals()
        
        # 应用主题
        self._apply_theme()
    
    def _setup_ui(self):
        """设置UI布局"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建标题栏
        self._create_title_bar(layout)
        
        # 创建主内容区域
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # 创建侧边栏
        self._create_sidebar(content_layout)
        
        # 创建设置面板
        self._create_settings_panel(content_layout)
        
        layout.addWidget(content_widget)
        
        # 创建底部按钮栏
        self._create_button_bar(layout)
    
    def _create_title_bar(self, parent_layout):
        """创建标题栏"""
        title_bar = QtWidgets.QFrame()
        title_bar.setObjectName("SettingsTitleBar")
        # 再次缩小：27 -> 24
        title_bar.setFixedHeight(24)
        
        title_layout = QtWidgets.QHBoxLayout(title_bar)
        # 再次缩小：16 -> 12
        title_layout.setContentsMargins(12, 0, 12, 0)
        
        # 标题
        title_label = QtWidgets.QLabel("设置")
        title_label.setObjectName("SettingsTitle")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 关闭按钮 - 再次缩小
        close_button = QtWidgets.QPushButton("×")
        close_button.setObjectName("SettingsCloseButton")
        # 缩小尺寸：44x32 -> 36x24
        close_button.setFixedSize(36, 24)
        close_button.clicked.connect(self.reject)
        title_layout.addWidget(close_button)
        
        parent_layout.addWidget(title_bar)
    
    def _create_sidebar(self, parent_layout):
        """创建侧边栏"""
        sidebar = QtWidgets.QFrame()
        sidebar.setObjectName("SettingsSidebar")
        # 再次缩小：160 -> 130
        sidebar.setFixedWidth(130)
        
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar)
        # 再次缩小：11 -> 8
        sidebar_layout.setContentsMargins(0, 8, 0, 8)
        sidebar_layout.setSpacing(1)
        
        # 设置项列表
        self.settings_list = QtWidgets.QListWidget()
        self.settings_list.setObjectName("SettingsList")
        
        # 添加设置项
        api_item = QtWidgets.QListWidgetItem("API 配置")
        api_item.setData(QtCore.Qt.UserRole, "api")
        self.settings_list.addItem(api_item)
        
        style_item = QtWidgets.QListWidgetItem("润色风格")
        style_item.setData(QtCore.Qt.UserRole, "styles")
        self.settings_list.addItem(style_item)
        
        advanced_item = QtWidgets.QListWidgetItem("高级设置")
        advanced_item.setData(QtCore.Qt.UserRole, "advanced")
        self.settings_list.addItem(advanced_item)
        
        # 默认选中第一项
        self.settings_list.setCurrentRow(0)
        
        sidebar_layout.addWidget(self.settings_list)
        sidebar_layout.addStretch()
        
        parent_layout.addWidget(sidebar)
    
    def _create_settings_panel(self, parent_layout):
        """创建设置面板"""
        # 创建堆叠窗口
        self.settings_stack = QtWidgets.QStackedWidget()
        self.settings_stack.setObjectName("SettingsStack")
        
        # API配置面板
        self._create_api_panel()
        
        # 风格管理面板
        self._create_style_panel()
        
        # 高级设置面板
        self._create_advanced_panel()
        
        parent_layout.addWidget(self.settings_stack)
    
    def _create_api_panel(self):
        """创建API配置面板"""
        panel = QtWidgets.QWidget()
        panel.setObjectName("APIPanel")
        
        layout = QtWidgets.QVBoxLayout(panel)
        # 缩小20%再缩小30%: 30->24->17
        layout.setContentsMargins(24, 17, 24, 17)
        # 缩小20%再缩小30%: 20->16->11
        layout.setSpacing(11)
        
        # 标题
        title = QtWidgets.QLabel("API 配置")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        
        # API密钥
        api_key_group = self._create_form_group("API 密钥", "输入您的AI服务API密钥")
        self.api_key_input = QtWidgets.QLineEdit()
        self.api_key_input.setObjectName("APIKeyInput")
        self.api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-...")
        # 再次缩小：22 -> 20
        self.api_key_input.setMinimumHeight(20)
        
        # 显示/隐藏密钥按钮 - 缩小
        show_key_button = QtWidgets.QPushButton("显示")
        show_key_button.setObjectName("ShowKeyButton")
        show_key_button.setCheckable(True)
        # 缩小尺寸：44x32 -> 40x26
        show_key_button.setMinimumSize(40, 26)
        show_key_button.clicked.connect(self._toggle_api_key_visibility)
        
        key_layout = QtWidgets.QHBoxLayout()
        key_layout.addWidget(self.api_key_input)
        key_layout.addWidget(show_key_button)
        
        api_key_group.layout().addLayout(key_layout)
        layout.addWidget(api_key_group)
        
        # 基础URL
        base_url_group = self._create_form_group("基础URL", "AI服务的API端点地址")
        self.base_url_input = QtWidgets.QLineEdit()
        self.base_url_input.setObjectName("BaseURLInput")
        self.base_url_input.setPlaceholderText("https://api.example.com/v1/chat/completions")
        # 再次缩小：22 -> 20
        self.base_url_input.setMinimumHeight(20)
        base_url_group.layout().addWidget(self.base_url_input)
        layout.addWidget(base_url_group)
        
        # 模型
        model_group = self._create_form_group("模型", "选择或输入AI模型名称")
        self.model_input = QtWidgets.QComboBox()
        self.model_input.setObjectName("ModelInput")
        self.model_input.setEditable(True)
        # 再次缩小：22 -> 20
        self.model_input.setMinimumHeight(20)
        
        # 预设模型列表
        models = [
            "deepseek-ai/deepseek-llm-67b-instruct",
            "Qwen/Qwen2.5-72B-Instruct",
            "meta-llama/Meta-Llama-3.1-70B-Instruct",
            "gpt-3.5-turbo",
            "gpt-4",
            "claude-3-sonnet"
        ]
        self.model_input.addItems(models)
        model_group.layout().addWidget(self.model_input)
        layout.addWidget(model_group)
        
        # 测试连接按钮
        test_layout = QtWidgets.QHBoxLayout()
        self.test_button = QtWidgets.QPushButton("测试连接")
        self.test_button.setObjectName("TestButton")
        # 缩小尺寸：44x32 -> 40x26
        self.test_button.setMinimumSize(40, 26)
        self.test_button.clicked.connect(self._test_api_connection)
        
        self.test_status_label = QtWidgets.QLabel("")
        self.test_status_label.setObjectName("TestStatusLabel")
        
        test_layout.addWidget(self.test_button)
        test_layout.addWidget(self.test_status_label)
        test_layout.addStretch()
        
        layout.addLayout(test_layout)
        layout.addStretch()
        
        self.settings_stack.addWidget(panel)
    
    def _create_style_panel(self):
        """创建风格管理面板"""
        panel = QtWidgets.QWidget()
        panel.setObjectName("StylePanel")
        
        layout = QtWidgets.QVBoxLayout(panel)
        # 再次缩小：17 -> 12
        layout.setContentsMargins(16, 12, 16, 12)
        # 再次缩小：11 -> 8
        layout.setSpacing(8)
        
        # 标题
        title = QtWidgets.QLabel("润色风格")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        
        # 风格选择区域（带滚动）
        style_selection_group = self._create_form_group("选择风格", "可以选择多个风格进行组合")
        
        # 创建滚动区域
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setObjectName("StyleScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setMinimumHeight(150)  # 确保有足够的高度显示内容
        
        # 创建滚动内容容器
        scroll_content = QtWidgets.QWidget()
        scroll_content_layout = QtWidgets.QVBoxLayout(scroll_content)
        scroll_content_layout.setContentsMargins(0, 0, 0, 0)
        scroll_content_layout.setSpacing(4)
        
        # 预设风格
        preset_label = QtWidgets.QLabel("预设风格:")
        preset_label.setObjectName("StyleSectionLabel")
        scroll_content_layout.addWidget(preset_label)
        
        self.preset_styles_widget = QtWidgets.QWidget()
        self.preset_styles_layout = QtWidgets.QVBoxLayout(self.preset_styles_widget)
        # 再次缩小：11 -> 8
        self.preset_styles_layout.setContentsMargins(8, 0, 0, 0)
        self.preset_styles_layout.setSpacing(2)
        scroll_content_layout.addWidget(self.preset_styles_widget)
        
        # 自定义风格
        custom_label = QtWidgets.QLabel("自定义风格:")
        custom_label.setObjectName("StyleSectionLabel")
        scroll_content_layout.addWidget(custom_label)
        
        self.custom_styles_widget = QtWidgets.QWidget()
        self.custom_styles_layout = QtWidgets.QVBoxLayout(self.custom_styles_widget)
        # 再次缩小：11 -> 8
        self.custom_styles_layout.setContentsMargins(8, 0, 0, 0)
        self.custom_styles_layout.setSpacing(2)
        scroll_content_layout.addWidget(self.custom_styles_widget)
        
        scroll_content_layout.addStretch()
        
        # 设置滚动区域内容
        scroll_area.setWidget(scroll_content)
        style_selection_group.layout().addWidget(scroll_area)
        
        layout.addWidget(style_selection_group)
        
        # 自定义风格管理
        custom_management_group = self._create_form_group("自定义风格管理", "创建和管理您的自定义风格")
        
        # 新建风格按钮 - 缩小
        new_style_button = QtWidgets.QPushButton("新建风格")
        new_style_button.setObjectName("NewStyleButton")
        # 缩小尺寸：44x32 -> 40x26
        new_style_button.setMinimumSize(40, 26)
        new_style_button.clicked.connect(self._create_new_style)
        custom_management_group.layout().addWidget(new_style_button)
        
        layout.addWidget(custom_management_group)
        
        # 风格预览（带滚动）
        preview_group = self._create_form_group("风格预览", "当前选中风格的组合效果")
        
        # 创建预览滚动区域
        preview_scroll = QtWidgets.QScrollArea()
        preview_scroll.setObjectName("PreviewScrollArea")
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        preview_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        # 缩小高度：80-120 -> 60-100
        preview_scroll.setMinimumHeight(60)
        preview_scroll.setMaximumHeight(100)
        
        # 创建预览标签容器
        preview_container = QtWidgets.QWidget()
        preview_container_layout = QtWidgets.QVBoxLayout(preview_container)
        preview_container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.style_preview_label = QtWidgets.QLabel("未选择风格")
        self.style_preview_label.setObjectName("StylePreviewLabel")
        self.style_preview_label.setWordWrap(True)
        self.style_preview_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        preview_container_layout.addWidget(self.style_preview_label)
        preview_container_layout.addStretch()
        
        preview_scroll.setWidget(preview_container)
        preview_group.layout().addWidget(preview_scroll)
        layout.addWidget(preview_group)
        
        layout.addStretch()
        
        self.settings_stack.addWidget(panel)
    
    def _create_advanced_panel(self):
        """创建高级设置面板"""
        panel = QtWidgets.QWidget()
        panel.setObjectName("AdvancedPanel")
        
        layout = QtWidgets.QVBoxLayout(panel)
        # 再次缩小：17 -> 12
        layout.setContentsMargins(16, 12, 16, 12)
        # 再次缩小：11 -> 8
        layout.setSpacing(8)
        
        # 标题
        title = QtWidgets.QLabel("高级设置")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        
        # 配置迁移
        migration_group = self._create_form_group("配置迁移", "从环境变量迁移配置到JSON文件")
        
        migration_info = QtWidgets.QLabel("如果您之前使用环境变量配置API密钥，可以点击下面的按钮将配置迁移到JSON文件中。")
        migration_info.setObjectName("MigrationInfo")
        migration_info.setWordWrap(True)
        migration_group.layout().addWidget(migration_info)
        
        migration_warning = QtWidgets.QLabel("⚠️ 迁移操作会将环境变量中的配置复制到配置文件中，请确认后再执行。")
        migration_warning.setObjectName("MigrationWarning")
        migration_warning.setWordWrap(True)
        migration_warning.setStyleSheet("color: orange; font-weight: bold;")
        migration_group.layout().addWidget(migration_warning)
        
        migrate_button = QtWidgets.QPushButton("迁移配置")
        migrate_button.setObjectName("MigrateButton")
        # 缩小尺寸：44x32 -> 40x26
        migrate_button.setMinimumSize(40, 26)
        migrate_button.clicked.connect(self._migrate_config)
        migration_group.layout().addWidget(migrate_button)
        
        layout.addWidget(migration_group)
        
        # 配置备份与恢复
        backup_group = self._create_form_group("配置备份", "备份和恢复您的配置")
        
        backup_layout = QtWidgets.QHBoxLayout()
        
        backup_button = QtWidgets.QPushButton("备份配置")
        backup_button.setObjectName("BackupButton")
        # 缩小尺寸：44x32 -> 40x26
        backup_button.setMinimumSize(40, 26)
        backup_button.clicked.connect(self._backup_config)
        
        restore_button = QtWidgets.QPushButton("恢复配置")
        restore_button.setObjectName("RestoreButton")
        # 缩小尺寸：44x32 -> 40x26
        restore_button.setMinimumSize(40, 26)
        restore_button.clicked.connect(self._restore_config)
        
        backup_layout.addWidget(backup_button)
        backup_layout.addWidget(restore_button)
        backup_layout.addStretch()
        
        backup_group.layout().addLayout(backup_layout)
        layout.addWidget(backup_group)
        
        # 重置设置
        reset_group = self._create_form_group("重置设置", "将所有设置恢复为默认值")
        
        reset_warning = QtWidgets.QLabel("⚠️ 此操作将删除所有自定义配置，包括API密钥和自定义风格。")
        reset_warning.setObjectName("ResetWarning")
        reset_warning.setWordWrap(True)
        reset_group.layout().addWidget(reset_warning)
        
        reset_button = QtWidgets.QPushButton("重置所有设置")
        reset_button.setObjectName("ResetButton")
        # 缩小尺寸：44x32 -> 40x26
        reset_button.setMinimumSize(40, 26)
        reset_button.clicked.connect(self._reset_all_settings)
        reset_group.layout().addWidget(reset_button)
        
        layout.addWidget(reset_group)
        layout.addStretch()
        
        self.settings_stack.addWidget(panel)
    
    def _create_form_group(self, title: str, description: str = "") -> QtWidgets.QGroupBox:
        """创建表单组"""
        group = QtWidgets.QGroupBox(title)
        group.setObjectName("FormGroup")
        
        layout = QtWidgets.QVBoxLayout(group)
        # 缩小间距：12,16,12,12 -> 8,12,8,8
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)
        
        if description:
            desc_label = QtWidgets.QLabel(description)
            desc_label.setObjectName("FormDescription")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        return group
    
    def _create_button_bar(self, parent_layout):
        """创建底部按钮栏"""
        button_bar = QtWidgets.QFrame()
        button_bar.setObjectName("SettingsButtonBar")
        # 再次缩小：34 -> 28
        button_bar.setFixedHeight(48)
        
        button_layout = QtWidgets.QHBoxLayout(button_bar)
        # 优化间距：提供更好的视觉效果
        button_layout.setContentsMargins(20, 8, 20, 8)
        
        button_layout.addStretch()
        
        # 取消按钮
        cancel_button = QtWidgets.QPushButton("取消")
        cancel_button.setObjectName("CancelButton")
        # 优化尺寸：更合理的按钮大小
        cancel_button.setMinimumSize(70, 32)
        cancel_button.setMaximumSize(90, 32)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        # 添加按钮间距
        button_layout.addSpacing(8)
        
        # 应用按钮
        apply_button = QtWidgets.QPushButton("应用")
        apply_button.setObjectName("ApplyButton")
        # 优化尺寸：更合理的按钮大小
        apply_button.setMinimumSize(70, 32)
        apply_button.setMaximumSize(90, 32)
        apply_button.clicked.connect(self._apply_settings)
        button_layout.addWidget(apply_button)
        
        # 添加按钮间距
        button_layout.addSpacing(8)
        
        # 确定按钮
        ok_button = QtWidgets.QPushButton("确定")
        ok_button.setObjectName("OKButton")
        # 优化尺寸：更合理的按钮大小
        ok_button.setMinimumSize(70, 32)
        ok_button.setMaximumSize(90, 32)
        ok_button.clicked.connect(self._save_and_close)
        button_layout.addWidget(ok_button)
        
        parent_layout.addWidget(button_bar)
    
    def _connect_signals(self):
        """连接信号"""
        self.settings_list.currentRowChanged.connect(self.settings_stack.setCurrentIndex)
        
        # API配置变化信号
        self.api_key_input.textChanged.connect(self._on_config_changed)
        self.base_url_input.textChanged.connect(self._on_config_changed)
        self.model_input.currentTextChanged.connect(self._on_config_changed)
    
    def _load_current_config(self):
        """加载当前配置"""
        # 加载API配置
        api_config = self.config_manager.get_api_config()
        self.api_key_input.setText(api_config.api_key or "")
        self.base_url_input.setText(api_config.base_url or "")
        
        # 设置模型
        model_text = api_config.model or ""
        index = self.model_input.findText(model_text)
        if index >= 0:
            self.model_input.setCurrentIndex(index)
        else:
            self.model_input.setCurrentText(model_text)
        
        # 加载风格配置
        self._load_style_config()
    
    def _load_style_config(self):
        """加载风格配置"""
        # 清除现有的风格选择框
        self._clear_style_widgets()
        
        # 加载预设风格
        preset_styles = self.style_manager.get_preset_styles()
        selected_styles = [style.id for style in self.style_manager.get_selected_styles()]
        
        self.preset_checkboxes = {}
        for style in preset_styles:
            checkbox = QtWidgets.QCheckBox(f"{style.name}")
            checkbox.setObjectName("StyleCheckbox")
            checkbox.setChecked(style.id in selected_styles)
            checkbox.setToolTip(style.prompt or "")
            checkbox.stateChanged.connect(self._on_style_selection_changed)
            
            self.preset_checkboxes[style.id] = checkbox
            self.preset_styles_layout.addWidget(checkbox)
        
        # 加载自定义风格
        custom_styles = self.style_manager.get_custom_styles()
        self.custom_checkboxes = {}
        
        for style in custom_styles:
            style_widget = self._create_custom_style_widget(style, style.id in selected_styles)
            self.custom_styles_layout.addWidget(style_widget)
        
        # 更新风格预览
        self._update_style_preview()
    
    def _create_custom_style_widget(self, style: PolishStyle, checked: bool) -> QtWidgets.QWidget:
        """创建自定义风格控件"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        checkbox = QtWidgets.QCheckBox(style.name)
        checkbox.setObjectName("StyleCheckbox")
        checkbox.setChecked(checked)
        checkbox.setToolTip(style.prompt or "")
        checkbox.stateChanged.connect(self._on_style_selection_changed)
        
        edit_button = QtWidgets.QPushButton("编辑")
        edit_button.setObjectName("EditStyleButton")
        edit_button.clicked.connect(lambda: self._edit_custom_style(style))
        
        delete_button = QtWidgets.QPushButton("删除")
        delete_button.setObjectName("DeleteStyleButton")
        delete_button.clicked.connect(lambda: self._delete_custom_style(style.id))
        
        layout.addWidget(checkbox)
        layout.addStretch()
        layout.addWidget(edit_button)
        layout.addWidget(delete_button)
        
        self.custom_checkboxes[style.id] = checkbox
        
        return widget
    
    def _clear_style_widgets(self):
        """清除风格控件"""
        # 清除预设风格
        while self.preset_styles_layout.count():
            child = self.preset_styles_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # 清除自定义风格
        while self.custom_styles_layout.count():
            child = self.custom_styles_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.preset_checkboxes = {}
        self.custom_checkboxes = {}
    
    def _toggle_api_key_visibility(self, checked: bool):
        """切换API密钥显示/隐藏"""
        if checked:
            self.api_key_input.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.sender().setText("隐藏")
        else:
            self.api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
            self.sender().setText("显示")
    
    def _test_api_connection(self):
        """测试API连接"""
        self.test_button.setEnabled(False)
        self.test_status_label.setText("测试中...")
        
        # 创建临时API客户端进行测试
        api_key = self.api_key_input.text().strip()
        base_url = self.base_url_input.text().strip()
        model = self.model_input.currentText().strip()
        
        if not api_key:
            self.test_status_label.setText("❌ 请输入API密钥")
            self.test_button.setEnabled(True)
            return
        
        try:
            client = AIClient(
                api_key=api_key,
                base_url=base_url or None,
                model=model or None
            )
            
            # 在新线程中测试连接
            self._test_worker = TestConnectionWorker(client)
            self._test_worker.finished.connect(self._on_test_finished)
            self._test_worker.start()
            
        except Exception as e:
            self.test_status_label.setText(f"❌ 测试失败: {str(e)}")
            self.test_button.setEnabled(True)
    
    def _on_test_finished(self, result: Dict[str, Any]):
        """测试完成回调"""
        if result["success"]:
            self.test_status_label.setText("✅ 连接成功")
        else:
            self.test_status_label.setText(f"❌ {result['message']}")
        
        self.test_button.setEnabled(True)
    
    def _on_config_changed(self):
        """配置变化回调"""
        # 清除测试状态
        self.test_status_label.setText("")
    
    def _on_style_selection_changed(self):
        """风格选择变化回调"""
        self._update_style_preview()
    
    def _update_style_preview(self):
        """更新风格预览"""
        selected_style_ids = []
        
        # 收集选中的预设风格
        for style_id, checkbox in self.preset_checkboxes.items():
            if checkbox.isChecked():
                selected_style_ids.append(style_id)
        
        # 收集选中的自定义风格
        for style_id, checkbox in self.custom_checkboxes.items():
            if checkbox.isChecked():
                selected_style_ids.append(style_id)
        
        if not selected_style_ids:
            self.style_preview_label.setText("未选择风格")
            return
        
        # 获取选中的风格
        selected_styles = []
        for style_id in selected_style_ids:
            style = self.style_manager.get_style_by_id(style_id)
            if style:
                selected_styles.append(style)
        
        # 生成预览文本
        if selected_styles:
            combined_prompt = self.style_manager.get_combined_prompt(selected_styles)
            self.style_preview_label.setText(f"组合效果：{combined_prompt}")
        else:
            self.style_preview_label.setText("未选择风格")
    
    def _create_new_style(self):
        """创建新风格"""
        dialog = StyleEditDialog(parent=self)
        # 传递当前主题给StyleEditDialog
        if self._current_theme:
            dialog.set_theme(self._current_theme)
        # 为ElidedLabel设置主题
        if hasattr(dialog, 'prompt_preview') and self._current_theme:
            dialog.prompt_preview.set_theme(self._current_theme)
        
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            style_data = dialog.get_style_data()
            style = PolishStyle(**style_data)
            
            if self.style_manager.add_custom_style(style):
                self._load_style_config()
                QtWidgets.QMessageBox.information(self, "成功", "风格创建成功！")
            else:
                QtWidgets.QMessageBox.warning(self, "错误", "风格创建失败，可能是ID已存在。")
    
    def _edit_custom_style(self, style: PolishStyle):
        """编辑自定义风格"""
        dialog = StyleEditDialog(style, parent=self)
        # 传递当前主题给StyleEditDialog
        if self._current_theme:
            dialog.set_theme(self._current_theme)
        # 为ElidedLabel设置主题
        if hasattr(dialog, 'prompt_preview') and self._current_theme:
            dialog.prompt_preview.set_theme(self._current_theme)
        
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            style_data = dialog.get_style_data()
            updated_style = PolishStyle(**style_data)
            
            if self.style_manager.update_custom_style(updated_style):
                self._load_style_config()
                QtWidgets.QMessageBox.information(self, "成功", "风格更新成功！")
            else:
                QtWidgets.QMessageBox.warning(self, "错误", "风格更新失败。")
    
    def _delete_custom_style(self, style_id: str):
        """删除自定义风格"""
        reply = QtWidgets.QMessageBox.question(
            self, "确认删除", 
            "确定要删除这个自定义风格吗？此操作不可撤销。",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            if self.style_manager.delete_custom_style(style_id):
                self._load_style_config()
                QtWidgets.QMessageBox.information(self, "成功", "风格删除成功！")
            else:
                QtWidgets.QMessageBox.warning(self, "错误", "风格删除失败。")
    
    def _check_migration_on_startup(self):
        """启动时检查是否需要迁移"""
        migration_info = self.migration.check_migration_needed()
        
        if migration_info["needs_migration"]:
            # 显示迁移提示
            self._show_migration_dialog(migration_info)
    
    def _show_migration_dialog(self, migration_info: Dict[str, Any]):
        """显示迁移对话框"""
        dialog = MigrationDialog(migration_info, self.migration, parent=self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            # 迁移完成后重新加载配置
            self._load_current_config()

    def _migrate_config(self):
        """迁移配置"""
        try:
            # 首先显示确认对话框
            reply = QtWidgets.QMessageBox.question(
                self, 
                "确认迁移配置", 
                "您确定要将环境变量中的配置迁移到配置文件中吗？\n\n"
                "此操作将：\n"
                "• 检查环境变量中的API配置\n"
                "• 将找到的配置复制到JSON配置文件\n"
                "• 不会删除环境变量\n\n"
                "是否继续？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply != QtWidgets.QMessageBox.Yes:
                return
            
            migration_info = self.migration.check_migration_needed()
            
            if not migration_info["needs_migration"]:
                QtWidgets.QMessageBox.information(self, "提示", "没有找到需要迁移的配置。")
                return
            
            # 显示详细的迁移对话框
            dialog = MigrationDialog(migration_info, self.migration, parent=self)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                self._load_current_config()
                
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "错误", f"配置迁移失败：{str(e)}")
    
    def _backup_config(self):
        """备份配置"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "备份配置", "config_backup.json", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                if self.config_manager.backup_config(file_path):
                    QtWidgets.QMessageBox.information(self, "成功", "配置备份成功！")
                else:
                    QtWidgets.QMessageBox.warning(self, "错误", "配置备份失败。")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "错误", f"配置备份失败：{str(e)}")
    
    def _restore_config(self):
        """恢复配置"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "恢复配置", "", "JSON Files (*.json)"
        )
        
        if file_path:
            reply = QtWidgets.QMessageBox.question(
                self, "确认恢复", 
                "恢复配置将覆盖当前所有设置，确定继续吗？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                try:
                    if self.config_manager.restore_config(file_path):
                        self._load_current_config()
                        QtWidgets.QMessageBox.information(self, "成功", "配置恢复成功！")
                    else:
                        QtWidgets.QMessageBox.warning(self, "错误", "配置恢复失败。")
                except Exception as e:
                    QtWidgets.QMessageBox.warning(self, "错误", f"配置恢复失败：{str(e)}")
    
    def _reset_all_settings(self):
        """重置所有设置"""
        reply = QtWidgets.QMessageBox.question(
            self, "确认重置", 
            "此操作将删除所有配置，包括API密钥和自定义风格。确定继续吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                self.config_manager.reset_to_defaults()
                self._load_current_config()
                QtWidgets.QMessageBox.information(self, "成功", "设置已重置为默认值！")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "错误", f"重置失败：{str(e)}")
    
    def _apply_settings(self):
        """应用设置"""
        try:
            # 保存API配置
            self.config_manager.update_api_config(
                api_key=self.api_key_input.text().strip(),
                base_url=self.base_url_input.text().strip(),
                model=self.model_input.currentText().strip()
            )
            
            # 保存风格选择
            selected_style_ids = []
            
            for style_id, checkbox in self.preset_checkboxes.items():
                if checkbox.isChecked():
                    selected_style_ids.append(style_id)
            
            for style_id, checkbox in self.custom_checkboxes.items():
                if checkbox.isChecked():
                    selected_style_ids.append(style_id)
            
            self.style_manager.set_selected_styles(selected_style_ids)
            
            # 发出配置变化信号
            self.configChanged.emit()
            
            QtWidgets.QMessageBox.information(self, "成功", "设置已保存！")
            
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "错误", f"保存设置失败：{str(e)}")
    
    def _save_and_close(self):
        """保存并关闭"""
        self._apply_settings()
        self.accept()
    
    def set_theme(self, theme: Dict[str, str]):
        """设置主题"""
        self._current_theme = theme
        self._apply_theme()
    
    def _apply_theme(self):
        """应用主题"""
        if not self._current_theme:
            return
        
        # 应用主题样式
        style_sheet = f"""
        QDialog {{
            background-color: {self._current_theme.get('editorBackground', '#1e1e1e')};
            color: {self._current_theme.get('editorForeground', '#ffffff')};
        }}
        
        #SettingsTitleBar {{
            background-color: {self._current_theme.get('titleBarBackground', '#2d2d30')};
            border-bottom: 1px solid {self._current_theme.get('borderColor', '#3e3e42')};
        }}
        
        #SettingsTitle {{
            font-size: 16px;
            font-weight: bold;
            color: {self._current_theme.get('titleBarForeground', '#ffffff')};
        }}
        
        #SettingsSidebar {{
            background-color: {self._current_theme.get('sidebarBackground', '#252526')};
            border-right: 1px solid {self._current_theme.get('borderColor', '#3e3e42')};
        }}
        
        #SettingsList {{
            background-color: transparent;
            border: none;
            outline: none;
        }}
        
        #SettingsList::item {{
            padding: 8px 16px;
            border: none;
            color: {self._current_theme.get('sidebarForeground', '#ffffff')};
        }}
        
        #SettingsList::item:selected {{
            background-color: {self._current_theme.get('listActiveSelectionBackground', '#094771')};
            color: {self._current_theme.get('listActiveSelectionForeground', '#ffffff')};
        }}
        
        #PanelTitle {{
            font-size: 20px;
            font-weight: bold;
            color: {self._current_theme.get('editorForeground', '#ffffff')};
            margin-bottom: 10px;
        }}
        
        QGroupBox {{
            font-weight: bold;
            border: 1px solid {self._current_theme.get('borderColor', '#3e3e42')};
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
            color: {self._current_theme.get('editorForeground', '#ffffff')};
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px 0 4px;
            color: {self._current_theme.get('editorForeground', '#ffffff')};
        }}
        
        QLabel {{
            color: {self._current_theme.get('editorForeground', '#ffffff')};
        }}
        
        QLineEdit, QComboBox {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            border: 1px solid {self._current_theme.get('inputBorder', '#5a5a5a')};
            border-radius: 3px;
            padding: 6px;
            color: {self._current_theme.get('inputForeground', '#ffffff')};
        }}
        
        QLineEdit:focus, QComboBox:focus {{
            border-color: {self._current_theme.get('focusBorder', '#007acc')};
        }}
        
        QPushButton {{
            background-color: {self._current_theme.get('buttonBackground', '#0e639c')};
            border: 1px solid {self._current_theme.get('buttonBorder', '#0e639c')};
            border-radius: 3px;
            padding: 6px 12px;
            color: {self._current_theme.get('buttonForeground', '#ffffff')};
        }}
        
        QPushButton:hover {{
            background-color: {self._current_theme.get('buttonHoverBackground', '#1177bb')};
        }}
        
        QPushButton:pressed {{
            background-color: {self._current_theme.get('buttonActiveBackground', '#0d5a9a')};
        }}
        
        QPushButton:disabled {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            color: {self._current_theme.get('mutedForeground', '#6c6c6c')};
            border-color: {self._current_theme.get('inputBorder', '#5a5a5a')};
        }}
        
        QCheckBox {{
            color: {self._current_theme.get('editorForeground', '#ffffff')};
        }}
        
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {self._current_theme.get('inputBorder', '#5a5a5a')};
            border-radius: 3px;
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
        }}
        
        QCheckBox::indicator:checked {{
            background-color: {self._current_theme.get('buttonBackground', '#0e639c')};
            border-color: {self._current_theme.get('buttonBorder', '#0e639c')};
        }}
        
        QCheckBox::indicator:hover {{
            border-color: {self._current_theme.get('focusBorder', '#007acc')};
        }}
        
        QComboBox::drop-down {{
            border: none;
            background-color: {self._current_theme.get('buttonBackground', '#0e639c')};
        }}
        
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 4px solid {self._current_theme.get('buttonForeground', '#ffffff')};
            margin: 0px;
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            border: 1px solid {self._current_theme.get('inputBorder', '#5a5a5a')};
            selection-background-color: {self._current_theme.get('listActiveSelectionBackground', '#094771')};
            color: {self._current_theme.get('inputForeground', '#ffffff')};
        }}
        
        #SettingsCloseButton {{
            background-color: transparent;
            border: none;
            color: {self._current_theme.get('titleBarForeground', '#ffffff')};
            font-size: 18px;
            font-weight: bold;
        }}
        
        #SettingsCloseButton:hover {{
            background-color: {self._current_theme.get('buttonHoverBackground', '#1177bb')};
        }}
        
        #SettingsCloseButton:pressed {{
            background-color: {self._current_theme.get('buttonActiveBackground', '#0d5a9a')};
        }}
        
        QTextEdit {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            border: 1px solid {self._current_theme.get('inputBorder', '#5a5a5a')};
            border-radius: 3px;
            color: {self._current_theme.get('inputForeground', '#ffffff')};
        }}
        
        QScrollArea {{
            background-color: transparent;
            border: none;
        }}
        
        QScrollArea > QWidget > QWidget {{
            background-color: transparent;
        }}
        
        QScrollBar:vertical {{
            background-color: {self._current_theme.get('scrollbarBackground', '#2e2e2e')};
            width: 12px;
            border: none;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {self._current_theme.get('scrollbarSlider', '#5a5a5a')};
            border-radius: 6px;
            min-height: 30px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {self._current_theme.get('scrollbarSliderHover', '#6e6e6e')};
        }}
        
        QScrollBar::handle:vertical:pressed {{
            background-color: {self._current_theme.get('scrollbarSliderActive', '#7e7e7e')};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        
        #StyleScrollArea {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            border: 1px solid {self._current_theme.get('inputBorder', '#5a5a5a')};
            border-radius: 3px;
        }}
        
        #PreviewScrollArea {{
            background-color: transparent;
            border: none;
        }}
        
        #StylePreviewLabel {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            border: 1px solid {self._current_theme.get('inputBorder', '#5a5a5a')};
            border-radius: 3px;
            padding: 6px;
            color: {self._current_theme.get('inputForeground', '#ffffff')};
        }}
        
        #SettingsButtonBar {{
            background-color: {self._current_theme.get('editorBackground', '#1e1e1e')};
            border-top: 1px solid {self._current_theme.get('borderColor', '#3e3e42')};
        }}
        
        /* 底部按钮栏专用样式 */
        #CancelButton {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            border: 1px solid {self._current_theme.get('inputBorder', '#5a5a5a')};
            border-radius: 4px;
            padding: 8px 16px;
            color: {self._current_theme.get('editorForeground', '#ffffff')};
            font-weight: 500;
            min-width: 60px;
        }}
        
        #CancelButton:hover {{
            background-color: {self._current_theme.get('listHoverBackground', '#2a2d2e')};
            border-color: {self._current_theme.get('focusBorder', '#007acc')};
        }}
        
        #CancelButton:pressed {{
            background-color: {self._current_theme.get('listActiveSelectionBackground', '#094771')};
        }}
        
        #ApplyButton {{
            background-color: {self._current_theme.get('buttonBackground', '#0e639c')};
            border: 1px solid {self._current_theme.get('buttonBorder', '#0e639c')};
            border-radius: 4px;
            padding: 8px 16px;
            color: {self._current_theme.get('buttonForeground', '#ffffff')};
            font-weight: 500;
            min-width: 60px;
        }}
        
        #ApplyButton:hover {{
            background-color: {self._current_theme.get('buttonHoverBackground', '#1177bb')};
        }}
        
        #ApplyButton:pressed {{
            background-color: {self._current_theme.get('buttonActiveBackground', '#0d5a9a')};
        }}
        
        #ApplyButton:disabled {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            color: {self._current_theme.get('mutedForeground', '#6c6c6c')};
            border-color: {self._current_theme.get('inputBorder', '#5a5a5a')};
        }}
        
        #OKButton {{
            background-color: #28a745;
            border: 1px solid #28a745;
            border-radius: 4px;
            padding: 8px 16px;
            color: #ffffff;
            font-weight: 500;
            min-width: 60px;
        }}
        
        #OKButton:hover {{
            background-color: #218838;
            border-color: #1e7e34;
        }}
        
        #OKButton:pressed {{
            background-color: #1e7e34;
        }}
        
        #OKButton:disabled {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            color: {self._current_theme.get('mutedForeground', '#6c6c6c')};
            border-color: {self._current_theme.get('inputBorder', '#5a5a5a')};
        }}
        """
        
        self.setStyleSheet(style_sheet)


class StyleEditDialog(QtWidgets.QDialog):
    """风格编辑对话框"""
    
    def __init__(self, style: Optional[PolishStyle] = None, parent=None):
        super().__init__(parent)
        self.style = style
        self._current_theme = None
        self.setWindowTitle("编辑风格" if style else "新建风格")
        self.setModal(True)
        # 缩小30%: 320 -> 224
        self.resize(400, 224)
        
        self._setup_ui()
        if style:
            self._load_style_data()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 风格名称
        name_layout = QtWidgets.QHBoxLayout()
        name_layout.addWidget(QtWidgets.QLabel("名称:"))
        self.name_input = QtWidgets.QLineEdit()
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # 风格ID
        id_layout = QtWidgets.QHBoxLayout()
        id_layout.addWidget(QtWidgets.QLabel("ID:"))
        self.id_input = QtWidgets.QLineEdit()
        self.id_input.setPlaceholderText("唯一标识符，如：custom_elegant")
        id_layout.addWidget(self.id_input)
        layout.addLayout(id_layout)
        
        # 提示词
        layout.addWidget(QtWidgets.QLabel("提示词:"))
        self.prompt_input = QtWidgets.QTextEdit()
        self.prompt_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        # 缩小30%: 96->67
        self.prompt_input.setFixedHeight(67)
        layout.addWidget(self.prompt_input)

        # 提示词预览（截断显示 + 悬浮提示）
        layout.addWidget(QtWidgets.QLabel("提示词预览:"))
        self.prompt_preview = ElidedLabel(max_chars=280)
        self.prompt_preview.setObjectName("PromptPreviewLabel")
        layout.addWidget(self.prompt_preview)
        self.prompt_input.textChanged.connect(self._update_prompt_preview)

        # 优化提示词
        opt_layout = QtWidgets.QHBoxLayout()
        self.optimize_button = QtWidgets.QPushButton("优化当前提示词")
        self.optimize_button.setObjectName("OptimizePromptButton")
        self.optimize_button.setMinimumSize(44, 32)
        self.optimize_button.clicked.connect(self._optimize_prompt)
        self.optimize_status = QtWidgets.QLabel("")
        self.optimize_status.setObjectName("OptimizeStatusLabel")
        opt_layout.addWidget(self.optimize_button)
        opt_layout.addWidget(self.optimize_status)
        opt_layout.addStretch()
        layout.addLayout(opt_layout)
        
        # 按钮
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QtWidgets.QPushButton("取消")
        cancel_button.setMinimumSize(44, 32)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        ok_button = QtWidgets.QPushButton("确定")
        ok_button.setMinimumSize(44, 32)
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        layout.addLayout(button_layout)
    
    def _load_style_data(self):
        """加载风格数据"""
        if self.style:
            self.name_input.setText(self.style.name)
            self.id_input.setText(self.style.id)
            self.prompt_input.setPlainText(self.style.prompt or "")
            self._update_prompt_preview()
            
            # 编辑模式下ID不可修改
            self.id_input.setReadOnly(True)
    
    def _update_prompt_preview(self):
        text = self.prompt_input.toPlainText()
        self.prompt_preview.set_full_text(text)
    
    def get_style_data(self) -> Dict[str, Any]:
        """获取风格数据"""
        return {
            "id": self.id_input.text().strip(),
            "name": self.name_input.text().strip(),
            "prompt": self.prompt_input.toPlainText().strip(),
            "is_preset": False,
            "parameters": {}
        }

    def _optimize_prompt(self):
        """调用AI优化当前提示词"""
        prompt_text = self.prompt_input.toPlainText().strip()
        if not prompt_text:
            QtWidgets.QMessageBox.warning(self, "提示", "请先输入提示词。")
            return
        # 获取配置管理器
        cm = None
        parent = self.parent()
        if parent and hasattr(parent, "config_manager"):
            cm = parent.config_manager
        # 禁用按钮并显示状态
        self.optimize_button.setEnabled(False)
        self.optimize_status.setText("优化中…")
        try:
            client = AIClient(config_manager=cm) if cm else AIClient()
            self._opt_worker = OptimizePromptWorker(client, prompt_text)
            self._opt_worker.finished.connect(self._on_optimize_finished)
            self._opt_worker.start()
        except Exception as e:
            self.optimize_status.setText(f"❌ 失败: {str(e)}")
            self.optimize_button.setEnabled(True)

    def _on_optimize_finished(self, result: Dict[str, Any]):
        """优化完成回调"""
        self.optimize_button.setEnabled(True)
        if result.get("success"):
            optimized = result.get("optimized", "")
            if optimized:
                self.prompt_input.setPlainText(optimized)
            self.optimize_status.setText("✅ 已优化")
        else:
            self.optimize_status.setText(f"❌ {result.get('message', '优化失败')}" )

    def set_theme(self, theme: Dict[str, str]):
        """设置主题"""
        self._current_theme = theme
        self._apply_theme()
    
    def _apply_theme(self):
        """应用主题"""
        if not self._current_theme:
            return
        
        # 应用主题样式
        style_sheet = f"""
        QDialog {{
            background-color: {self._current_theme.get('editorBackground', '#1e1e1e')};
            color: {self._current_theme.get('editorForeground', '#ffffff')};
        }}
        
        QLabel {{
            color: {self._current_theme.get('editorForeground', '#ffffff')};
        }}
        
        QLineEdit {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            border: 1px solid {self._current_theme.get('inputBorder', '#5a5a5a')};
            border-radius: 3px;
            padding: 6px;
            color: {self._current_theme.get('inputForeground', '#ffffff')};
        }}
        
        QLineEdit:focus {{
            border-color: {self._current_theme.get('focusBorder', '#007acc')};
        }}
        
        QTextEdit {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            border: 1px solid {self._current_theme.get('inputBorder', '#5a5a5a')};
            border-radius: 3px;
            color: {self._current_theme.get('inputForeground', '#ffffff')};
        }}
        
        QTextEdit:focus {{
            border-color: {self._current_theme.get('focusBorder', '#007acc')};
        }}
        
        QPushButton {{
            background-color: {self._current_theme.get('buttonBackground', '#0e639c')};
            border: 1px solid {self._current_theme.get('buttonBorder', '#0e639c')};
            border-radius: 3px;
            padding: 6px 12px;
            color: {self._current_theme.get('buttonForeground', '#ffffff')};
        }}
        
        QPushButton:hover {{
            background-color: {self._current_theme.get('buttonHoverBackground', '#1177bb')};
        }}
        
        QPushButton:pressed {{
            background-color: {self._current_theme.get('buttonActiveBackground', '#0d5a9a')};
        }}
        
        QPushButton:disabled {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            color: {self._current_theme.get('mutedForeground', '#6c6c6c')};
            border-color: {self._current_theme.get('inputBorder', '#5a5a5a')};
        }}
        
        #PromptPreviewLabel {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            border: 1px solid {self._current_theme.get('inputBorder', '#5a5a5a')};
            border-radius: 3px;
            padding: 6px;
            color: {self._current_theme.get('inputForeground', '#ffffff')};
        }}
        
        #OptimizeStatusLabel {{
            color: {self._current_theme.get('editorForeground', '#ffffff')};
        }}
        """
        
        self.setStyleSheet(style_sheet)


class TestConnectionWorker(QtCore.QThread):
    """测试连接工作线程"""
    
    finished = QtCore.pyqtSignal(dict)
    
    def __init__(self, client: AIClient):
        super().__init__()
        self.client = client
    
    def run(self):
        """运行测试"""
        result = self.client.test_connection()
        self.finished.emit(result)

class OptimizePromptWorker(QtCore.QThread):
    """优化提示词工作线程"""
    finished = QtCore.pyqtSignal(dict)

    def __init__(self, client: AIClient, prompt_text: str):
        super().__init__()
        self.client = client
        self.prompt_text = prompt_text

    def run(self):
        try:
            optimized = self.client.optimize_prompt(self.prompt_text)
            self.finished.emit({"success": True, "optimized": optimized})
        except Exception as e:
            self.finished.emit({"success": False, "message": str(e)})


class MigrationDialog(QtWidgets.QDialog):
    """配置迁移对话框"""
    
    def __init__(self, migration_info: Dict[str, Any], migration: ConfigMigration, parent=None):
        super().__init__(parent)
        self.migration_info = migration_info
        self.migration = migration
        
        self.setWindowTitle("配置迁移")
        self.setModal(True)
        self.resize(600, 500)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 标题
        title = QtWidgets.QLabel("配置迁移")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # 迁移信息
        info_text = self._generate_migration_info_text()
        info_label = QtWidgets.QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(info_label)
        
        # 迁移报告
        report_group = QtWidgets.QGroupBox("迁移详情")
        report_layout = QtWidgets.QVBoxLayout(report_group)
        
        self.report_text = QtWidgets.QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setMaximumHeight(200)
        self.report_text.setPlainText(self.migration.get_migration_report())
        report_layout.addWidget(self.report_text)
        
        layout.addWidget(report_group)
        
        # 选项
        options_group = QtWidgets.QGroupBox("迁移选项")
        options_layout = QtWidgets.QVBoxLayout(options_group)
        
        self.backup_checkbox = QtWidgets.QCheckBox("迁移前备份现有配置")
        self.backup_checkbox.setChecked(True)
        options_layout.addWidget(self.backup_checkbox)
        
        self.cleanup_checkbox = QtWidgets.QCheckBox("迁移后清理环境变量（可选）")
        self.cleanup_checkbox.setChecked(False)
        options_layout.addWidget(self.cleanup_checkbox)
        
        layout.addWidget(options_group)
        
        # 进度条
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("color: blue;")
        layout.addWidget(self.status_label)
        
        # 按钮
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QtWidgets.QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.migrate_button = QtWidgets.QPushButton("开始迁移")
        self.migrate_button.clicked.connect(self._start_migration)
        button_layout.addWidget(self.migrate_button)
        
        layout.addLayout(button_layout)
    
    def _generate_migration_info_text(self) -> str:
        """生成迁移信息文本"""
        migration_type = self.migration_info["migration_type"]
        env_vars = self.migration_info["env_vars_found"]
        
        if migration_type == "env_to_json":
            return f"检测到 {len(env_vars)} 个环境变量配置，建议迁移到JSON配置文件中以便更好地管理。"
        elif migration_type == "update_from_env":
            return f"检测到环境变量中有更新的配置值，建议更新到JSON配置文件中。"
        else:
            return "检测到配置需要更新。"
    
    def _start_migration(self):
        """开始迁移"""
        self.migrate_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        self.status_label.setText("正在迁移配置...")
        
        # 在新线程中执行迁移
        self._migration_worker = MigrationWorker(
            self.migration,
            self.migration_info,
            self.backup_checkbox.isChecked(),
            self.cleanup_checkbox.isChecked()
        )
        self._migration_worker.finished.connect(self._on_migration_finished)
        self._migration_worker.start()
    
    def _on_migration_finished(self, result: Dict[str, Any]):
        """迁移完成回调"""
        self.progress_bar.setVisible(False)
        
        if result["success"]:
            self.status_label.setText("✅ 迁移成功！")
            self.status_label.setStyleSheet("color: green;")
            
            # 显示迁移结果
            message = result["message"]
            if result.get("migrated_values"):
                message += f"\n\n迁移的配置项：\n"
                for key, value in result["migrated_values"].items():
                    message += f"- {key}: {value}\n"
            
            if result.get("backup_path"):
                message += f"\n备份文件：{result['backup_path']}"
            
            QtWidgets.QMessageBox.information(self, "迁移成功", message)
            self.accept()
            
        else:
            self.status_label.setText("❌ 迁移失败")
            self.status_label.setStyleSheet("color: red;")
            QtWidgets.QMessageBox.warning(self, "迁移失败", result["message"])
            
            self.migrate_button.setEnabled(True)
            self.cancel_button.setEnabled(True)


class MigrationWorker(QtCore.QThread):
    """迁移工作线程"""
    
    finished = QtCore.pyqtSignal(dict)
    
    def __init__(self, migration: ConfigMigration, migration_info: Dict[str, Any], 
                 backup: bool, cleanup: bool):
        super().__init__()
        self.migration = migration
        self.migration_info = migration_info
        self.backup = backup
        self.cleanup = cleanup
    
    def run(self):
        """执行迁移"""
        try:
            # 执行迁移
            result = self.migration.perform_migration(self.migration_info, self.backup)
            
            # 如果需要清理环境变量
            if result["success"] and self.cleanup and self.migration_info["env_vars_found"]:
                cleanup_result = self.migration.cleanup_environment_variables(
                    self.migration_info["env_vars_found"], 
                    confirm=True
                )
                
                if cleanup_result["success"]:
                    result["message"] += f"\n已清理 {len(cleanup_result['cleaned_vars'])} 个环境变量"
                else:
                    result["message"] += f"\n环境变量清理部分失败：{cleanup_result['message']}"
            
            self.finished.emit(result)
            
        except Exception as e:
            self.finished.emit({
                "success": False,
                "message": f"迁移过程中发生错误：{str(e)}",
                "backup_path": None,
                "migrated_values": {}
            })