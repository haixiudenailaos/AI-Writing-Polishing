"""
脉冲闪烁标签组件
用于显示"加载中..."、"优化中..."等动态状态
"""

from typing import Optional
from PySide6 import QtWidgets, QtCore, QtGui


class PulsingLabel(QtWidgets.QLabel):
    """带脉冲闪烁动画的标签
    
    特点：
    - 平滑的透明度过渡动画
    - 自动循环播放
    - 支持自定义颜色和动画速度
    """
    
    def __init__(self, text: str = "", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(text, parent)
        
        # 动画效果
        self._opacity_effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        
        # 脉冲动画
        self._pulse_animation = QtCore.QPropertyAnimation(self._opacity_effect, b"opacity")
        self._pulse_animation.setDuration(1200)  # 1.2秒一个周期
        self._pulse_animation.setStartValue(0.3)  # 最小透明度 30%
        self._pulse_animation.setEndValue(1.0)   # 最大透明度 100%
        self._pulse_animation.setEasingCurve(QtCore.QEasingCurve.InOutSine)  # 正弦曲线，更自然
        self._pulse_animation.setLoopCount(-1)  # 无限循环
        self._pulse_animation.setDirection(QtCore.QAbstractAnimation.Forward)
        
        # 使用 QVariantAnimation 实现来回脉冲
        self._pulse_animation.finished.connect(self._reverse_animation)
        
        self._is_pulsing = False
        self._forward = True
    
    def _reverse_animation(self):
        """反转动画方向以实现来回脉冲"""
        if self._is_pulsing:
            if self._forward:
                self._pulse_animation.setDirection(QtCore.QAbstractAnimation.Backward)
                self._forward = False
            else:
                self._pulse_animation.setDirection(QtCore.QAbstractAnimation.Forward)
                self._forward = True
            self._pulse_animation.start()
    
    def start_pulsing(self):
        """开始脉冲动画"""
        if not self._is_pulsing:
            self._is_pulsing = True
            self._forward = True
            self._pulse_animation.setDirection(QtCore.QAbstractAnimation.Forward)
            self._pulse_animation.start()
    
    def stop_pulsing(self):
        """停止脉冲动画"""
        self._is_pulsing = False
        self._pulse_animation.stop()
        self._opacity_effect.setOpacity(1.0)  # 恢复完全不透明
    
    def set_pulsing_text(self, text: str):
        """设置文本并开始脉冲"""
        self.setText(text)
        self.start_pulsing()
    
    def set_static_text(self, text: str):
        """设置静态文本并停止脉冲"""
        self.stop_pulsing()
        self.setText(text)
    
    def is_pulsing(self) -> bool:
        """检查是否正在脉冲"""
        return self._is_pulsing
    
    def set_pulse_duration(self, ms: int):
        """设置脉冲周期（毫秒）"""
        self._pulse_animation.setDuration(ms)
    
    def set_pulse_range(self, min_opacity: float, max_opacity: float):
        """设置透明度范围
        
        Args:
            min_opacity: 最小透明度 (0.0-1.0)
            max_opacity: 最大透明度 (0.0-1.0)
        """
        self._pulse_animation.setStartValue(max(0.0, min(1.0, min_opacity)))
        self._pulse_animation.setEndValue(max(0.0, min(1.0, max_opacity)))


class SpinnerLabel(QtWidgets.QLabel):
    """旋转加载指示器标签
    
    显示一个旋转的圆点动画，类似于现代UI的加载指示器
    """
    
    def __init__(self, text: str = "", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(text, parent)
        self._angle = 0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.setInterval(100)  # 每100ms旋转一次
        self._is_spinning = False
        self._dot_sequence = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._current_dot_index = 0
        self._base_text = ""
    
    def _rotate(self):
        """更新旋转动画"""
        self._current_dot_index = (self._current_dot_index + 1) % len(self._dot_sequence)
        dot = self._dot_sequence[self._current_dot_index]
        self.setText(f"{dot} {self._base_text}")
    
    def start_spinning(self, text: str = ""):
        """开始旋转动画"""
        if not self._is_spinning:
            self._is_spinning = True
            self._base_text = text
            self._current_dot_index = 0
            self._timer.start()
    
    def stop_spinning(self):
        """停止旋转动画"""
        self._is_spinning = False
        self._timer.stop()
        self.setText("")
    
    def set_spinning_text(self, text: str):
        """设置文本并开始旋转"""
        self.start_spinning(text)
    
    def set_static_text(self, text: str):
        """设置静态文本并停止旋转"""
        self.stop_spinning()
        self.setText(text)
    
    def is_spinning(self) -> bool:
        """检查是否正在旋转"""
        return self._is_spinning


class DotAnimationLabel(QtWidgets.QLabel):
    """点点点动画标签
    
    显示经典的"加载中..."动画，点数逐渐增加
    """
    
    def __init__(self, base_text: str = "加载中", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._base_text = base_text
        self._dot_count = 0
        self._max_dots = 3
        
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._update_dots)
        self._timer.setInterval(500)  # 每500ms更新一次
        self._is_animating = False
    
    def _update_dots(self):
        """更新点数"""
        self._dot_count = (self._dot_count + 1) % (self._max_dots + 1)
        dots = "." * self._dot_count
        self.setText(f"{self._base_text}{dots}")
    
    def start_animation(self, base_text: str = ""):
        """开始动画"""
        if base_text:
            self._base_text = base_text
        if not self._is_animating:
            self._is_animating = True
            self._dot_count = 0
            self._timer.start()
    
    def stop_animation(self):
        """停止动画"""
        self._is_animating = False
        self._timer.stop()
        self.setText("")
    
    def set_animating_text(self, text: str):
        """设置文本并开始动画"""
        self.start_animation(text)
    
    def set_static_text(self, text: str):
        """设置静态文本并停止动画"""
        self.stop_animation()
        self.setText(text)
    
    def is_animating(self) -> bool:
        """检查是否正在动画"""
        return self._is_animating
    
    def set_max_dots(self, max_dots: int):
        """设置最大点数"""
        self._max_dots = max(1, max_dots)

