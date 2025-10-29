from __future__ import annotations

"""
设计系统（Design System）
提供统一的尺寸、排版、圆角、动画与常用效果，便于在各个控件中保持一致的高品质视觉与交互体验。
"""

from PySide6 import QtCore, QtGui, QtWidgets


class Animation:
    """动画相关的统一常量。"""

    class Duration:
        """统一的动画时长（毫秒）。"""

        MICRO = 120
        FAST = 180
        NORMAL = 300
        SLOW = 450
        LONG = 600

    class Easing:
        """常用缓动曲线。"""

        DEFAULT = QtCore.QEasingCurve.InOutCubic
        EMPHASIZED = QtCore.QEasingCurve.OutCubic
        GENTLE = QtCore.QEasingCurve.InOutQuad


class Spacing:
    """统一的间距尺度（像素）。"""

    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 20
    XXL = 24


class BorderRadius:
    """统一的圆角尺度（像素）。"""

    SM = 4
    MD = 6
    LG = 8


class Typography:
    """排版体系：字号与字重。"""

    class FontSize:
        XS = 11
        SM = 12
        BASE = 13
        LG = 14
        XL = 16

    class FontWeight:
        LIGHT = 300
        REGULAR = 400
        MEDIUM = 500
        BOLD = 600


class Elevation:
    """阴影层级与默认参数。"""

    @staticmethod
    def apply_shadow(
        widget: QtWidgets.QWidget,
        blur_radius: int = 16,
        offset_x: int = 0,
        offset_y: int = 3,
        color: QtGui.QColor | None = None,
    ) -> None:
        """为给定控件应用统一的投影效果。"""
        effect = QtWidgets.QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur_radius)
        effect.setOffset(offset_x, offset_y)
        if color is None:
            color = QtGui.QColor(0, 0, 0, 80)
        effect.setColor(color)
        widget.setGraphicsEffect(effect)


def set_widget_rounded_background(
    widget: QtWidgets.QWidget,
    background: str,
    border: str,
    radius: int = BorderRadius.LG,
) -> None:
    """快捷设置带圆角与边框的背景样式。"""
    widget.setStyleSheet(
        "\n".join(
            [
                f"QWidget#{widget.objectName()} {{",
                f"  background-color: {background};",
                f"  border: 1px solid {border};",
                f"  border-radius: {radius}px;",
                "}",
            ]
        )
    )







