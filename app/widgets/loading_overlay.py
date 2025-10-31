from __future__ import annotations

from typing import Dict

from PySide6 import QtCore, QtGui, QtWidgets
from app.widgets.design_system import Animation


def _parse_color(value: str) -> QtGui.QColor:
    color = QtGui.QColor()
    if value.lower().startswith("rgba"):
        inside = value[value.find("(") + 1 : value.rfind(")")]
        components = [component.strip() for component in inside.split(",")]
        if len(components) == 4:
            red, green, blue, alpha = components
            red_value = int(float(red))
            green_value = int(float(green))
            blue_value = int(float(blue))
            if "." in alpha:
                alpha_value = float(alpha)
                alpha_channel = int(max(0, min(1, alpha_value)) * 255)
            else:
                alpha_channel = int(float(alpha))
            color.setRgb(red_value, green_value, blue_value, alpha_channel)
            return color
    color.setNamedColor(value)
    return color


class LoadingOverlay(QtWidgets.QWidget):
    """半透明加载遮罩层，显示 VSCode 风格旋转指示器。"""

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self._spinner_timer = QtCore.QTimer(self)
        self._spinner_timer.timeout.connect(self._handle_tick)
        self._rotation_angle = 0
        self._opacity = 0.0  # 用于淡入淡出效果

        self._overlay_color = QtGui.QColor(0, 0, 0, 180)
        self._accent_color = QtGui.QColor("#0e639c")
        self._track_color = QtGui.QColor(255, 255, 255, 30)
        
        # 淡入淡出动画
        self._fade_animation = QtCore.QPropertyAnimation(self, b"windowOpacity")
        self._fade_animation.setDuration(Animation.Duration.NORMAL)
        self._fade_animation.setEasingCurve(QtCore.QEasingCurve.InOutQuad)

        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setWindowOpacity(0.0)
        self.hide()

    def set_theme(self, theme: Dict[str, str]) -> None:
        overlay_value = theme.get("overlayBackground")
        accent_value = theme.get("accent")
        track_value = theme.get("borderColor")

        if overlay_value:
            overlay_color = _parse_color(overlay_value)
            if overlay_color.isValid():
                if overlay_color.alpha() == 0:
                    overlay_color.setAlpha(184)
                self._overlay_color = overlay_color
        if accent_value:
            accent_color = _parse_color(accent_value)
            if accent_color.isValid():
                if accent_color.alpha() == 0:
                    accent_color.setAlpha(255)
                self._accent_color = accent_color
        if track_value:
            track_color = _parse_color(track_value)
            if track_color.isValid():
                track_color.setAlpha(90)
                self._track_color = track_color
        self.update()

    def start(self) -> None:
        self._rotation_angle = 0
        if not self._spinner_timer.isActive():
            self._spinner_timer.start(16)
        self.resize(self.parent().size())
        self.show()
        self.raise_()
        
        # 淡入动画
        self._fade_animation.stop()
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.start()

    def stop(self) -> None:
        # 淡出动画
        self._fade_animation.stop()
        self._fade_animation.setStartValue(self.windowOpacity())
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.finished.connect(self._on_fade_out_finished)
        self._fade_animation.start()

    def _on_fade_out_finished(self) -> None:
        """淡出动画完成后隐藏遮罩"""
        self._spinner_timer.stop()
        self.hide()
        self._fade_animation.finished.disconnect(self._on_fade_out_finished)

    def _handle_tick(self) -> None:
        self._rotation_angle = (self._rotation_angle + 8) % 360
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802 - Qt 命名规范
        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

            painter.fillRect(self.rect(), self._overlay_color)

            center = self.rect().center()
            indicator_radius = 18
            stroke_width = 4

            painter.save()
            painter.translate(center)
            painter.rotate(self._rotation_angle)

            gradient = QtGui.QConicalGradient(QtCore.QPointF(0, 0), 0)
            gradient.setColorAt(0.0, self._accent_color)
            gradient.setColorAt(0.65, self._accent_color)
            faded_accent = QtGui.QColor(self._accent_color)
            faded_accent.setAlpha(max(30, int(self._accent_color.alpha() * 0.2)))
            gradient.setColorAt(1.0, faded_accent)

            pen = QtGui.QPen(QtGui.QBrush(gradient), stroke_width)
            pen.setCapStyle(QtCore.Qt.RoundCap)
            painter.setPen(pen)
            painter.drawArc(
                QtCore.QRectF(
                    -indicator_radius,
                    -indicator_radius,
                    indicator_radius * 2,
                    indicator_radius * 2,
                ),
                0,
                270 * 16,
            )

            track_pen = QtGui.QPen(self._track_color, stroke_width)
            track_pen.setCapStyle(QtCore.Qt.RoundCap)
            painter.setPen(track_pen)
            painter.drawArc(
                QtCore.QRectF(
                    -indicator_radius,
                    -indicator_radius,
                    indicator_radius * 2,
                    indicator_radius * 2,
                ),
                0,
                360 * 16,
            )

            painter.restore()
        finally:
            painter.end()
