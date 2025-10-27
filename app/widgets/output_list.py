from __future__ import annotations

from typing import Callable, Dict, Iterable

from PyQt5 import QtCore, QtGui, QtWidgets

from widgets.theme_manager import THEME_CATALOG


def _parse_color(value: str) -> QtGui.QColor:
    color = QtGui.QColor()
    if value.startswith("#"):
        color.setNamedColor(value)
        return color
    if value.lower().startswith("rgba"):
        component_text = value[value.find("(") + 1 : value.rfind(")")]
        components = [part.strip() for part in component_text.split(",")]
        if len(components) == 4:
            red, green, blue, alpha = components
            alpha_value = float(alpha) if "." in alpha else int(alpha)
            red_value = int(float(red))
            green_value = int(float(green))
            blue_value = int(float(blue))
            alpha_channel = int(alpha_value * 255 if alpha_value <= 1 else alpha_value)
            color.setRgb(red_value, green_value, blue_value, alpha_channel)
            return color
    color.setNamedColor(value)
    return color


def _code_font() -> QtGui.QFont:
    font = QtGui.QFont("Cascadia Mono", 11)
    font.setStyleHint(QtGui.QFont.Monospace)
    font.setFixedPitch(True)
    return font


class OutputItemWidget(QtWidgets.QWidget):
    def __init__(
        self,
        text: str,
        is_original: bool,
        theme: Dict[str, str],
        on_accept: Callable[[], None],
        on_reject: Callable[[], None],
        on_reuse: Callable[[str], None],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._is_original = is_original
        self._theme = dict(theme)
        self._on_accept = on_accept
        self._on_reject = on_reject
        self._on_reuse = on_reuse

        self._line_indicator: QtWidgets.QFrame | None = None
        self._text_browser: QtWidgets.QTextBrowser | None = None
        self._accept_button: QtWidgets.QPushButton | None = None
        self._reject_button: QtWidgets.QPushButton | None = None
        self._reuse_button: QtWidgets.QPushButton | None = None
        self._shadow_effect: QtWidgets.QGraphicsDropShadowEffect | None = None

        self._build_ui()
        self.update_theme(self._theme)

    def _build_ui(self) -> None:
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 16, 8)
        layout.setSpacing(16)

        self._line_indicator = QtWidgets.QFrame(self)
        self._line_indicator.setFixedWidth(4)
        self._line_indicator.setObjectName("lineIndicator")

        self._text_browser = QtWidgets.QTextBrowser(self)
        self._text_browser.setReadOnly(True)
        self._text_browser.setOpenExternalLinks(False)
        self._text_browser.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._text_browser.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._text_browser.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self._text_browser.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self._text_browser.setPlainText(self._text)
        self._text_browser.document().setDefaultFont(_code_font())
        self._text_browser.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self._text_browser.setMinimumHeight(54)
        self._text_browser.setFont(_code_font())
        # 轻量阴影效果，卡片化视觉
        self._shadow_effect = QtWidgets.QGraphicsDropShadowEffect(self)
        self._shadow_effect.setBlurRadius(12)
        self._shadow_effect.setOffset(0, 2)
        self._text_browser.setGraphicsEffect(self._shadow_effect)

        button_container = QtWidgets.QWidget(self)
        button_layout = QtWidgets.QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(6)

        self._accept_button = QtWidgets.QPushButton("接受", button_container)
        self._accept_button.setObjectName("acceptButton")
        self._accept_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._accept_button.clicked.connect(self._handle_accept)

        self._reject_button = QtWidgets.QPushButton("拒绝", button_container)
        self._reject_button.setObjectName("rejectButton")
        self._reject_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._reject_button.clicked.connect(self._handle_reject)

        self._reuse_button = QtWidgets.QPushButton("再次润色", button_container)
        self._reuse_button.setObjectName("reuseButton")
        self._reuse_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._reuse_button.clicked.connect(self._handle_reuse)

        for button in (self._accept_button, self._reject_button, self._reuse_button):
            button.setFixedWidth(92)

        button_layout.addWidget(self._accept_button)
        button_layout.addWidget(self._reject_button)
        button_layout.addWidget(self._reuse_button)
        button_layout.addStretch(1)

        layout.addWidget(self._line_indicator)
        layout.addWidget(self._text_browser, 1)
        layout.addWidget(button_container, 0, QtCore.Qt.AlignTop)

    def update_theme(self, theme: Dict[str, str]) -> None:
        theme_key = theme.get("key")
        if theme_key not in THEME_CATALOG:
            theme = THEME_CATALOG.get("dark", theme)
        self._theme = dict(theme)
        accent_color = _parse_color(self._theme["accent"])
        foreground_color = _parse_color(self._theme["outputForeground"])
        original_background = _parse_color(self._theme["originalBackground"])
        polished_background = _parse_color(self._theme["polishedBackground"])
        button_background = _parse_color(self._theme["buttonBackground"])
        button_foreground = _parse_color(self._theme["buttonForeground"])
        border_color = _parse_color(self._theme["borderColor"])

        line_color = QtGui.QColor("#f14c4c" if self._is_original else "#6a9955")
        if self._line_indicator is not None:
            self._line_indicator.setStyleSheet(
                f"QFrame#lineIndicator {{ background-color: {line_color.name()}; border-radius: 2px; }}"
            )

        if self._text_browser is not None:
            background_color = original_background if self._is_original else polished_background
            self._text_browser.setFont(_code_font())
            self._text_browser.viewport().setAutoFillBackground(False)
            self._text_browser.document().setPlainText(self._text)
            scrollbar_track = background_color.darker(120)
            scrollbar_handle = accent_color
            # 阴影颜色随主题调整（暗色更明显，亮色更轻）
            if self._shadow_effect is not None:
                if theme_key == "light":
                    self._shadow_effect.setColor(QtGui.QColor(0, 0, 0, 40))
                else:
                    self._shadow_effect.setColor(QtGui.QColor(0, 0, 0, 80))
            self._text_browser.setStyleSheet(
                "\n".join(
                    [
                        "QTextBrowser {",
                        f"  background-color: {background_color.name()};",
                        f"  color: {foreground_color.name()};",
                        f"  border: 1px solid {border_color.name()};",
                        "  border-radius: 6px;",
                        "  padding: 8px 10px;",
                        "  selection-background-color: rgba(14, 99, 156, 0.45);",
                        "  selection-color: #ffffff;",
                        "}",
                        "QTextBrowser QScrollBar:vertical {",
                        "  width: 6px;",
                        f"  background: {scrollbar_track.name()};",
                        "  margin: 0px;",
                        "  border-radius: 3px;",
                        "}",
                        "QTextBrowser QScrollBar::handle:vertical {",
                        f"  background: {scrollbar_handle.name()};",
                        "  border-radius: 3px;",
                        "}",
                        "QTextBrowser QScrollBar::add-line:vertical,",
                        "QTextBrowser QScrollBar::sub-line:vertical {",
                        "  height: 0px;",
                        "  border: none;",
                        "}",
                    ]
                )
            )

        button_style = "\n".join(
            [
                "QPushButton {",
                f"  background-color: {button_background.name()};",
                f"  color: {button_foreground.name()};",
                f"  border: 1px solid {border_color.name()};",
                "  border-radius: 3px;",
                "  padding: 4px 0;",
                "  font-size: 12px;",
                "  font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;",
                "}",
                "QPushButton:hover {",
                f"  background-color: {accent_color.name()};",
                "  color: #ffffff;",
                "}",
                "QPushButton:pressed {",
                f"  background-color: {accent_color.darker(120).name()};",
                "}",
            ]
        )

        if self._accept_button is not None:
            self._accept_button.setStyleSheet(button_style)
        if self._reject_button is not None:
            self._reject_button.setStyleSheet(button_style)
        if self._reuse_button is not None:
            self._reuse_button.setStyleSheet(button_style)

    def trigger_accept(self) -> None:
        self._handle_accept()

    def trigger_reject(self) -> None:
        self._handle_reject()

    def trigger_reuse(self) -> None:
        self._handle_reuse()

    def _handle_accept(self) -> None:
        if callable(self._on_accept):
            self._on_accept()

    def _handle_reject(self) -> None:
        if callable(self._on_reject):
            self._on_reject()

    def _handle_reuse(self) -> None:
        if callable(self._on_reuse):
            self._on_reuse(self._text)

    def update_text(self, text: str) -> None:
        self._text = text
        if self._text_browser is not None:
            self._text_browser.setPlainText(text)


