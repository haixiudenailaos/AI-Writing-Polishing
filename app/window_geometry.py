from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

from app.config_manager import ConfigManager


class WindowGeometryManager:
    """负责主窗口的几何信息持久化与恢复，含多屏与DPI自适应修正。"""

    def __init__(self, config_manager: ConfigManager) -> None:
        self._config_manager = config_manager

    def apply_initial_geometry(self, window: QtWidgets.QMainWindow) -> None:
        """在首次显示前调用：尽力恢复上次几何；若无记录，使用专业默认值并居中。"""
        state = self._get_state()
        screen = self._pick_target_screen(state)
        available = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1280, 800)

        # 默认：工作区的 80%，并设置合理最小尺寸
        default_size = self._clamp_size(
            QtCore.QSize(int(available.width() * 0.8), int(available.height() * 0.8)),
            available
        )
        window.setMinimumSize(960, 640)

        if not state:
            # 首次运行，居中显示
            self._center_on_screen(window, available, default_size)
            return

        # 恢复大小与位置
        is_max = bool(state.get("is_maximized", False))
        x = int(state.get("x", available.x()))
        y = int(state.get("y", available.y()))
        w = int(state.get("w", default_size.width()))
        h = int(state.get("h", default_size.height()))

        rect = QtCore.QRect(x, y, w, h)
        rect = self._ensure_onscreen(rect, available)

        window.setGeometry(rect)
        if is_max:
            # 先设置几何再最大化，避免跨屏错位
            window.showMaximized()

    def save_geometry(self, window: QtWidgets.QMainWindow) -> None:
        """保存当前窗口几何信息到配置。"""
        cfg = self._config_manager.get_config()

        is_maximized = window.isMaximized()
        # 使用 normalGeometry 确保最大化状态下也记录还原前的尺寸
        rect = window.normalGeometry() if is_maximized else window.frameGeometry()

        # 当前屏幕标识
        screen = window.screen() or QtWidgets.QApplication.primaryScreen()
        screen_name = screen.name() if screen else ""

        new_state: Dict[str, Any] = {
            "x": int(rect.x()),
            "y": int(rect.y()),
            "w": int(rect.width()),
            "h": int(rect.height()),
            "is_maximized": bool(is_maximized),
            "screen": screen_name,
        }

        cfg.window_state = new_state
        self._config_manager.save_config()

    # ---------- 内部工具 ----------

    def _get_state(self) -> Dict[str, Any]:
        try:
            return dict(self._config_manager.get_config().window_state or {})
        except Exception:
            return {}

    def _pick_target_screen(self, state: Optional[Dict[str, Any]]) -> Optional[QtGui.QScreen]:
        app = QtWidgets.QApplication.instance()
        if app is None:
            return None

        screens = app.screens()
        if not screens:
            return None

        # 优先使用记录的屏幕名称
        if state:
            target_name = state.get("screen", "")
            for s in screens:
                try:
                    if s.name() == target_name and target_name:
                        return s
                except Exception:
                    pass

        # 其次使用当前鼠标所在屏幕
        try:
            cursor_pos = QtGui.QCursor.pos()
            for s in screens:
                if s.geometry().contains(cursor_pos):
                    return s
        except Exception:
            pass

        # 回退主屏
        try:
            return QtWidgets.QApplication.primaryScreen()
        except Exception:
            return screens[0]

    def _center_on_screen(self, window: QtWidgets.QMainWindow, available: QtCore.QRect,
                           size: QtCore.QSize) -> None:
        size = self._clamp_size(size, available)
        x = available.x() + (available.width() - size.width()) // 2
        y = available.y() + (available.height() - size.height()) // 2
        window.setGeometry(QtCore.QRect(x, y, size.width(), size.height()))

    def _ensure_onscreen(self, rect: QtCore.QRect, available: QtCore.QRect) -> QtCore.QRect:
        # 若尺寸超出工作区，则按 90% 缩放到可用范围
        width = min(rect.width(), int(available.width() * 0.9))
        height = min(rect.height(), int(available.height() * 0.9))
        if width < 640:
            width = 640
        if height < 480:
            height = 480

        x = rect.x()
        y = rect.y()

        # 纠正位置：确保至少 80px 边界在可见范围内
        min_visible = 80
        if x + min_visible > available.right():
            x = available.right() - min_visible
        if y + min_visible > available.bottom():
            y = available.bottom() - min_visible
        if x + width - min_visible < available.left():
            x = available.left() + min_visible - width
        if y + height - min_visible < available.top():
            y = available.top() + min_visible - height

        # 如果仍然完全不可见，则居中
        rect_candidate = QtCore.QRect(x, y, width, height)
        if not rect_candidate.intersects(available):
            x = available.x() + (available.width() - width) // 2
            y = available.y() + (available.height() - height) // 2

        return QtCore.QRect(x, y, width, height)

    def _clamp_size(self, size: QtCore.QSize, available: QtCore.QRect) -> QtCore.QSize:
        width = min(size.width(), int(available.width() * 0.95))
        height = min(size.height(), int(available.height() * 0.95))
        width = max(width, 960)
        height = max(height, 640)
        return QtCore.QSize(width, height)


