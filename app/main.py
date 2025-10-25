from __future__ import annotations

import itertools
import sys
from pathlib import Path
from typing import Dict, Optional

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog
from dotenv import load_dotenv

from api_client import AIClient, AIError
from widgets.loading_overlay import LoadingOverlay
from widgets.output_list import OutputListWidget
from widgets.theme_manager import ThemeManager
from widgets.settings_dialog import SettingsDialog
from config_manager import ConfigManager
from style_manager import StyleManager
from text_processor import TextProcessor

OUTPUT_ITEM_ROLE = QtCore.Qt.UserRole + 1


class LineNumberArea(QtWidgets.QWidget):
    def __init__(self, editor: "VsCodeEditor") -> None:
        super().__init__(editor)
        self._editor = editor
        self.setObjectName("LineNumberArea")

    def sizeHint(self) -> QtCore.QSize:  # type: ignore[override]
        return QtCore.QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
        self._editor.paint_line_number_area(event)


class VsCodeEditor(QtWidgets.QPlainTextEdit):
    enterPressed = QtCore.pyqtSignal()
    tabPressed = QtCore.pyqtSignal()
    quickRejectPressed = QtCore.pyqtSignal()
    textPolishRequested = QtCore.pyqtSignal(str)  # 新增：请求润色信号
    inputStoppedForPrediction = QtCore.pyqtSignal()  # 新增：输入停止3秒信号，用于触发剧情预测

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._current_theme: Dict[str, str] | None = None
        self._line_number_area = LineNumberArea(self)
        
        # 导入UI增强模块
        from widgets.ui_enhancer import UnderlineRenderer
        self._underline_renderer = UnderlineRenderer(self)

        self.setObjectName("VsCodeEditor")
        self.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setTabChangesFocus(False)
        self.setCenterOnScroll(True)
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)  # 修改为自动换行
        
        # 记录上一次的行数，用于检测行数变化
        self._previous_block_count = 0
        
        # 输入停止检测定时器（3秒）
        self._input_stop_timer = QtCore.QTimer(self)
        self._input_stop_timer.setSingleShot(True)
        self._input_stop_timer.setInterval(3000)  # 3秒 = 3000ms
        self._input_stop_timer.timeout.connect(self._on_input_stopped)

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._handle_update_request)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.textChanged.connect(self._on_text_changed)  # 新增：监听文本变化
        self.blockCountChanged.connect(self._on_block_count_changed)  # 新增：监听行数变化

        self._configure_editor()
        self._update_line_number_area_width(0)
        self._highlight_current_line()

    def _configure_editor(self) -> None:
        editor_font = QtGui.QFont()
        editor_font.setFamily("Cascadia Code")
        editor_font.setPointSize(12)
        editor_font.setStyleHint(QtGui.QFont.Monospace)
        editor_font.setFixedPitch(True)
        self.setFont(editor_font)

        metrics = QtGui.QFontMetrics(editor_font)
        self.setTabStopDistance(metrics.horizontalAdvance(" ") * 4)
        document_options = self.document().defaultTextOption()
        document_options.setWrapMode(QtGui.QTextOption.NoWrap)
        self.document().setDefaultTextOption(document_options)
        self.setPlaceholderText("在此输入待润色的长文本，按 Enter 键提交到 AI 进行润色…")

    def line_number_area_width(self) -> int:
        block_count = max(1, self.blockCount())
        digits = len(str(block_count))
        space = self.fontMetrics().horizontalAdvance("9") * digits
        return space + 16

    def _update_line_number_area_width(self, _: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _handle_update_request(self, rect: QtCore.QRect, dy: int) -> None:
        if dy != 0:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(self.blockCount())

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        content_rect = self.contentsRect()
        self._line_number_area.setGeometry(
            QtCore.QRect(content_rect.left(), content_rect.top(), self.line_number_area_width(), content_rect.height())
        )

    def paint_line_number_area(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self._line_number_area)
        background_color = self._theme_color("lineNumberBackground", "#252526")
        foreground_color = self._theme_color("lineNumberForeground", "#858585")
        painter.fillRect(event.rect(), background_color)
        painter.setPen(foreground_color)
        painter.setFont(self.font())

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        line_height = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 6,
                    line_height,
                    QtCore.Qt.AlignRight,
                    str(block_number + 1),
                )
            block = block.next()
            block_number += 1
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())

    def _highlight_current_line(self) -> None:
        if self.isReadOnly():
            self.setExtraSelections([])
            return
        highlight_color = self._theme_color("selection", "#264f78")
        highlight_color.setAlphaF(0.15)
        selection = QtWidgets.QTextEdit.ExtraSelection()
        selection.format.setBackground(highlight_color)
        selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # type: ignore[override]
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and event.modifiers() == QtCore.Qt.NoModifier:
            # Enter键行为：先插入换行符，然后触发润色
            # 1. 执行默认的换行操作
            super().keyPressEvent(event)
            # 2. 发送enterPressed信号让主窗口处理润色逻辑
            self.enterPressed.emit()
            event.accept()
            return
        if event.key() == QtCore.Qt.Key_Tab and event.modifiers() == QtCore.Qt.NoModifier:
            self.tabPressed.emit()
            event.accept()
            return
        if event.key() in (QtCore.Qt.Key_QuoteLeft, QtCore.Qt.Key_AsciiTilde) and event.modifiers() == QtCore.Qt.NoModifier:
            self.quickRejectPressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def update_theme(self, theme: Dict[str, str]) -> None:
        self._current_theme = dict(theme)
        base_color = self._theme_color("editorBackground", "#1e1e1e")
        text_color = self._theme_color("editorForeground", "#d4d4d4")
        selection_color = self._theme_color("selection", "#264f78")
        accent_color = self._theme_color("accent", "#007acc")  # 获取主题accent颜色

        palette = self.palette()
        palette.setColor(QtGui.QPalette.Base, base_color)
        palette.setColor(QtGui.QPalette.Text, text_color)
        palette.setColor(QtGui.QPalette.Highlight, selection_color)
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#ffffff"))
        self.setPalette(palette)
        self.viewport().setPalette(palette)
        self.viewport().setAutoFillBackground(True)
        
        # 更新下划线渲染器的颜色
        if hasattr(self, '_underline_renderer'):
            self._underline_renderer.set_underline_color(accent_color)
        
        self._line_number_area.update()
        self.viewport().update()
        self._highlight_current_line()
    
    def _on_text_changed(self):
        """文本变化时的处理 - 重启输入停止定时器"""
        # 每次文本变化时，重启定时器
        self._input_stop_timer.stop()
        self._input_stop_timer.start()
    
    def _on_input_stopped(self):
        """输入停止3秒后触发的回调"""
        # 发送信号通知主窗口
        self.inputStoppedForPrediction.emit()
    
    def _on_block_count_changed(self, new_block_count: int):
        """行数变化时的处理 - 通知主窗口调整行号"""
        if hasattr(self, '_previous_block_count') and self._previous_block_count > 0:
            delta = new_block_count - self._previous_block_count
            if delta != 0:
                # 发送信号通知主窗口调整行号
                # 获取当前光标位置
                cursor = self.textCursor()
                changed_line = cursor.blockNumber()
                
                # 触发自定义信号（需要在主窗口中处理）
                if hasattr(self.parent(), 'on_editor_line_count_changed'):
                    self.parent().on_editor_line_count_changed(changed_line, delta)
        
        self._previous_block_count = new_block_count
    
    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """重写绘制事件"""
        super().paintEvent(event)

    def _theme_color(self, key: str, fallback_hex: str) -> QtGui.QColor:
        if self._current_theme and key in self._current_theme:
            candidate = QtGui.QColor(self._current_theme[key])
            if candidate.isValid():
                return candidate
        fallback = QtGui.QColor(fallback_hex)
        if fallback.isValid():
            return fallback
        return QtGui.QColor("#1e1e1e")


class WorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)


class PolishWorker(QtCore.QRunnable):
    def __init__(self, client: AIClient, context_lines: list[str], target_line: str, style_prompt: Optional[str] = None) -> None:
        super().__init__()
        self._client = client
        self._context_lines = context_lines
        self._target_line = target_line
        self._style_prompt = style_prompt
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            polished_text = self._client.polish_last_line(self._context_lines, self._target_line, self._style_prompt)
        except AIError as exception:
            self.signals.error.emit(str(exception))
        except Exception as exception:  # noqa: BLE001
            self.signals.error.emit(f"未知错误：{exception}")
        else:
            self.signals.finished.emit(polished_text)


class PlotPredictionWorker(QtCore.QRunnable):
    """剧情预测工作线程"""
    def __init__(self, client: AIClient, full_text: str) -> None:
        super().__init__()
        self._client = client
        self._full_text = full_text
        self.signals = WorkerSignals()
    
    def run(self) -> None:
        try:
            predicted_text = self._client.predict_plot_continuation(self._full_text)
        except AIError as exception:
            self.signals.error.emit(str(exception))
        except Exception as exception:  # noqa: BLE001
            self.signals.error.emit(f"未知错误：{exception}")
        else:
            self.signals.finished.emit(predicted_text)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VSCode风格小说润色器")
        self.resize(1100, 720)

        # 初始化配置管理器
        self._config_manager = ConfigManager()
        self._style_manager = StyleManager(self._config_manager)
        self._text_processor = TextProcessor()
        
        self._theme_manager = ThemeManager()
        self._current_theme: Dict[str, str] = self._theme_manager.getCurrentTheme()
        
        # 使用配置管理器初始化API客户端
        self._api_client = AIClient(config_manager=self._config_manager)
        
        # 初始化异步润色处理器和心跳管理器
        from processors.async_polish_processor import AsyncPolishProcessor, HeartbeatManager
        self._async_polish_processor = AsyncPolishProcessor(self._api_client, self)
        self._heartbeat_manager = HeartbeatManager(self._api_client, 30, self)
        
        self._thread_pool = QtCore.QThreadPool.globalInstance()
        self._polish_in_progress = False
        self._group_sequence = itertools.count(1)
        self._pending_group_id: Optional[int] = None
        self._current_polish_line: int = -1  # 记录当前正在润色的行号

        self._central_container: Optional[QtWidgets.QWidget] = None
        self._header_frame: Optional[QtWidgets.QFrame] = None
        self._theme_selector: Optional[QtWidgets.QComboBox] = None
        self._message_label: Optional[QtWidgets.QLabel] = None
        self._overlay: Optional[LoadingOverlay] = None
        self._message_timer = QtCore.QTimer(self)
        self._message_timer.setSingleShot(True)

        self.editor = VsCodeEditor(self)
        self.output_list = OutputListWidget(self)
        self.output_list.setFocusPolicy(QtCore.Qt.StrongFocus)
        
        # 初始化润色结果面板
        from widgets.polish_result_panel import PolishResultPanel
        self.polish_result_panel = PolishResultPanel(self)
        
        # 初始化动画管理器
        from widgets.ui_enhancer import AnimationManager
        self.animation_manager = AnimationManager(self)

        self._build_ui()
        self._connect_signals()

        self._theme_manager.themeChanged.connect(self._apply_theme)
        self._theme_manager.emitCurrentTheme()
    
    def on_editor_line_count_changed(self, changed_line: int, delta: int) -> None:
        """处理编辑器行数变化 - 调整润色结果面板中的行号
        
        Args:
            changed_line: 发生变化的行号
            delta: 行数变化量（正数表示插入，负数表示删除）
        """
        if hasattr(self, 'polish_result_panel'):
            self.polish_result_panel.adjust_line_numbers(changed_line, delta)

    def _build_ui(self) -> None:
        central_container = QtWidgets.QFrame()
        central_container.setObjectName("CentralContainer")
        central_layout = QtWidgets.QVBoxLayout(central_container)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        header_frame = QtWidgets.QFrame()
        header_frame.setObjectName("HeaderFrame")
        header_layout = QtWidgets.QHBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 8, 16, 6)
        header_layout.setSpacing(12)
        header_frame.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        header_frame.setFixedHeight(44)
        title_label = QtWidgets.QLabel("小说润色")
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)

        theme_selector = QtWidgets.QComboBox()
        theme_selector.setObjectName("ThemeSelector")
        theme_selector.setMinimumWidth(160)
        theme_selector.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        for theme_key, theme_data in self._theme_manager.getAvailableThemes():
            theme_selector.addItem(theme_data.get("label", theme_key), theme_key)

        # 设置按钮
        settings_button = QtWidgets.QPushButton("设置")
        settings_button.setObjectName("SettingsButton")
        settings_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        export_button = QtWidgets.QPushButton("导出文本")
        export_button.setObjectName("ExportButton")
        export_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        quick_reject_button = QtWidgets.QPushButton("快速拒绝 (~)")
        quick_reject_button.setObjectName("QuickRejectButton")
        quick_reject_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        message_label = QtWidgets.QLabel()
        message_label.setObjectName("MessageLabel")
        message_label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)

        header_layout.addWidget(title_label)
        header_layout.addSpacing(12)
        header_layout.addWidget(theme_selector, 0)
        header_layout.addWidget(settings_button, 0)
        header_layout.addWidget(export_button, 0)
        header_layout.addWidget(quick_reject_button, 0)
        header_layout.addStretch(1)
        header_layout.addWidget(message_label, 0)

        # 创建主分割器（水平）- 左侧编辑器，右侧润色结果和输出列表
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_splitter.setObjectName("MainSplitter")
        main_splitter.setHandleWidth(3)
        
        # 左侧：编辑器
        main_splitter.addWidget(self.editor)
        
        # 右侧：创建垂直分割器包含润色结果面板和输出列表
        right_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        right_splitter.setObjectName("RightSplitter")
        right_splitter.setHandleWidth(3)
        right_splitter.addWidget(self.polish_result_panel)
        right_splitter.addWidget(self.output_list)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)
        right_splitter.setChildrenCollapsible(False)
        right_splitter.setSizes([300, 300])
        
        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 2)  # 编辑器占2份
        main_splitter.setStretchFactor(1, 1)  # 右侧面板占1份
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setSizes([700, 350])

        central_layout.addWidget(header_frame)
        central_layout.addWidget(main_splitter)
        central_layout.setStretch(0, 0)
        central_layout.setStretch(1, 1)
        overlay = LoadingOverlay(central_container)
        overlay.hide()
        overlay.set_theme(self._current_theme)

        self._central_container = central_container
        self._header_frame = header_frame
        self._theme_selector = theme_selector
        self._settings_button = settings_button
        self._export_button = export_button
        self._quick_reject_button = quick_reject_button
        self._message_label = message_label
        self._overlay = overlay

        self.setCentralWidget(central_container)

    def _connect_signals(self) -> None:
        # 原有信号连接
        self.editor.enterPressed.connect(self._on_editor_enter)
        self.editor.tabPressed.connect(self._on_editor_tab)
        self.editor.quickRejectPressed.connect(self._on_quick_reject)
        self.output_list.itemSelectionChanged.connect(self._on_output_selection_changed)
        
        # 新增：连接输入停止信号，用于剧情预测
        self.editor.inputStoppedForPrediction.connect(self._on_input_stopped_for_prediction)
        
        # 连接异步润色处理器信号
        self._async_polish_processor.polish_started.connect(self._on_async_polish_started)
        self._async_polish_processor.polish_progress.connect(self._on_async_polish_progress)
        self._async_polish_processor.polish_completed.connect(self._on_async_polish_completed)
        self._async_polish_processor.polish_failed.connect(self._on_async_polish_failed)
        
        # 连接心跳管理器信号
        self._heartbeat_manager.connection_status_changed.connect(self._on_connection_status_changed)
        self._heartbeat_manager.heartbeat_failed.connect(self._on_heartbeat_failed)
        
        # 连接润色结果面板信号
        self.polish_result_panel.acceptResult.connect(self._on_overwrite_requested)
        self.polish_result_panel.rejectResult.connect(self._on_reject_requested)
        
        if self._theme_selector is not None:
            self._theme_selector.currentIndexChanged.connect(self._on_theme_selector_changed)
        if getattr(self, "_settings_button", None) is not None:
            self._settings_button.clicked.connect(self._on_settings_clicked)
        if getattr(self, "_export_button", None) is not None:
            self._export_button.clicked.connect(self._on_export_clicked)
        if getattr(self, "_quick_reject_button", None) is not None:
            self._quick_reject_button.clicked.connect(self._on_quick_reject)
        self._message_timer.timeout.connect(self._clear_status_message)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._overlay is not None and self._central_container is not None:
            self._overlay.resize(self._central_container.size())

    def _on_editor_enter(self) -> None:
        """处理Enter键：获取刚输入完成的行（上一行）并进行异步润色"""
        # 因为Enter键已经插入了换行，所以当前光标在新的一行
        # 我们需要获取上一行（刚输入完成的行）
        cursor = self.editor.textCursor()
        current_block = cursor.blockNumber()
        
        # 如果当前在第一行，说明没有上一行可以润色
        if current_block == 0:
            return
        
        # 移动到上一行（刚输入完成的行）
        previous_block = current_block - 1
        previous_block_obj = self.editor.document().findBlockByNumber(previous_block)
        previous_line = previous_block_obj.text().strip()
        
        # 检查上一行是否有内容
        if not previous_line:
            return
        
        # 获取上下文（上一行之前的最多5行）
        full_text = self.editor.toPlainText()
        lines = full_text.splitlines()
        
        # 获取上下文行（上一行之前的最多5行）
        start_context = max(0, previous_block - 5)
        context_lines = lines[start_context:previous_block] if previous_block > 0 else []
        
        # 异步润色，不阻塞界面，不显示加载遮罩
        # 调用异步润色，传入上下文和上一行
        request_id = self._polish_text_with_context_async(context_lines, previous_line, previous_block)
        
        # 保存当前正在润色的行号，用于后续替换
        self._current_polish_line = previous_block

    def _on_editor_tab(self) -> None:
        # 优先处理润色结果面板中的内容
        if self.polish_result_panel.get_result_count() > 0:
            self._on_overwrite_requested()
        elif not self.output_list.accept_current():
            self._show_message("没有可确认的润色结果。", duration_ms=1600, is_error=False)

    def _on_quick_reject(self) -> None:
        # 优先处理润色结果面板中的内容
        if self.polish_result_panel.get_result_count() > 0:
            self._on_reject_requested()
        elif not self.output_list.reject_current():
            self._show_message("没有可拒绝的润色候选。", duration_ms=2000, is_error=True)

    def _on_settings_clicked(self) -> None:
        """打开设置对话框"""
        dialog = SettingsDialog(self._config_manager, self._style_manager, self)
        dialog.set_theme(self._current_theme)
        
        # 连接配置变化信号
        dialog.configChanged.connect(self._on_config_changed)
        
        dialog.exec_()

    def _on_config_changed(self) -> None:
        """配置变化回调"""
        # 更新API客户端配置
        self._api_client.update_config(self._config_manager)
        self._show_message("配置已更新", duration_ms=2000, is_error=False)

    def _on_export_clicked(self) -> None:
        text = self.editor.toPlainText()
        if not text.strip():
            self._show_message("没有可导出的文本内容。", duration_ms=2000, is_error=True)
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出文本",
            "novel_text.txt",
            "文本文件 (*.txt);;所有文件 (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                self._show_message(f"文本已成功导出到: {Path(file_path).name}", duration_ms=3000, is_error=False)
            except Exception as e:
                self._show_message(f"导出失败: {str(e)}", duration_ms=3000, is_error=True)
    
    def _polish_text_with_context_async(self, context_lines: list[str], target_line: str, line_number: int) -> str:
        """使用上下文异步润色文本（不阻塞界面）"""
        # 获取当前选中的风格组合提示词
        selected_styles = self._style_manager.get_selected_styles()
        style_prompt = self._style_manager.get_combined_prompt(selected_styles) if selected_styles else None
        
        # 使用worker方式处理（异步，不阻塞界面）
        group_id = next(self._group_sequence)
        self._pending_group_id = group_id
        
        # 不设置polish_state，保持界面可编辑
        # self._set_polish_state(True)  # 注释掉这行，避免锁定编辑器
        
        worker = PolishWorker(self._api_client, context_lines, target_line, style_prompt)
        worker.signals.finished.connect(
            lambda polished: self._on_context_polish_finished(polished, target_line, line_number)
        )
        worker.signals.error.connect(
            lambda error_message: self._on_context_polish_error(error_message)
        )
        self._thread_pool.start(worker)
        
        return f"request_{group_id}"
    
    def _on_context_polish_finished(self, polished_text: str, original_text: str, line_number: int) -> None:
        """上下文润色完成回调"""
        # 在润色结果面板显示结果
        self.polish_result_panel.add_result(original_text, polished_text, line_number)
        
        # 不设置polish_state，保持界面可编辑
        # self._set_polish_state(False)
        self._pending_group_id = None
        
        # 简短提示，不干扰用户
        self._show_message("润色完成，按TAB键覆盖，按~键拒绝", duration_ms=2000, is_error=False)
    
    def _on_context_polish_error(self, error_message: str) -> None:
        """上下文润色失败回调"""
        self._set_polish_state(False)
        self._pending_group_id = None
        self._show_message(f"润色失败：{error_message}", duration_ms=3600, is_error=True)
    def _on_text_polish_requested(self, text: str) -> None:
        """处理文本润色请求（已废弃，改用_on_editor_enter）"""
        # 此方法已废弃，Enter键现在直接触发_on_editor_enter
        pass
    
    def _on_async_polish_started(self, request_id: str) -> None:
        """异步润色开始"""
        # 不显示阻塞界面，保持用户输入流畅性
        pass
    
    def _on_async_polish_progress(self, request_id: str, progress_message: str) -> None:
        """异步润色进度更新"""
        # 可以在状态栏显示进度，但不阻塞UI
        pass
    
    def _on_async_polish_completed(self, request_id: str, result: str) -> None:
        """异步润色完成"""
        # 获取原始文本（从请求中获取）
        request = self._async_polish_processor.requests.get(request_id)
        original_text = request.text if request else ""
        
        # 在润色结果面板显示结果
        self.polish_result_panel.add_result(original_text, result)
        
        # 使用动画管理器实现平滑显示效果
        self.animation_manager.fade_in(self.polish_result_panel, duration=300)
        
        self._show_message("润色完成，可在下方面板查看结果", duration_ms=2000, is_error=False)
    
    def _on_async_polish_failed(self, request_id: str, error_message: str) -> None:
        """异步润色失败"""
        self._show_message(f"润色失败: {error_message}", duration_ms=3000, is_error=True)
    
    def _on_connection_status_changed(self, is_connected: bool) -> None:
        """连接状态变化"""
        if is_connected:
            self._show_message("API连接已恢复", duration_ms=2000, is_error=False)
        else:
            self._show_message("API连接已断开", duration_ms=3000, is_error=True)
    
    def _on_heartbeat_failed(self, error_message: str) -> None:
        """心跳失败"""
        # 可以在状态栏显示连接问题，但不阻塞用户操作
        pass
    
    def _on_input_stopped_for_prediction(self) -> None:
        """输入停止3秒后的处理 - 触发剧情预测
        
        触发条件：
        1. 用户停止输入达到3秒
        2. 存在润色行（历史或当前）
        """
        # 检查是否存在润色行（检查润色结果面板是否有历史数据）
        has_polish_results = self.polish_result_panel.get_result_count() > 0
        
        # 检查是否有输出列表中的历史润色记录
        has_output_history = self.output_list.count() > 0
        
        # 如果不存在润色行，不触发预测
        if not (has_polish_results or has_output_history):
            return
        
        # 获取当前编辑器中的全部文本
        full_text = self.editor.toPlainText().strip()
        
        # 如果文本为空，不触发预测
        if not full_text:
            return
        
        # 异步调用剧情预测
        self._predict_plot_continuation_async(full_text)
    
    def _predict_plot_continuation_async(self, full_text: str) -> None:
        """异步预测剧情续写（不阻塞界面）
        
        Args:
            full_text: 当前编辑器中的全部文本内容
        """
        # 使用后台线程处理，不阻塞界面
        worker = PlotPredictionWorker(self._api_client, full_text)
        worker.signals.finished.connect(self._on_plot_prediction_finished)
        worker.signals.error.connect(self._on_plot_prediction_error)
        self._thread_pool.start(worker)
        
        # 显示简短提示，不干扰用户
        self._show_message("正在预测剧情...", duration_ms=1500, is_error=False)
    
    def _on_plot_prediction_finished(self, predicted_text: str) -> None:
        """剧情预测完成回调
        
        Args:
            predicted_text: 预测的两行剧情内容
        """
        # 解析预测的两行内容
        lines = predicted_text.strip().split('\n')
        
        # 确保至少有一行
        if not lines or not lines[0].strip():
            self._show_message("预测结果为空，跳过", duration_ms=1500, is_error=True)
            return
        
        # 取前两行（如果有）
        first_line = lines[0].strip() if len(lines) > 0 else ""
        second_line = lines[1].strip() if len(lines) > 1 else ""
        
        # 获取当前文本的行数
        current_block_count = self.editor.document().blockCount()
        
        # 计算预测内容应该插入的行号（末尾+1和末尾+2）
        first_line_number = current_block_count  # 末尾行号+1（从0开始）
        second_line_number = current_block_count + 1  # 末尾行号+2
        
        # 在润色结果面板中显示预测结果，标记为预测类型
        if first_line:
            self.polish_result_panel.add_result(
                original_text="",  # 预测内容没有原文
                polished_text=first_line,
                line_number=first_line_number,
                is_prediction=True
            )
        
        if second_line:
            self.polish_result_panel.add_result(
                original_text="",  # 预测内容没有原文
                polished_text=second_line,
                line_number=second_line_number,
                is_prediction=True
            )
        
        # 显示结果消息
        prediction_count = 2 if second_line else 1
        self._show_message(f"剧情预测完成，生成{prediction_count}行内容，按TAB键确认插入", duration_ms=3000, is_error=False)
    
    def _on_plot_prediction_error(self, error_message: str) -> None:
        """剧情预测失败回调
        
        Args:
            error_message: 错误消息
        """
        self._show_message(f"剧情预测失败：{error_message}", duration_ms=3000, is_error=True)
    
    def _on_overwrite_requested(self) -> None:
        """处理一键覆盖请求（TAB键） - 批量替换所有润色结果。
        对于预测类型的内容，执行插入操作；
        对于普通润色类型，执行替换操作。
        """
        # 获取所有润色结果
        all_results = self.polish_result_panel.get_all_results()
        if not all_results:
            self._show_message("没有可覆盖的润色结果", duration_ms=1500, is_error=True)
            return
        
        # 按行号从大到小排序，从后往前替换，避免行号偏移
        sorted_results = sorted(all_results, key=lambda x: x.line_number, reverse=True)
        
        total_blocks = self.editor.document().blockCount()
        replaced_count = 0
        inserted_count = 0
        skipped_count = 0
        
        # 从后往前处理每个结果
        for result in sorted_results:
            line_number = result.line_number
            result_text = result.current_text
            
            # 验证行号有效性
            if line_number < 0:
                skipped_count += 1
                continue
            
            # 处理预测类型：插入新行
            if result.is_prediction:
                # 如果行号大于等于总行数，说明是追加在末尾
                if line_number >= total_blocks:
                    # 在末尾追加
                    cursor = self.editor.textCursor()
                    cursor.movePosition(QtGui.QTextCursor.End)
                    # 检查当前光标位置是否在行首，避免重复换行
                    current_text = self.editor.toPlainText()
                    if current_text and not current_text.endswith('\n'):
                        cursor.insertText("\n")
                    cursor.insertText(result_text)
                    inserted_count += 1
                else:
                    # 在指定行号插入
                    cursor = self.editor.textCursor()
                    block = self.editor.document().findBlockByNumber(line_number)
                    if block.isValid():
                        cursor.setPosition(block.position())
                        cursor.insertText(result_text + "\n")
                        inserted_count += 1
                    else:
                        skipped_count += 1
            else:
                # 处理普通润色类型：替换现有行
                # 检查行号是否超出范围
                if line_number >= total_blocks:
                    skipped_count += 1
                    continue
                
                # 替换指定行的文本
                cursor = self.editor.textCursor()
                block = self.editor.document().findBlockByNumber(line_number)
                if block.isValid():
                    cursor.setPosition(block.position())
                    cursor.movePosition(QtGui.QTextCursor.StartOfBlock)
                    cursor.movePosition(QtGui.QTextCursor.EndOfBlock, QtGui.QTextCursor.KeepAnchor)
                    cursor.insertText(result_text)
                    replaced_count += 1
                else:
                    skipped_count += 1
        
        # 清空所有结果并隐藏面板
        self.polish_result_panel.hide_result()
        
        # 显示结果消息
        if replaced_count > 0 or inserted_count > 0:
            message_parts = []
            if replaced_count > 0:
                message_parts.append(f"已替换 {replaced_count} 行")
            if inserted_count > 0:
                message_parts.append(f"已插入 {inserted_count} 行")
            if skipped_count > 0:
                message_parts.append(f"跳过 {skipped_count} 行")
            self._show_message(", ".join(message_parts), duration_ms=2000, is_error=False)
        else:
            self._show_message("没有有效的润色结果可以处理", duration_ms=1500, is_error=True)
    
    def _on_reject_requested(self) -> None:
        """处理一键拒绝请求（~键） - 批量拒绝所有润色结果"""
        # 获取结果数量
        result_count = self.polish_result_panel.get_result_count()
        if result_count == 0:
            self._show_message("没有可拒绝的润色结果", duration_ms=1500, is_error=True)
            return
        
        # 清空所有结果并隐藏面板
        self.polish_result_panel.hide_result()
        
        # 显示结果消息
        self._show_message(f"已批量拒绝 {result_count} 个润色结果", duration_ms=1500, is_error=False)

    def _start_polish(self, context_lines: list[str], target_line: str) -> None:
        group_id = next(self._group_sequence)
        self._pending_group_id = group_id
        self._add_output_entry(text=target_line, is_original=True, group_id=group_id)
        self._set_polish_state(True)
        self._show_message("正在润色最后一行…", duration_ms=0, is_error=False)

        # 获取当前选中的风格组合提示词
        selected_styles = self._style_manager.get_selected_styles()
        style_prompt = self._style_manager.get_combined_prompt(selected_styles) if selected_styles else None

        worker = PolishWorker(self._api_client, context_lines, target_line, style_prompt)
        worker.signals.finished.connect(
            lambda polished, gid=group_id: self._on_polish_finished(gid, polished)
        )
        worker.signals.error.connect(
            lambda error_message, gid=group_id: self._on_polish_error(gid, error_message)
        )
        self._thread_pool.start(worker)

    def _on_polish_finished(self, group_id: int, polished_text: str) -> None:
        self._add_output_entry(text=polished_text, is_original=False, group_id=group_id)
        self._set_polish_state(False)
        self._pending_group_id = None
        self._show_message("润色完成，按 Tab 接受，按 ~ 快速拒绝。", duration_ms=3200, is_error=False)

    def _on_polish_error(self, group_id: int, error_message: str) -> None:
        self._set_polish_state(False)
        self._pending_group_id = None
        self._show_message(error_message, duration_ms=3600, is_error=True)
        if not self._group_has_entries(group_id):
            self._show_message("润色失败，保留原文供继续编辑。", duration_ms=3200, is_error=False)

    def _add_output_entry(self, text: str, is_original: bool, group_id: int) -> None:
        theme = dict(self._current_theme)
        item_reference: Dict[str, QtWidgets.QListWidgetItem] = {}

        if is_original:
            for row_index in range(self.output_list.count()):
                list_item = self.output_list.item(row_index)
                item_data = list_item.data(OUTPUT_ITEM_ROLE) or {}
                if item_data.get("group") == group_id and item_data.get("is_original"):
                    widget = self.output_list.itemWidget(list_item)
                    if widget is not None and hasattr(widget, "update_text"):
                        widget.update_text(text)
                    list_item.setData(
                        OUTPUT_ITEM_ROLE,
                        {"group": group_id, "is_original": True, "text": text},
                    )
                    return

        def handle_accept() -> None:
            self._apply_editor_text(text)
            self._remove_group(group_id)
            self._show_message("已应用选中的文本。按 Tab 可快速接受下一条候选。", duration_ms=3000, is_error=False)

        def handle_reject() -> None:
            item = item_reference.get("item")
            if item is None:
                return
            self.output_list.remove_item(item)
            if not self._group_has_entries(group_id):
                self._show_message("已移除该润色候选。", duration_ms=2000, is_error=False)

        def handle_reuse(reuse_text: str) -> None:
            self._show_message("已提交再次润色请求，按 Tab 可快捷接受。", duration_ms=2600, is_error=False)
            current = self.editor.toPlainText().rstrip()
            lines = current.splitlines()
            tail = lines[-5:] if len(lines) > 5 else lines
            context_lines = tail[:-1] if len(tail) >= 2 else []
            # 使用该项文本作为目标行进行再次润色
            self._start_polish(context_lines, reuse_text)

        item = self.output_list.add_entry(
            text=text,
            is_original=is_original,
            theme=theme,
            on_accept=handle_accept,
            on_reject=handle_reject,
            on_reuse=handle_reuse,
        )
        item_reference["item"] = item
        item.setData(OUTPUT_ITEM_ROLE, {"group": group_id, "is_original": is_original, "text": text})
        self.output_list.setCurrentItem(item)

    def _remove_group(self, group_id: int) -> None:
        items_to_remove: list[QtWidgets.QListWidgetItem] = []
        for row_index in range(self.output_list.count()):
            list_item = self.output_list.item(row_index)
            item_data = list_item.data(OUTPUT_ITEM_ROLE) or {}
            if item_data.get("group") == group_id:
                items_to_remove.append(list_item)
        for list_item in items_to_remove:
            self.output_list.remove_item(list_item)

    def _group_has_entries(self, group_id: int) -> bool:
        for row_index in range(self.output_list.count()):
            list_item = self.output_list.item(row_index)
            item_data = list_item.data(OUTPUT_ITEM_ROLE) or {}
            if item_data.get("group") == group_id:
                return True
        return False

    def _set_polish_state(self, in_progress: bool) -> None:
        self._polish_in_progress = in_progress
        self.editor.setReadOnly(in_progress)
        if self._theme_selector is not None:
            self._theme_selector.setEnabled(not in_progress)
        if getattr(self, "_export_button", None) is not None:
            self._export_button.setEnabled(not in_progress)
        if getattr(self, "_quick_reject_button", None) is not None:
            self._quick_reject_button.setEnabled(not in_progress)
        if self._overlay is not None and self._central_container is not None:
            overlay_theme = dict(self._current_theme)
            self._overlay.set_theme(overlay_theme)
            self._overlay.resize(self._central_container.size())
            if in_progress:
                self._overlay.start()
            else:
                self._overlay.stop()

    def _apply_editor_text(self, last_line_text: str) -> None:
        current = self.editor.toPlainText()
        lines = current.splitlines()
        if lines:
            lines[-1] = last_line_text
            new_text = "\n".join(lines)
        else:
            new_text = last_line_text
        self.editor.blockSignals(True)
        self.editor.setPlainText(new_text)
        cursor = self.editor.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.editor.setTextCursor(cursor)
        self.editor.blockSignals(False)

    def _on_output_selection_changed(self) -> None:
        self.editor.setFocus(QtCore.Qt.OtherFocusReason)

    def _on_theme_selector_changed(self) -> None:
        if self._theme_selector is None:
            return
        theme_key = self._theme_selector.currentData()
        if not theme_key or theme_key == self._theme_manager.getCurrentThemeKey():
            return
        try:
            self._theme_manager.saveTheme(theme_key)
        except ValueError as exception:
            self._show_message(str(exception), duration_ms=2600, is_error=True)

    def _apply_theme(self, theme: Dict[str, str]) -> None:
        self._current_theme = dict(theme)
        window_palette = self.palette()
        window_palette.setColor(QtGui.QPalette.Window, QtGui.QColor(theme["background"]))
        window_palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(theme["foreground"]))
        self.setPalette(window_palette)

        if self._overlay is not None:
            self._overlay.set_theme(self._current_theme)

        if self._central_container is not None:
            self._central_container.setPalette(window_palette)
            self._central_container.setAutoFillBackground(True)
        if self._header_frame is not None and self._theme_selector is not None:
            header_stylesheet = "\n".join(
                [
                    "QFrame#HeaderFrame {",
                    f"  background-color: {theme['panelBackground']};",
                    f"  border-bottom: 1px solid {theme['borderColor']};",
                    "}",
                    "QLabel#TitleLabel {",
                    "  font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;",
                    "  font-size: 18px;",
                    "  font-weight: 600;",
                    f"  color: {theme['foreground']};",
                    "  letter-spacing: 0.5px;",
                    "}",
                    "QLabel#MessageLabel {",
                    "  font-size: 12px;",
                    f"  color: {theme['mutedForeground']};",
                    "}",
                    "QComboBox#ThemeSelector {",
                    f"  background-color: {theme['buttonBackground']};",
                    f"  color: {theme['buttonForeground']};",
                    f"  border: 1px solid {theme['borderColor']};",
                    "  border-radius: 4px;",
                    "  padding: 6px 10px;",
                    "  font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;",
                    "}",
                    "QComboBox#ThemeSelector::drop-down {",
                    "  width: 18px;",
                    "  border: none;",
                    "}",
                    "QPushButton#ExportButton {",
                    f"  background-color: {theme['buttonBackground']};",
                    f"  color: {theme['buttonForeground']};",
                    f"  border: 1px solid {theme['borderColor']};",
                    "  border-radius: 4px;",
                    "  padding: 6px 14px;",
                    "}",
                    "QPushButton#ExportButton:hover {",
                    f"  background-color: {theme['accent']};",
                    "  color: #ffffff;",
                    "}",
                    "QPushButton#QuickRejectButton {",
                    f"  background-color: {theme.get('buttonBackground', '#3a3d41')};",
                    f"  color: {theme.get('buttonForeground', '#f3f3f3')};",
                    f"  border: 1px solid {theme['borderColor']};",
                    "  border-radius: 4px;",
                    "  padding: 6px 14px;",
                    "}",
                    "QPushButton#QuickRejectButton:hover {",
                    "  background-color: #d13438;",
                    "  color: #ffffff;",
                    "}",
                    "QSplitter#EditorOutputSplitter::handle {",
                    f"  background: {theme['borderColor']};",
                    "}",
                    "QSplitter#EditorOutputSplitter::handle:hover {",
                    f"  background: {theme['accent']};",
                    "}",
                ]
            )
            self._header_frame.setStyleSheet(header_stylesheet)

            # 编辑器统一样式（边框、圆角、选区色、滚动条）
            editor_stylesheet = "\n".join(
                [
                    "QPlainTextEdit#VsCodeEditor {",
                    f"  background-color: {theme['editorBackground']};",
                    f"  color: {theme['editorForeground']};",
                    f"  border: 1px solid {theme['borderColor']};",
                    "  border-radius: 6px;",
                    f"  selection-background-color: {theme['selection']};",
                    "  selection-color: #ffffff;",
                    "}",
                    "QPlainTextEdit#VsCodeEditor QScrollBar:vertical {",
                    "  width: 8px;",
                    f"  background: {theme['panelBackground']};",
                    "  margin: 0;",
                    "  border-radius: 4px;",
                    "}",
                    "QPlainTextEdit#VsCodeEditor QScrollBar::handle:vertical {",
                    f"  background: {theme['accent']};",
                    "  border-radius: 4px;",
                    "}",
                    "QPlainTextEdit#VsCodeEditor QScrollBar::add-line:vertical,",
                    "QPlainTextEdit#VsCodeEditor QScrollBar::sub-line:vertical {",
                    "  height: 0px;",
                    "  border: none;",
                    "}",
                ]
            )
            self.editor.setStyleSheet(editor_stylesheet)

            # 同步主题选择器索引，不触发变更信号
            current_key = theme.get("key")
            if self._theme_selector is not None and current_key:
                idx = self._theme_selector.findData(current_key)
                if idx != -1:
                    self._theme_selector.blockSignals(True)
                    self._theme_selector.setCurrentIndex(idx)
                    self._theme_selector.blockSignals(False)
        # 同步子控件主题
        self.editor.update_theme(self._current_theme)
        self.output_list.update_theme(self._current_theme)
        
        # 更新润色结果面板主题
        if hasattr(self, 'polish_result_panel'):
            self.polish_result_panel.update_theme(self._current_theme)

    def _show_message(self, message: str, duration_ms: int, is_error: bool) -> None:
        if self._message_label is None:
            return
        color = "#f14c4c" if is_error else self._current_theme.get("mutedForeground", "#9c9c9c")
        self._message_label.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._message_label.setText(message)
        self._message_timer.stop()
        if duration_ms > 0:
            self._message_timer.start(duration_ms)

    def _clear_status_message(self) -> None:
        if self._message_label is None:
            return
        self._message_label.clear()


def main() -> None:
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    load_dotenv()
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("VSCode风格小说润色器")
    app.setOrganizationName("NovelPolisherStudio")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