class OutputListWidget(QtWidgets.QListWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme: Dict[str, str] | None = None
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.setSpacing(6)
        self.setUniformItemSizes(False)
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)

    def add_entry(
        self,
        text: str,
        is_original: bool,
        theme: Dict[str, str],
        on_accept: Callable[[], None],
        on_reject: Callable[[], None],
        on_reuse: Callable[[str], None],
    ) -> QtWidgets.QListWidgetItem:
        item = QtWidgets.QListWidgetItem()
        item.setFlags(item.flags() | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        widget_theme = self._theme or theme
        widget = OutputItemWidget(text, is_original, widget_theme, on_accept, on_reject, on_reuse, self)
        item.setSizeHint(widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, widget)
        return item

    def iter_item_widgets(self) -> Iterable[OutputItemWidget]:
        for index in range(self.count()):
            widget = self.itemWidget(self.item(index))
            if isinstance(widget, OutputItemWidget):
                yield widget

    def update_theme(self, theme: Dict[str, str]) -> None:
        self._theme = dict(theme)
        background_color = _parse_color(theme["panelBackground"])
        border_color = _parse_color(theme["borderColor"])
        self.setStyleSheet(
            "\n".join(
                [
                    "QListWidget {",
                    f"  background-color: {background_color.name()};",
                    "  border: none;",
                    "  padding: 0;",
                    "}",
                    "QListWidget::item {",
                    "  margin: 4px 0;",
                    "}",
                    "QListWidget::item:selected {",
                    f"  background: {border_color.lighter(120).name()};",
                    "}",
                    "QListWidget QScrollBar:vertical {",
                    "  width: 8px;",
                    f"  background: {background_color.darker(110).name()};",
                    "  margin: 0;",
                    "  border-radius: 4px;",
                    "}",
                    "QListWidget QScrollBar::handle:vertical {",
                    f"  background: {_parse_color(theme['accent']).name()};",
                    "  border-radius: 4px;",
                    "}",
                    "QListWidget QScrollBar::add-line:vertical,",
                    "QListWidget QScrollBar::sub-line:vertical {",
                    "  height: 0px;",
                    "  border: none;",
                    "}",
                ]
            )
        )
        for widget in self.iter_item_widgets():
            widget.update_theme(self._theme)

    def accept_current(self) -> bool:
        item = self.currentItem()
        if not item:
            return False
        widget = self.itemWidget(item)
        if isinstance(widget, OutputItemWidget):
            widget.trigger_accept()
            return True
        return False

    def reject_current(self) -> bool:
        item = self.currentItem()
        if not item:
            return False
        widget = self.itemWidget(item)
        if isinstance(widget, OutputItemWidget):
            widget.trigger_reject()
            return True
        return False

    def reuse_current(self) -> bool:
        item = self.currentItem()
        if not item:
            return False
        widget = self.itemWidget(item)
        if isinstance(widget, OutputItemWidget):
            widget.trigger_reuse()
            return True
        return False

    def remove_item(self, item: QtWidgets.QListWidgetItem) -> None:
        row = self.row(item)
        widget = self.itemWidget(item)
        if widget is not None:
            widget.deleteLater()
        self.takeItem(row)

    def clear_entries(self) -> None:
        while self.count() > 0:
            item = self.item(0)
            self.remove_item(item)

    def sizeHint(self) -> QtCore.QSize:
        hint = super().sizeHint()
        return QtCore.QSize(hint.width(), max(hint.height(), 220))
