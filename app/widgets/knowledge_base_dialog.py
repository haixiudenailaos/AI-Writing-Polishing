"""
知识库创建进度对话框
"""

from typing import Dict, Optional, Callable
from PySide6 import QtWidgets, QtCore, QtGui


class KnowledgeBaseProgressDialog(QtWidgets.QDialog):
    """知识库创建进度对话框"""
    
    # 信号定义
    cancelled = QtCore.Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_theme = {}
        
        self.setWindowTitle("创建知识库")
        self.setModal(True)
        self.resize(500, 300)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # 标题
        title = QtWidgets.QLabel("正在创建知识库")
        title.setObjectName("DialogTitle")
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)
        
        # 旋转加载动画
        self.loading_label = QtWidgets.QLabel("⏳")
        self.loading_label.setObjectName("LoadingLabel")
        self.loading_label.setAlignment(QtCore.Qt.AlignCenter)
        font = self.loading_label.font()
        font.setPointSize(24)
        self.loading_label.setFont(font)
        layout.addWidget(self.loading_label)
        
        # 创建旋转动画
        self.rotation_angle = 0
        self.animation_timer = QtCore.QTimer(self)
        self.animation_timer.timeout.connect(self._update_loading_animation)
        self.animation_timer.start(100)  # 每100ms更新一次
        
        # 进度条
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setObjectName("ProgressBar")
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QtWidgets.QLabel("准备中...")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        # 日志区域
        log_group = QtWidgets.QGroupBox("处理日志")
        log_group.setObjectName("LogGroup")
        log_layout = QtWidgets.QVBoxLayout(log_group)
        
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setObjectName("LogText")
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QtWidgets.QPushButton("取消")
        self.cancel_button.setObjectName("CancelButton")
        self.cancel_button.setMinimumSize(80, 32)
        self.cancel_button.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_button)
        
        self.close_button = QtWidgets.QPushButton("关闭")
        self.close_button.setObjectName("CloseButton")
        self.close_button.setMinimumSize(80, 32)
        self.close_button.clicked.connect(self.accept)
        self.close_button.setEnabled(False)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def update_progress(self, current: int, total: int, message: str):
        """更新进度"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
        
        self.status_label.setText(message)
        self.log(message)
    
    def log(self, message: str):
        """添加日志"""
        self.log_text.append(message)
        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def set_completed(self, success: bool = True):
        """设置完成状态"""
        # 停止加载动画
        if hasattr(self, 'animation_timer'):
            self.animation_timer.stop()
        
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)
        
        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText("✅ 知识库创建完成！")
            if hasattr(self, 'loading_label'):
                self.loading_label.setText("✅")
        else:
            self.status_label.setText("❌ 知识库创建失败")
            if hasattr(self, 'loading_label'):
                self.loading_label.setText("❌")
    
    def _update_loading_animation(self):
        """更新加载动画"""
        # 使用不同的加载符号来创建动画效果
        loading_chars = ["⏳", "⌛"]
        self.rotation_angle = (self.rotation_angle + 1) % len(loading_chars)
        if hasattr(self, 'loading_label'):
            self.loading_label.setText(loading_chars[self.rotation_angle])
    
    def _on_cancel(self):
        """取消操作"""
        reply = QtWidgets.QMessageBox.question(
            self, "确认取消",
            "确定要取消知识库创建吗？已处理的数据将丢失。",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.cancelled.emit()
            self.reject()
    
    def set_theme(self, theme: Dict[str, str]):
        """设置主题"""
        self._current_theme = theme
        self._apply_theme()
    
    def _apply_theme(self):
        """应用主题"""
        if not self._current_theme:
            return
        
        style_sheet = f"""
        QDialog {{
            background-color: {self._current_theme.get('editorBackground', '#1e1e1e')};
            color: {self._current_theme.get('editorForeground', '#d4d4d4')};
        }}
        
        #DialogTitle {{
            font-size: 16px;
            font-weight: bold;
            color: {self._current_theme.get('titleBarForeground', '#ffffff')};
        }}
        
        #ProgressBar {{
            border: 1px solid {self._current_theme.get('borderColor', '#3e3e42')};
            border-radius: 3px;
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            text-align: center;
        }}
        
        #ProgressBar::chunk {{
            background-color: {self._current_theme.get('accent', '#007acc')};
            border-radius: 2px;
        }}
        
        #StatusLabel {{
            color: {self._current_theme.get('editorForeground', '#d4d4d4')};
            font-size: 13px;
        }}
        
        #LoadingLabel {{
            color: {self._current_theme.get('accent', '#007acc')};
            font-size: 24px;
        }}
        
        #LogGroup {{
            border: 1px solid {self._current_theme.get('borderColor', '#3e3e42')};
            border-radius: 3px;
            margin-top: 6px;
            padding-top: 6px;
        }}
        
        #LogGroup::title {{
            color: {self._current_theme.get('editorForeground', '#d4d4d4')};
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 3px;
        }}
        
        #LogText {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            border: 1px solid {self._current_theme.get('inputBorder', '#5a5a5a')};
            border-radius: 3px;
            color: {self._current_theme.get('inputForeground', '#ffffff')};
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 11px;
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
        
        QPushButton:disabled {{
            background-color: {self._current_theme.get('buttonDisabledBackground', '#2d2d30')};
            color: {self._current_theme.get('buttonDisabledForeground', '#656565')};
            border-color: {self._current_theme.get('buttonDisabledBackground', '#2d2d30')};
        }}
        
        #CancelButton {{
            background-color: transparent;
            border: 1px solid {self._current_theme.get('borderColor', '#3e3e42')};
            color: {self._current_theme.get('editorForeground', '#d4d4d4')};
        }}
        
        #CancelButton:hover {{
            background-color: {self._current_theme.get('listHoverBackground', '#2a2d2e')};
        }}
        """
        
        self.setStyleSheet(style_sheet)
