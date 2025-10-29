"""
剧情预测开关控件
支持悬停3秒显示功能介绍的开关按钮
"""

from typing import Dict, Optional
from PySide6 import QtCore, QtGui, QtWidgets
from app.widgets.design_system import BorderRadius, Spacing


class PredictionToggle(QtWidgets.QWidget):
    """剧情预测开关控件 - 支持悬停3秒显示提示"""
    
    # 信号定义
    toggled = QtCore.Signal(bool)  # 开关状态变化信号
    
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._current_theme: Dict[str, str] = {}
        self._is_enabled = False  # 默认关闭
        self._hover_timer = QtCore.QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(3000)  # 3秒
        self._hover_timer.timeout.connect(self._show_tooltip)
        self._tooltip_widget: Optional[QtWidgets.QLabel] = None
        
        self.setObjectName("PredictionToggle")
        self._setup_ui()
        self._apply_theme()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        layout.setSpacing(Spacing.SM)
        
        # 图标标签
        self._icon_label = QtWidgets.QLabel("🔮")
        self._icon_label.setObjectName("PredictionIcon")
        layout.addWidget(self._icon_label)
        
        # 功能标签
        self._label = QtWidgets.QLabel("剧情预测")
        self._label.setObjectName("PredictionLabel")
        layout.addWidget(self._label)
        
        layout.addSpacing(Spacing.SM)
        
        # 开关按钮
        self._toggle_button = QtWidgets.QPushButton()
        self._toggle_button.setObjectName("ToggleButton")
        self._toggle_button.setCheckable(True)
        self._toggle_button.setChecked(self._is_enabled)
        self._toggle_button.setFixedSize(48, 24)
        self._toggle_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        self._update_button_text()
        layout.addWidget(self._toggle_button)
        
        layout.addStretch()
        
        # 设置鼠标追踪以支持悬停检测
        self.setMouseTracking(True)
        self._toggle_button.setMouseTracking(True)
        self._label.setMouseTracking(True)
        self._icon_label.setMouseTracking(True)
    
    def _on_toggle_clicked(self, checked: bool):
        """处理开关点击"""
        self._is_enabled = checked
        self._update_button_text()
        self.toggled.emit(self._is_enabled)
    
    def _update_button_text(self):
        """更新按钮文本"""
        if self._is_enabled:
            self._toggle_button.setText("开启")
        else:
            self._toggle_button.setText("关闭")
    
    def is_enabled(self) -> bool:
        """获取开关状态"""
        return self._is_enabled
    
    def set_enabled(self, enabled: bool):
        """设置开关状态"""
        if self._is_enabled != enabled:
            self._is_enabled = enabled
            self._toggle_button.setChecked(enabled)
            self._update_button_text()
            self.toggled.emit(self._is_enabled)
    
    def enterEvent(self, event: QtCore.QEvent):
        """鼠标进入事件 - 启动悬停计时器"""
        super().enterEvent(event)
        self._hover_timer.start()
    
    def leaveEvent(self, event: QtCore.QEvent):
        """鼠标离开事件 - 停止计时器并隐藏提示"""
        super().leaveEvent(event)
        self._hover_timer.stop()
        self._hide_tooltip()
    
    def _show_tooltip(self):
        """显示功能介绍提示框"""
        if self._tooltip_widget is not None:
            return
        
        # 创建提示框
        self._tooltip_widget = QtWidgets.QLabel(self)
        self._tooltip_widget.setObjectName("PredictionTooltip")
        self._tooltip_widget.setWindowFlags(QtCore.Qt.ToolTip)
        self._tooltip_widget.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        # 设置提示内容
        tooltip_text = (
            "<b>🔮 文本预测功能</b><br><br>"
            "<b>功能说明：</b><br>"
            "当您停止输入3秒后，AI会自动分析当前内容，<br>"
            "预测可能的后续发展，帮助您拓展创作思路。<br><br>"
            "<b>使用方式：</b><br>"
            "• 开启此开关后，正常输入您的文本内容<br>"
            "• 暂停输入等待3秒，系统会自动预测<br>"
            "• 预测结果会显示在右侧面板供参考<br>"
            "• 您可以选择采纳或继续自己的创作<br><br>"
            "<b>注意：</b>关闭此开关后，自动预测功能将停止。"
        )
        self._tooltip_widget.setText(tooltip_text)
        self._tooltip_widget.setWordWrap(True)
        self._tooltip_widget.setMaximumWidth(400)
        
        # 应用样式 - 统一使用黑底白字配色方案
        # 使用固定的黑色背景和白色文字，确保在任何主题下都有清晰的视觉效果
        tooltip_bg = '#000000'  # 纯黑色背景
        tooltip_fg = '#ffffff'  # 纯白色文字
        tooltip_border = self._current_theme.get('accent', '#007acc')  # 使用主题强调色作为边框
        
        self._tooltip_widget.setStyleSheet(f"""
            QLabel#PredictionTooltip {{
                background-color: {tooltip_bg};
                color: {tooltip_fg};
                border: 2px solid {tooltip_border};
                border-radius: {BorderRadius.MD}px;
                padding: {Spacing.MD}px;
                font-size: 13px;
                line-height: 1.5;
                font-weight: 400;
            }}
        """)
        
        # 计算位置（显示在控件下方）
        global_pos = self.mapToGlobal(QtCore.QPoint(0, self.height() + 5))
        self._tooltip_widget.move(global_pos)
        self._tooltip_widget.adjustSize()
        self._tooltip_widget.show()
        
        # 添加淡入动画
        self._animate_tooltip_in()
    
    def _hide_tooltip(self):
        """隐藏提示框"""
        if self._tooltip_widget is not None:
            self._tooltip_widget.hide()
            self._tooltip_widget.deleteLater()
            self._tooltip_widget = None
    
    def _animate_tooltip_in(self):
        """提示框淡入动画"""
        if self._tooltip_widget is None:
            return
        
        effect = QtWidgets.QGraphicsOpacityEffect(self._tooltip_widget)
        self._tooltip_widget.setGraphicsEffect(effect)
        
        animation = QtCore.QPropertyAnimation(effect, b"opacity")
        animation.setDuration(300)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        animation.start()
        
        # 保持动画引用避免被垃圾回收
        self._tooltip_animation = animation
    
    def _is_dark_color(self, color_hex: str) -> bool:
        """判断颜色是否为暗色
        
        Args:
            color_hex: 十六进制颜色代码，如 '#2d2d30'
            
        Returns:
            True 如果是暗色，False 如果是亮色
        """
        try:
            # 移除 # 号
            color_hex = color_hex.lstrip('#')
            
            # 转换为 RGB
            r = int(color_hex[0:2], 16)
            g = int(color_hex[2:4], 16)
            b = int(color_hex[4:6], 16)
            
            # 计算亮度（使用感知亮度公式）
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            
            # 亮度小于 0.5 认为是暗色
            return luminance < 0.5
        except (ValueError, IndexError):
            # 解析失败，默认认为是暗色
            return True
    
    def set_theme(self, theme: Dict[str, str]):
        """设置主题"""
        self._current_theme = theme
        self._apply_theme()
    
    def _apply_theme(self):
        """应用主题样式"""
        if not self._current_theme:
            return
        
        bg_color = self._current_theme.get('panelBackground', '#252526')
        fg_color = self._current_theme.get('editorForeground', '#ffffff')
        accent_color = self._current_theme.get('accent', '#007acc')
        border_color = self._current_theme.get('borderColor', '#3e3e42')
        
        style_sheet = f"""
        QWidget#PredictionToggle {{
            background-color: {bg_color};
            border-bottom: 1px solid {border_color};
        }}
        
        #PredictionIcon {{
            font-size: 16px;
            color: {fg_color};
        }}
        
        #PredictionLabel {{
            font-size: 13px;
            font-weight: 500;
            color: {fg_color};
        }}
        
        #ToggleButton {{
            background-color: #4a4a4a;
            border: 1px solid {border_color};
            border-radius: 12px;
            color: #ffffff;
            font-size: 11px;
            font-weight: 500;
            padding: 4px 8px;
        }}
        
        #ToggleButton:checked {{
            background-color: {accent_color};
            border-color: {accent_color};
            color: #ffffff;
        }}
        
        #ToggleButton:hover {{
            border-color: {accent_color};
        }}
        
        #ToggleButton:checked:hover {{
            background-color: {self._current_theme.get('buttonHoverBackground', '#1177bb')};
        }}
        """
        
        self.setStyleSheet(style_sheet)

