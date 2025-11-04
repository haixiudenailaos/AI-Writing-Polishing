"""
知识库状态指示器组件
紧凑设计，鼠标悬停时显示详细信息
"""

from typing import Dict, Optional
from PySide6 import QtWidgets, QtCore, QtGui


class KnowledgeBaseStatusIndicator(QtWidgets.QWidget):
    """知识库状态指示器
    
    紧凑的状态显示组件，默认显示图标和简要状态，
    鼠标悬停时显示完整的知识库信息
    """
    
    # 信号定义
    clicked = QtCore.Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_theme = {}
        
        # 状态数据
        self._history_kb_name = None
        self._outline_kb_name = None
        self._character_kb_name = None
        self._rerank_enabled = False
        
        # 工具提示定时器
        self._tooltip_timer = QtCore.QTimer(self)
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.timeout.connect(self._show_tooltip)
        
        # 悬浮窗
        self._tooltip_widget = None
        
        self._setup_ui()
        self.setMouseTracking(True)
    
    def _setup_ui(self):
        """设置UI"""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        
        # 图标标签
        self.icon_label = QtWidgets.QLabel("📚")
        self.icon_label.setObjectName("KBStatusIcon")
        font = self.icon_label.font()
        font.setPointSize(12)
        self.icon_label.setFont(font)
        layout.addWidget(self.icon_label)
        
        # 状态指示器（小圆点）
        self.status_dot = QtWidgets.QLabel("●")
        self.status_dot.setObjectName("KBStatusDot")
        font = self.status_dot.font()
        font.setPointSize(10)
        self.status_dot.setFont(font)
        layout.addWidget(self.status_dot)
        
        # 设置固定大小
        self.setFixedSize(50, 30)
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        
        # 更新状态显示
        self._update_status_display()
    
    def update_status(
        self,
        history_kb_name: Optional[str] = None,
        outline_kb_name: Optional[str] = None,
        character_kb_name: Optional[str] = None,
        rerank_enabled: bool = False
    ):
        """更新知识库状态
        
        Args:
            history_kb_name: 历史知识库名称
            outline_kb_name: 大纲知识库名称
            character_kb_name: 人设知识库名称
            rerank_enabled: 重排序是否启用
        """
        self._history_kb_name = history_kb_name
        self._outline_kb_name = outline_kb_name
        self._character_kb_name = character_kb_name
        self._rerank_enabled = rerank_enabled
        
        self._update_status_display()
    
    def _update_status_display(self):
        """更新状态显示"""
        # 计算激活的知识库数量
        active_count = sum([
            bool(self._history_kb_name),
            bool(self._outline_kb_name),
            bool(self._character_kb_name)
        ])
        
        # 根据激活数量设置颜色
        if active_count == 0:
            color = "#808080"  # 灰色 - 未激活
            status_text = "未激活"
        elif active_count == 1:
            color = "#4ec9b0"  # 青色 - 部分激活
            status_text = "已激活"
        elif active_count == 2:
            color = "#569cd6"  # 蓝色 - 多数激活
            status_text = "已激活"
        else:
            color = "#4caf50"  # 绿色 - 全部激活
            status_text = "全激活"
        
        # 更新状态点颜色
        self.status_dot.setStyleSheet(f"color: {color};")
        
        # 设置工具提示（简短版本）
        tooltip = f"知识库: {status_text}"
        if self._rerank_enabled:
            tooltip += " | 重排: 启用"
        self.setToolTip(tooltip)
    
    def enterEvent(self, event: QtCore.QEvent):
        """鼠标进入事件"""
        super().enterEvent(event)
        # 延迟500ms显示详细信息
        self._tooltip_timer.start(500)
    
    def leaveEvent(self, event: QtCore.QEvent):
        """鼠标离开事件"""
        super().leaveEvent(event)
        # 取消显示
        self._tooltip_timer.stop()
        self._hide_tooltip()
    
    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """鼠标点击事件"""
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
    
    def _show_tooltip(self):
        """显示详细信息悬浮窗"""
        if self._tooltip_widget is not None:
            self._tooltip_widget.close()
            self._tooltip_widget = None
        
        # 创建悬浮窗
        self._tooltip_widget = KnowledgeBaseTooltip(
            history_kb=self._history_kb_name,
            outline_kb=self._outline_kb_name,
            character_kb=self._character_kb_name,
            rerank_enabled=self._rerank_enabled,
            parent=self
        )
        
        # 应用主题
        if self._current_theme:
            self._tooltip_widget.set_theme(self._current_theme)
        
        # 计算位置（在指示器下方显示）
        global_pos = self.mapToGlobal(QtCore.QPoint(0, self.height() + 2))
        self._tooltip_widget.move(global_pos)
        
        # 显示
        self._tooltip_widget.show()
    
    def _hide_tooltip(self):
        """隐藏悬浮窗"""
        if self._tooltip_widget is not None:
            self._tooltip_widget.close()
            self._tooltip_widget = None
    
    def set_theme(self, theme: Dict[str, str]):
        """设置主题"""
        self._current_theme = theme
        self._apply_theme()
    
    def _apply_theme(self):
        """应用主题"""
        if not self._current_theme:
            return
        
        border_color = self._current_theme.get('borderColor', '#3e3e42')
        background = self._current_theme.get('panelBackground', '#2d2d30')
        
        style_sheet = f"""
        KnowledgeBaseStatusIndicator {{
            background-color: {background};
            border: 1px solid {border_color};
            border-radius: 4px;
        }}
        
        KnowledgeBaseStatusIndicator:hover {{
            border: 1px solid {self._current_theme.get('accent', '#007acc')};
        }}
        """
        
        self.setStyleSheet(style_sheet)


