"""
UI增强模块
包含下划线渲染器和动画管理器
"""

from typing import Dict, Optional, List
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, pyqtSignal


class UnderlineRenderer(QtCore.QObject):
    """下划线渲染器 - 为编辑器添加行级下划线视觉效果"""
    
    def __init__(self, editor: QtWidgets.QPlainTextEdit, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._editor = editor
        self._theme: Dict[str, str] = {}
        self._underline_enabled = True
        self._underline_color = QtGui.QColor("#007ACC")
        self._underline_opacity = 0.3
        
        # 连接编辑器信号
        self._editor.textChanged.connect(self._update_underlines)
        self._editor.cursorPositionChanged.connect(self._update_underlines)
    
    def set_theme(self, theme: Dict[str, str]) -> None:
        """设置主题"""
        self._theme = dict(theme)
        accent_color = theme.get('accent', '#007ACC')
        self._underline_color = QtGui.QColor(accent_color)
        self._underline_color.setAlphaF(self._underline_opacity)
        self._update_underlines()
    
    def set_enabled(self, enabled: bool) -> None:
        """启用或禁用下划线渲染"""
        self._underline_enabled = enabled
        self._update_underlines()
    
    def set_underline_color(self, color: QtGui.QColor) -> None:
        """设置下划线颜色"""
        self._underline_color = QtGui.QColor(color)
        self._underline_color.setAlphaF(self._underline_opacity)
        self._update_underlines()
    
    def _update_underlines(self) -> None:
        """更新下划线显示"""
        if not self._underline_enabled:
            self._editor.setExtraSelections([])
            return
        
        # 获取所有文本行
        document = self._editor.document()
        selections = []
        
        # 为每一行添加下划线
        block = document.firstBlock()
        while block.isValid():
            if block.text().strip():  # 只为非空行添加下划线
                selection = QtWidgets.QTextEdit.ExtraSelection()
                
                # 设置下划线格式
                char_format = QtGui.QTextCharFormat()
                char_format.setUnderlineStyle(QtGui.QTextCharFormat.SingleUnderline)
                char_format.setUnderlineColor(self._underline_color)
                
                # 创建选择区域
                cursor = QtGui.QTextCursor(block)
                cursor.select(QtGui.QTextCursor.LineUnderCursor)
                
                selection.cursor = cursor
                selection.format = char_format
                selections.append(selection)
            
            block = block.next()
        
        # 应用下划线选择
        current_selections = self._editor.extraSelections()
        
        # 保留当前行高亮选择
        highlight_selections = [sel for sel in current_selections 
                              if sel.format.property(QtGui.QTextFormat.FullWidthSelection)]
        
        # 合并下划线和高亮选择
        all_selections = highlight_selections + selections
        self._editor.setExtraSelections(all_selections)


class AnimationManager(QtCore.QObject):
    """动画管理器 - 管理UI过渡动画效果"""
    
    animationFinished = pyqtSignal(str)  # 动画完成信号
    
    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._animations: Dict[str, QPropertyAnimation] = {}
        self._default_duration = 300
        self._default_easing = QEasingCurve.OutCubic
    
    def fade_in(self, widget: QtWidgets.QWidget, duration: int = None, 
                animation_id: str = None) -> None:
        """淡入动画"""
        if duration is None:
            duration = self._default_duration
        
        if animation_id is None:
            animation_id = f"fade_in_{id(widget)}"
        
        # 停止现有动画
        self._stop_animation(animation_id)
        
        # 创建透明度动画
        animation = QPropertyAnimation(widget, b"windowOpacity")
        animation.setDuration(duration)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(self._default_easing)
        
        # 连接完成信号
        animation.finished.connect(lambda: self._on_animation_finished(animation_id))
        
        # 存储并启动动画
        self._animations[animation_id] = animation
        widget.setWindowOpacity(0.0)
        widget.show()
        animation.start()
    
    def fade_out(self, widget: QtWidgets.QWidget, duration: int = None,
                 animation_id: str = None, hide_on_finish: bool = True) -> None:
        """淡出动画"""
        if duration is None:
            duration = self._default_duration
        
        if animation_id is None:
            animation_id = f"fade_out_{id(widget)}"
        
        # 停止现有动画
        self._stop_animation(animation_id)
        
        # 创建透明度动画
        animation = QPropertyAnimation(widget, b"windowOpacity")
        animation.setDuration(duration)
        animation.setStartValue(widget.windowOpacity())
        animation.setEndValue(0.0)
        animation.setEasingCurve(self._default_easing)
        
        # 连接完成信号
        if hide_on_finish:
            animation.finished.connect(widget.hide)
        animation.finished.connect(lambda: self._on_animation_finished(animation_id))
        
        # 存储并启动动画
        self._animations[animation_id] = animation
        animation.start()
    
    def slide_in_from_bottom(self, widget: QtWidgets.QWidget, duration: int = None,
                           animation_id: str = None) -> None:
        """从底部滑入动画"""
        if duration is None:
            duration = self._default_duration
        
        if animation_id is None:
            animation_id = f"slide_in_{id(widget)}"
        
        # 停止现有动画
        self._stop_animation(animation_id)
        
        # 获取目标位置
        parent = widget.parent()
        if not parent:
            return
        
        target_pos = widget.pos()
        start_pos = QtCore.QPoint(target_pos.x(), parent.height())
        
        # 创建位置动画
        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(duration)
        animation.setStartValue(start_pos)
        animation.setEndValue(target_pos)
        animation.setEasingCurve(self._default_easing)
        
        # 连接完成信号
        animation.finished.connect(lambda: self._on_animation_finished(animation_id))
        
        # 存储并启动动画
        self._animations[animation_id] = animation
        widget.move(start_pos)
        widget.show()
        animation.start()
    
    def slide_out_to_bottom(self, widget: QtWidgets.QWidget, duration: int = None,
                          animation_id: str = None, hide_on_finish: bool = True) -> None:
        """滑出到底部动画"""
        if duration is None:
            duration = self._default_duration
        
        if animation_id is None:
            animation_id = f"slide_out_{id(widget)}"
        
        # 停止现有动画
        self._stop_animation(animation_id)
        
        # 获取目标位置
        parent = widget.parent()
        if not parent:
            return
        
        start_pos = widget.pos()
        target_pos = QtCore.QPoint(start_pos.x(), parent.height())
        
        # 创建位置动画
        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(duration)
        animation.setStartValue(start_pos)
        animation.setEndValue(target_pos)
        animation.setEasingCurve(self._default_easing)
        
        # 连接完成信号
        if hide_on_finish:
            animation.finished.connect(widget.hide)
        animation.finished.connect(lambda: self._on_animation_finished(animation_id))
        
        # 存储并启动动画
        self._animations[animation_id] = animation
        animation.start()
    
    def smooth_resize(self, widget: QtWidgets.QWidget, target_size: QtCore.QSize,
                     duration: int = None, animation_id: str = None) -> None:
        """平滑调整大小动画"""
        if duration is None:
            duration = self._default_duration
        
        if animation_id is None:
            animation_id = f"resize_{id(widget)}"
        
        # 停止现有动画
        self._stop_animation(animation_id)
        
        # 创建大小动画
        animation = QPropertyAnimation(widget, b"size")
        animation.setDuration(duration)
        animation.setStartValue(widget.size())
        animation.setEndValue(target_size)
        animation.setEasingCurve(self._default_easing)
        
        # 连接完成信号
        animation.finished.connect(lambda: self._on_animation_finished(animation_id))
        
        # 存储并启动动画
        self._animations[animation_id] = animation
        animation.start()
    
    def _stop_animation(self, animation_id: str) -> None:
        """停止指定动画"""
        if animation_id in self._animations:
            animation = self._animations[animation_id]
            if animation.state() == QPropertyAnimation.Running:
                animation.stop()
            del self._animations[animation_id]
    
    def _on_animation_finished(self, animation_id: str) -> None:
        """动画完成处理"""
        if animation_id in self._animations:
            del self._animations[animation_id]
        self.animationFinished.emit(animation_id)
    
    def stop_all_animations(self) -> None:
        """停止所有动画"""
        for animation_id in list(self._animations.keys()):
            self._stop_animation(animation_id)
    
    def set_default_duration(self, duration: int) -> None:
        """设置默认动画时长"""
        self._default_duration = duration
    
    def set_default_easing(self, easing: QEasingCurve.Type) -> None:
        """设置默认缓动类型"""
        self._default_easing = easing


class UIEnhancer(QtCore.QObject):
    """UI增强器 - 统一管理UI增强功能"""
    
    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._underline_renderers: Dict[str, UnderlineRenderer] = {}
        self._animation_manager = AnimationManager(self)
    
    def add_underline_renderer(self, editor: QtWidgets.QPlainTextEdit, 
                             renderer_id: str = None) -> UnderlineRenderer:
        """为编辑器添加下划线渲染器"""
        if renderer_id is None:
            renderer_id = f"renderer_{id(editor)}"
        
        renderer = UnderlineRenderer(editor, self)
        self._underline_renderers[renderer_id] = renderer
        return renderer
    
    def get_underline_renderer(self, renderer_id: str) -> Optional[UnderlineRenderer]:
        """获取下划线渲染器"""
        return self._underline_renderers.get(renderer_id)
    
    def remove_underline_renderer(self, renderer_id: str) -> None:
        """移除下划线渲染器"""
        if renderer_id in self._underline_renderers:
            del self._underline_renderers[renderer_id]
    
    def get_animation_manager(self) -> AnimationManager:
        """获取动画管理器"""
        return self._animation_manager
    
    def update_theme(self, theme: Dict[str, str]) -> None:
        """更新所有渲染器的主题"""
        for renderer in self._underline_renderers.values():
            renderer.set_theme(theme)
    
    def set_underlines_enabled(self, enabled: bool) -> None:
        """启用或禁用所有下划线渲染"""
        for renderer in self._underline_renderers.values():
            renderer.set_enabled(enabled)