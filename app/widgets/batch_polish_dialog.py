"""
一键润色对话框
支持用户输入润色需求，并对整个文档进行批量润色
"""

from typing import Dict, Optional
from PySide6 import QtWidgets, QtCore, QtGui
from app.api_client import AIClient
from app.widgets.pulsing_label import PulsingLabel


class BatchPolishDialog(QtWidgets.QDialog):
    """一键润色对话框"""
    
    # 信号定义
    polish_requested = QtCore.Signal(str, str)  # requirement_text, original_content
    
    def __init__(self, original_content: str, config_manager=None, parent=None):
        super().__init__(parent)
        self.original_content = original_content
        self.config_manager = config_manager
        self._current_theme = {}
        
        self.setWindowTitle("一键润色")
        self.setModal(True)
        self.resize(500, 350)
        
        self._setup_ui()
        
    def _setup_ui(self):
        """设置UI"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title = QtWidgets.QLabel("批量润色整个文档")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # 说明文字
        description = QtWidgets.QLabel(
            "请输入您的润色需求，系统将根据需求对整个文档进行润色。\n"
            "例如：优化语句流畅度、提升专业性、调整为口语化风格等。"
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(description)
        
        # 需求输入框
        requirement_label = QtWidgets.QLabel("润色需求:")
        requirement_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(requirement_label)
        
        self.requirement_input = QtWidgets.QTextEdit()
        self.requirement_input.setPlaceholderText(
            "例如：将文本优化为更专业的商务风格，提升语言的准确性和简洁度..."
        )
        self.requirement_input.setMinimumHeight(100)
        self.requirement_input.setMaximumHeight(150)
        layout.addWidget(self.requirement_input)
        
        # 优化提示词按钮
        optimize_layout = QtWidgets.QHBoxLayout()
        
        self.optimize_button = QtWidgets.QPushButton("✨ AI优化提示词")
        self.optimize_button.setMinimumHeight(32)
        self.optimize_button.clicked.connect(self._optimize_requirement)
        self.optimize_button.setToolTip("使用AI优化和完善您的润色需求")
        optimize_layout.addWidget(self.optimize_button)
        
        # 使用脉冲动画标签
        self.optimize_status = PulsingLabel("")
        optimize_layout.addWidget(self.optimize_status)
        optimize_layout.addStretch()
        
        layout.addLayout(optimize_layout)
        
        # 文档信息
        info_text = f"当前文档字数：约 {len(self.original_content)} 字"
        info_label = QtWidgets.QLabel(info_text)
        info_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(info_label)
        
        # 警告提示
        warning = QtWidgets.QLabel(
            "⚠️ 注意：批量润色会替换整个文档内容，建议先备份原文档。"
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #ff6b35; font-weight: bold; padding: 10px; background: #fff4e6; border-radius: 4px;")
        layout.addWidget(warning)
        
        layout.addStretch()
        
        # 按钮栏
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QtWidgets.QPushButton("取消")
        cancel_button.setMinimumSize(80, 36)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        self.polish_button = QtWidgets.QPushButton("开始润色")
        self.polish_button.setMinimumSize(80, 36)
        self.polish_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        self.polish_button.clicked.connect(self._start_polish)
        button_layout.addWidget(self.polish_button)
        
        layout.addLayout(button_layout)
    
    def _optimize_requirement(self):
        """优化润色需求"""
        requirement = self.requirement_input.toPlainText().strip()
        
        if not requirement:
            QtWidgets.QMessageBox.warning(self, "提示", "请先输入润色需求")
            return
        
        # 禁用按钮并显示脉冲动画
        self.optimize_button.setEnabled(False)
        self.optimize_status.set_pulsing_text("🔄 优化中...")
        
        try:
            # 复用父窗口的共享 API 客户端以优化连接池性能
            client = None
            parent = self.parent()
            if parent and hasattr(parent, "_shared_api_client"):
                client = parent._shared_api_client
            elif parent and hasattr(parent, "_api_client"):
                client = parent._api_client
            else:
                # 降级：创建新客户端
                client = AIClient(config_manager=self.config_manager) if self.config_manager else AIClient()
            
            # 创建优化工作线程
            self._optimize_worker = OptimizeRequirementWorker(client, requirement)
            self._optimize_worker.finished.connect(self._on_optimize_finished)
            self._optimize_worker.start()
            
        except Exception as e:
            self.optimize_status.set_static_text(f"❌ 失败: {str(e)}")
            self.optimize_button.setEnabled(True)
    
    def _on_optimize_finished(self, result: Dict):
        """优化完成回调"""
        self.optimize_button.setEnabled(True)
        
        if result.get("success"):
            optimized = result.get("optimized", "")
            if optimized:
                self.requirement_input.setPlainText(optimized)
                self.optimize_status.set_static_text("✅ 已优化")
        else:
            self.optimize_status.set_static_text(f"❌ {result.get('message', '优化失败')}")
    
    def _start_polish(self):
        """开始润色"""
        requirement = self.requirement_input.toPlainText().strip()
        
        if not requirement:
            QtWidgets.QMessageBox.warning(
                self, 
                "提示", 
                "请输入润色需求，以便系统了解如何优化您的文档。"
            )
            return
        
        # 确认对话框
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认润色",
            f"确定要对整个文档（约{len(self.original_content)}字）进行批量润色吗？\n"
            f"此操作将替换文档内容，建议先备份。",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            # 发送信号
            self.polish_requested.emit(requirement, self.original_content)
            self.accept()
    
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
            color: {self._current_theme.get('editorForeground', '#ffffff')};
        }}
        
        QLabel {{
            color: {self._current_theme.get('editorForeground', '#ffffff')};
        }}
        
        QTextEdit {{
            background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
            border: 1px solid {self._current_theme.get('inputBorder', '#5a5a5a')};
            border-radius: 4px;
            color: {self._current_theme.get('inputForeground', '#ffffff')};
            padding: 8px;
        }}
        
        QTextEdit:focus {{
            border-color: {self._current_theme.get('focusBorder', '#007acc')};
        }}
        
        QPushButton {{
            background-color: {self._current_theme.get('buttonBackground', '#0e639c')};
            border: 1px solid {self._current_theme.get('buttonBorder', '#0e639c')};
            border-radius: 4px;
            padding: 8px 16px;
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
        }}
        """
        
        self.setStyleSheet(style_sheet)


class OptimizeRequirementWorker(QtCore.QThread):
    """优化需求工作线程"""
    
    finished = QtCore.Signal(dict)
    
    def __init__(self, client: AIClient, requirement: str):
        super().__init__()
        self.client = client
        self.requirement = requirement
    
    def run(self):
        """运行优化"""
        try:
            # 调用API优化需求
            optimized = self.client.optimize_prompt(self.requirement)
            self.finished.emit({"success": True, "optimized": optimized})
        except Exception as e:
            self.finished.emit({"success": False, "message": str(e)})