class KnowledgeBaseTooltip(QtWidgets.QWidget):
    """知识库状态详细信息悬浮窗"""
    
    def __init__(
        self,
        history_kb: Optional[str],
        outline_kb: Optional[str],
        character_kb: Optional[str],
        rerank_enabled: bool,
        parent=None
    ):
        super().__init__(parent, QtCore.Qt.ToolTip | QtCore.Qt.FramelessWindowHint)
        
        self.history_kb = history_kb
        self.outline_kb = outline_kb
        self.character_kb = character_kb
        self.rerank_enabled = rerank_enabled
        self._current_theme = {}
        
        # 使用不透明背景，避免半透明导致的可读性问题
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        
        self._setup_ui()
        
        # 自动隐藏定时器
        self._hide_timer = QtCore.QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.close)
    
    def _setup_ui(self):
        """设置UI"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        
        # 标题
        title_label = QtWidgets.QLabel("知识库状态")
        title_label.setObjectName("TooltipTitle")
        font = title_label.font()
        font.setPointSize(11)
        font.setBold(True)
        title_label.setFont(font)
        layout.addWidget(title_label)
        
        # 分隔线
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        separator.setObjectName("Separator")
        layout.addWidget(separator)
        
        # 历史知识库
        history_layout = QtWidgets.QHBoxLayout()
        history_icon = QtWidgets.QLabel("📚")
        history_icon.setFixedWidth(20)
        history_layout.addWidget(history_icon)
        
        history_text = self.history_kb if self.history_kb else "未激活"
        history_label = QtWidgets.QLabel(f"历史: {history_text}")
        history_label.setObjectName("StatusItem")
        if not self.history_kb:
            history_label.setStyleSheet("color: #808080;")
        history_layout.addWidget(history_label, 1)
        layout.addLayout(history_layout)
        
        # 大纲知识库
        outline_layout = QtWidgets.QHBoxLayout()
        outline_icon = QtWidgets.QLabel("📋")
        outline_icon.setFixedWidth(20)
        outline_layout.addWidget(outline_icon)
        
        outline_text = self.outline_kb if self.outline_kb else "未激活"
        outline_label = QtWidgets.QLabel(f"大纲: {outline_text}")
        outline_label.setObjectName("StatusItem")
        if not self.outline_kb:
            outline_label.setStyleSheet("color: #808080;")
        outline_layout.addWidget(outline_label, 1)
        layout.addLayout(outline_layout)
        
        # 人设知识库
        character_layout = QtWidgets.QHBoxLayout()
        character_icon = QtWidgets.QLabel("👤")
        character_icon.setFixedWidth(20)
        character_layout.addWidget(character_icon)
        
        character_text = self.character_kb if self.character_kb else "未激活"
        character_label = QtWidgets.QLabel(f"人设: {character_text}")
        character_label.setObjectName("StatusItem")
        if not self.character_kb:
            character_label.setStyleSheet("color: #808080;")
        character_layout.addWidget(character_label, 1)
        layout.addLayout(character_layout)
        
        # 分隔线
        separator2 = QtWidgets.QFrame()
        separator2.setFrameShape(QtWidgets.QFrame.HLine)
        separator2.setFrameShadow(QtWidgets.QFrame.Sunken)
        separator2.setObjectName("Separator")
        layout.addWidget(separator2)
        
        # 重排状态
        rerank_layout = QtWidgets.QHBoxLayout()
        rerank_icon = QtWidgets.QLabel("⚡")
        rerank_icon.setFixedWidth(20)
        rerank_layout.addWidget(rerank_icon)
        
        rerank_text = "已启用" if self.rerank_enabled else "未启用"
        rerank_label = QtWidgets.QLabel(f"重排序: {rerank_text}")
        rerank_label.setObjectName("StatusItem")
        if not self.rerank_enabled:
            rerank_label.setStyleSheet("color: #808080;")
        rerank_layout.addWidget(rerank_label, 1)
        layout.addLayout(rerank_layout)
        
        # 提示文字
        hint_label = QtWidgets.QLabel("点击图标打开知识库管理")
        hint_label.setObjectName("HintLabel")
        font = hint_label.font()
        font.setPointSize(9)
        hint_label.setFont(font)
        hint_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(hint_label)
        
        # 设置最小宽度
        self.setMinimumWidth(220)
    
    def showEvent(self, event: QtGui.QShowEvent):
        """显示事件"""
        super().showEvent(event)
        # 3秒后自动隐藏
        self._hide_timer.start(3000)
    
    def enterEvent(self, event: QtCore.QEvent):
        """鼠标进入悬浮窗"""
        super().enterEvent(event)
        # 取消自动隐藏
        self._hide_timer.stop()
    
    def leaveEvent(self, event: QtCore.QEvent):
        """鼠标离开悬浮窗"""
        super().leaveEvent(event)
        # 立即隐藏
        self.close()
    
    def set_theme(self, theme: Dict[str, str]):
        """设置主题"""
        self._current_theme = theme
        self._apply_theme()
    
    def _apply_theme(self):
        """应用主题"""
        if not self._current_theme:
            return
        
        background = self._current_theme.get('panelBackground', '#2d2d30')
        foreground = self._current_theme.get('foreground', '#cccccc')
        border_color = self._current_theme.get('borderColor', '#3e3e42')
        accent = self._current_theme.get('accent', '#007acc')
        
        style_sheet = f"""
        KnowledgeBaseTooltip {{
            background-color: {background};
            border: 1px solid {accent};
            border-radius: 6px;
        }}
        
        #TooltipTitle {{
            color: {foreground};
        }}
        
        #StatusItem {{
            color: {foreground};
            font-size: 10px;
        }}
        
        #HintLabel {{
            color: {self._current_theme.get('mutedForeground', '#858585')};
        }}
        
        #Separator {{
            background-color: {border_color};
        }}
        """
        
        self.setStyleSheet(style_sheet)

