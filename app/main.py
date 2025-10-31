from __future__ import annotations

import itertools
import sys
from pathlib import Path
from typing import Dict, Optional
from functools import partial

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QFileDialog
from dotenv import load_dotenv

import sys
import os

# 添加项目根目录到 Python 路径
if __name__ == '__main__':
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from app.api_client import AIClient, AIError
from app.widgets.loading_overlay import LoadingOverlay
from app.widgets.design_system import Elevation
from app.widgets.output_list import OutputListWidget
from app.widgets.theme_manager import ThemeManager
from app.widgets.settings_dialog import SettingsDialog
from app.widgets.file_explorer import FileExplorerWidget
from app.widgets.knowledge_base_dialog import KnowledgeBaseProgressDialog
from app.widgets.polish_result_panel import PolishResultPanel
from app.widgets.prediction_toggle import PredictionToggle
from app.config_manager import ConfigManager
from app.style_manager import StyleManager
from app.text_processor import TextProcessor
from app.knowledge_base import KnowledgeBaseManager
from app.auto_export_manager import AutoExportManager
from app.document_handler import DocumentHandler
from app.auto_save_manager import AutoSaveManager
from app.widgets.batch_polish_dialog import BatchPolishDialog
from app.processors.async_polish_processor import AsyncPolishProcessor, HeartbeatManager
from app.request_queue_manager import RequestQueueManager, RequestType, RequestPriority
from app.config_manager import PolishStyle

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
    enterPressed = QtCore.Signal()
    tabPressed = QtCore.Signal()
    quickRejectPressed = QtCore.Signal()
    textPolishRequested = QtCore.Signal(str)  # 新增：请求润色信号
    inputStoppedForPrediction = QtCore.Signal()  # 新增：输入停止3秒信号，用于触发剧情预测

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._current_theme: Dict[str, str] | None = None
        self._line_number_area = LineNumberArea(self)
        
        # 导入UI增强模块
        from app.widgets.ui_enhancer import UnderlineRenderer
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
        try:
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
        finally:
            painter.end()

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
        if event.key() in (QtCore.Qt.Key_QuoteLeft, QtCore.Qt.Key_AsciiTilde) and event.modifiers() in (QtCore.Qt.NoModifier, QtCore.Qt.ShiftModifier):
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
    """Worker 信号类 - 用于线程间通信"""
    finished = QtCore.Signal(str)
    error = QtCore.Signal(str)
    
    def __init__(self):
        super().__init__()
        print(f"[DEBUG] WorkerSignals 初始化完成", flush=True)


class PolishWorker(QtCore.QRunnable):
    def __init__(self, client: AIClient, context_lines: list[str], target_line: str, style_prompt: Optional[str] = None) -> None:
        super().__init__()
        self._client = client
        self._context_lines = context_lines
        self._target_line = target_line
        self._style_prompt = style_prompt
        self.signals = WorkerSignals()
        print(f"[DEBUG] PolishWorker.__init__() 完成，target_line={target_line[:20]}", flush=True)

    def run(self) -> None:
        import sys
        import traceback
        
        print(f"[DEBUG] PolishWorker.run() 开始执行", flush=True)
        sys.stdout.flush()
        
        polished_text = None  # 初始化变量
        
        try:
            print(f"[DEBUG] 调用 API polish_last_line，参数: context行数={len(self._context_lines)}, target={self._target_line[:30]}...", flush=True)
            sys.stdout.flush()
            
            print(f"[DEBUG] 准备接收 API 返回值...", flush=True)
            sys.stdout.flush()
            
            polished_text = self._client.polish_last_line(self._context_lines, self._target_line, self._style_prompt)
            
            print(f"[DEBUG] ===== API 返回值已接收 =====", flush=True)
            print(f"[DEBUG] polish_last_line 返回成功，type={type(polished_text)}, len={len(polished_text) if polished_text else 0}", flush=True)
            print(f"[DEBUG] polished_text repr: {repr(polished_text[:100])}", flush=True)
            sys.stdout.flush()
            
            if polished_text:
                print(f"[DEBUG] API 返回结果: {polished_text[:50] if len(polished_text) > 50 else polished_text}...", flush=True)
            else:
                print(f"[DEBUG] API 返回结果为空！", flush=True)
            sys.stdout.flush()
            
        except AIError as exception:
            print(f"[DEBUG] 捕获 AIError: {exception}", flush=True)
            sys.stdout.flush()
            try:
                self.signals.error.emit(str(exception))
            except Exception as e2:
                print(f"[ERROR] 发送error信号失败: {e2}", flush=True)
                traceback.print_exc()
                sys.stdout.flush()
            return  # 发生错误后直接返回
        except Exception as exception:  # noqa: BLE001
            print(f"[DEBUG] 捕获 Exception: {type(exception).__name__}: {exception}", flush=True)
            traceback.print_exc()
            sys.stdout.flush()
            try:
                self.signals.error.emit(f"未知错误：{exception}")
            except Exception as e2:
                print(f"[ERROR] 发送error信号失败: {e2}", flush=True)
                traceback.print_exc()
                sys.stdout.flush()
            return  # 发生错误后直接返回
        
        print(f"[DEBUG] try块执行完毕，polished_text={'有值' if polished_text else '为空'}", flush=True)
        sys.stdout.flush()
        
        # 只有成功获取到润色文本时才发送 finished 信号
        if polished_text:
            print(f"[DEBUG] 准备发送 finished 信号，polished_text={polished_text[:30] if len(polished_text) > 30 else polished_text}", flush=True)
            sys.stdout.flush()
            
            try:
                print(f"[DEBUG] 调用 signals.finished.emit()...", flush=True)
                sys.stdout.flush()
                
                self.signals.finished.emit(polished_text)
                
                print(f"[DEBUG] finished 信号已发送", flush=True)
                sys.stdout.flush()
            except Exception as e:
                print(f"[ERROR] 发送 finished 信号时出错: {type(e).__name__}: {e}", flush=True)
                traceback.print_exc()
                sys.stdout.flush()
        else:
            print(f"[ERROR] polished_text 为空，不发送信号", flush=True)
            sys.stdout.flush()
            try:
                self.signals.error.emit("润色结果为空")
            except Exception as e:
                print(f"[ERROR] 发送error信号失败: {e}", flush=True)
                traceback.print_exc()
                sys.stdout.flush()
        
        print(f"[DEBUG] PolishWorker.run() 执行完毕", flush=True)
        sys.stdout.flush()


class PlotPredictionWorker(QtCore.QRunnable):
    """剧情预测工作线程"""
    def __init__(self, client: AIClient, full_text: str, style_prompt: Optional[str] = None) -> None:
        super().__init__()
        self._client = client
        self._full_text = full_text
        self._style_prompt = style_prompt
        self.signals = WorkerSignals()
    
    def run(self) -> None:
        try:
            predicted_text = self._client.predict_plot_continuation(self._full_text, self._style_prompt or "")
        except AIError as exception:
            self.signals.error.emit(str(exception))
        except Exception as exception:  # noqa: BLE001
            self.signals.error.emit(f"未知错误：{exception}")
        else:
            self.signals.finished.emit(predicted_text)


class BatchPolishWorker(QtCore.QThread):
    """批量润色工作线程"""
    
    finished = QtCore.Signal(str)  # 润色完成，发送润色后的内容
    error = QtCore.Signal(str)  # 发生错误
    
    def __init__(self, client: AIClient, content: str, requirement: str):
        super().__init__()
        self.client = client
        self.content = content
        self.requirement = requirement
    
    def run(self):
        """执行批量润色"""
        try:
            print(f"[DEBUG] BatchPolishWorker 开始执行", flush=True)
            polished = self.client.batch_polish_document(self.content, self.requirement)
            print(f"[DEBUG] BatchPolishWorker 完成，返回长度: {len(polished)}", flush=True)
            self.finished.emit(polished)
        except AIError as e:
            print(f"[ERROR] BatchPolishWorker AI错误: {e}", flush=True)
            self.error.emit(f"AI服务错误：{str(e)}")
        except Exception as e:
            print(f"[ERROR] BatchPolishWorker 异常: {e}", flush=True)
            import traceback
            traceback.print_exc()
            self.error.emit(f"未知错误：{str(e)}")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("字见润新")
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
        # 注意：已在文件顶部导入，不需要在此处再次导入
        self._async_polish_processor = AsyncPolishProcessor(self._api_client, self)
        self._heartbeat_manager = HeartbeatManager(self._api_client, 30, self)
        
        # 初始化请求队列管理器（避免润色和预测冲突）
        # 注意：已在文件顶部导入，不需要在此处再次导入
        self._request_queue_manager = RequestQueueManager(max_concurrent=1, parent=self)
        
        # 连接队列管理器的信号（用于监控队列状态）
        self._request_queue_manager.request_started.connect(self._on_request_started)
        self._request_queue_manager.request_completed.connect(self._on_request_completed)
        self._request_queue_manager.request_failed.connect(self._on_request_failed)
        
        # 初始化知识库管理器
        self._kb_manager = KnowledgeBaseManager()
        
        # 当前激活的知识库（用于剧情预测）
        self._active_kb = None
        self._active_kb_id = None
        
        # 重排序客户端（用于知识库增强预测）
        self._rerank_client = None
        
        # 初始化实时导出管理器
        self._auto_export_manager = AutoExportManager(debounce_ms=2000, parent=self)
        
        # 初始化自动保存管理器（每30秒保存一次）
        self._auto_save_manager = AutoSaveManager(interval_seconds=30, parent=self)
        self._current_file_path: Optional[str] = None  # 当前打开的文件路径
        
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
        
        # 初始化文件资源管理器
        self.file_explorer = FileExplorerWidget(self)
        self.file_explorer.setMinimumWidth(200)
        self.file_explorer.setMaximumWidth(400)
        
        # 初始化润色结果面板
        # 注意：已在文件顶部导入，不需要在此处再次导入
        self.polish_result_panel = PolishResultPanel(self)
        # 润色结果面板投影，突出层级
        try:
            Elevation.apply_shadow(self.polish_result_panel, blur_radius=20, offset_x=0, offset_y=2, color=QtGui.QColor(0, 0, 0, 72))
        except Exception:
            pass
        
        # 初始化动画管理器
        from app.widgets.ui_enhancer import AnimationManager
        self.animation_manager = AnimationManager(self)

        self._build_ui()
        self._connect_signals()

        self._theme_manager.themeChanged.connect(self._apply_theme)
        self._theme_manager.emitCurrentTheme()
        
        # 自动加载上次打开的文件夹
        self._load_last_opened_folder()
        
        # 加载剧情预测开关状态
        self._load_prediction_config()
        
        # 【性能优化】程序启动后立即预热API连接，确保最快响应
        self._warmup_api_connection()
    
    def on_editor_line_count_changed(self, changed_line: int, delta: int) -> None:
        """处理编辑器行数变化 - 调整润色结果面板中的行号
        
        Args:
            changed_line: 发生变化的行号
            delta: 行数变化量（正数表示插入，负数表示删除）
        """
        if hasattr(self, 'polish_result_panel'):
            self.polish_result_panel.adjust_line_numbers(changed_line, delta)
    
    def _load_last_opened_folder(self) -> None:
        """加载上次打开的文件夹"""
        workspace_config = self._config_manager.get_workspace_config()
        last_folder = workspace_config.last_opened_folder
        
        # 检查文件夹是否存在
        if last_folder and os.path.isdir(last_folder):
            try:
                self.file_explorer.load_folder(last_folder)
                print(f"[INFO] 已自动加载上次打开的文件夹: {last_folder}")
            except Exception as e:
                print(f"[WARN] 加载上次打开的文件夹失败: {e}")
    
    def _load_prediction_config(self) -> None:
        """加载剧情预测开关状态"""
        workspace_config = self._config_manager.get_workspace_config()
        prediction_enabled = workspace_config.prediction_enabled
        self.prediction_toggle.set_enabled(prediction_enabled)
        print(f"[INFO] 剧情预测功能: {'已启用' if prediction_enabled else '已关闭'}")
    
    def _on_prediction_toggle_changed(self, enabled: bool) -> None:
        """处理剧情预测开关状态变化"""
        # 保存到配置
        workspace_config = self._config_manager.get_workspace_config()
        workspace_config.prediction_enabled = enabled
        self._config_manager.update_workspace_config(workspace_config)
        
        # 更新状态
        status = "已启用" if enabled else "已关闭"
        self._show_message(f"剧情预测功能{status}", duration_ms=2000, is_error=False)
        print(f"[INFO] 剧情预测功能{status}")
    
    def _warmup_api_connection(self) -> None:
        """预热API连接 - 在后台线程中执行，不阻塞UI启动"""
        import sys
        print(f"[INFO] 启动API预热任务...", file=sys.stderr, flush=True)
        
        # 使用QTimer延迟100ms执行，确保主窗口已完全显示
        QtCore.QTimer.singleShot(100, self._execute_warmup)
    
    def _execute_warmup(self) -> None:
        """执行API预热 - 在后台线程中运行"""
        import sys
        from PySide6.QtCore import QThread
        
        class WarmupWorker(QThread):
            """预热工作线程"""
            warmup_completed = QtCore.Signal(dict)  # 预热完成信号
            
            def __init__(self, api_client, parent=None):
                super().__init__(parent)
                self.api_client = api_client
            
            def run(self):
                """执行预热任务"""
                try:
                    print(f"[INFO] 预热工作线程开始执行...", file=sys.stderr, flush=True)
                    result = self.api_client.warmup_connection()
                    self.warmup_completed.emit(result)
                except Exception as e:
                    print(f"[ERROR] 预热失败: {e}", file=sys.stderr, flush=True)
                    import traceback
                    traceback.print_exc()
                    self.warmup_completed.emit({
                        "success": False,
                        "message": f"预热异常: {str(e)}",
                        "warmup_time": 0.0
                    })
        
        # 创建并启动预热工作线程
        self._warmup_worker = WarmupWorker(self._api_client, self)
        self._warmup_worker.warmup_completed.connect(self._on_warmup_completed)
        self._warmup_worker.start()
        
        # 触发心跳管理器的首次检查（轻量级，不发送请求）
        if hasattr(self, '_heartbeat_manager') and self._heartbeat_manager:
            # 延迟500ms后执行首次心跳
            QtCore.QTimer.singleShot(500, self._heartbeat_manager.force_reconnect)
            print(f"[INFO] 心跳管理器已启动", file=sys.stderr, flush=True)
    
    def _on_warmup_completed(self, result: dict) -> None:
        """预热完成回调"""
        import sys
        if result.get("success"):
            warmup_time = result.get("warmup_time", 0.0)
            print(f"[INFO] API连接池已就绪（{warmup_time*1000:.1f}ms）", file=sys.stderr, flush=True)
            # 不显示消息，避免干扰用户
        else:
            error_msg = result.get("message", "未知错误")
            print(f"[WARNING] 预热失败: {error_msg}", file=sys.stderr, flush=True)

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
        # 细腻的顶部阴影，提升层次感
        try:
            Elevation.apply_shadow(header_frame, blur_radius=18, offset_x=0, offset_y=2, color=QtGui.QColor(0, 0, 0, 64))
        except Exception:
            pass
        title_label = QtWidgets.QLabel("字见润新")
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
        
        # 导入文件夹按钮
        import_folder_button = QtWidgets.QPushButton("导入文件夹")
        import_folder_button.setObjectName("ImportFolderButton")
        import_folder_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        import_folder_button.clicked.connect(self._on_import_folder)
        
        # 新建知识库按钮
        create_kb_button = QtWidgets.QPushButton("新建知识库")
        create_kb_button.setObjectName("CreateKBButton")
        create_kb_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        create_kb_button.clicked.connect(self._on_create_knowledge_base)
        
        # 知识库选择按钮
        select_kb_button = QtWidgets.QPushButton("选择知识库")
        select_kb_button.setObjectName("SelectKBButton")
        select_kb_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        select_kb_button.clicked.connect(self._on_select_knowledge_base)
        
        # 当前知识库状态标签
        kb_status_label = QtWidgets.QLabel("知识库: 未激活")
        kb_status_label.setObjectName("KBStatusLabel")
        
        # 一键润色按钮
        batch_polish_button = QtWidgets.QPushButton("✨ 一键润色")
        batch_polish_button.setObjectName("BatchPolishButton")
        batch_polish_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        batch_polish_button.clicked.connect(self._on_batch_polish_clicked)
        batch_polish_button.setToolTip("对当前文档进行批量润色")

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

        # 选择导出目录按钮
        select_export_dir_button = QtWidgets.QPushButton("选择导出目录")
        select_export_dir_button.setObjectName("SelectExportDirButton")
        select_export_dir_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        
        # 实时导出状态标签
        auto_export_status_label = QtWidgets.QLabel("实时导出: 未启用")
        auto_export_status_label.setObjectName("AutoExportStatusLabel")
        
        export_button = QtWidgets.QPushButton("手动导出")
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
        header_layout.addWidget(import_folder_button, 0)
        header_layout.addWidget(create_kb_button, 0)
        header_layout.addWidget(select_kb_button, 0)
        header_layout.addWidget(kb_status_label, 0)
        header_layout.addWidget(batch_polish_button, 0)
        header_layout.addWidget(theme_selector, 0)
        header_layout.addWidget(settings_button, 0)
        header_layout.addWidget(select_export_dir_button, 0)
        header_layout.addWidget(export_button, 0)
        header_layout.addWidget(quick_reject_button, 0)
        header_layout.addWidget(auto_export_status_label, 0)
        header_layout.addStretch(1)
        header_layout.addWidget(message_label, 0)

        # 创建主分割器（水平）- 左侧文件浏览器，中间编辑器，右侧润色结果和输出列表
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_splitter.setObjectName("MainSplitter")
        main_splitter.setHandleWidth(3)
        
        # 左侧：文件资源管理器
        main_splitter.addWidget(self.file_explorer)
        
        # 中间：编辑器
        main_splitter.addWidget(self.editor)
        
        # 右侧：创建垂直分割器包含剧情预测开关、润色结果面板和输出列表
        right_panel = QtWidgets.QWidget()
        right_panel.setObjectName("RightPanel")
        right_panel_layout = QtWidgets.QVBoxLayout(right_panel)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(0)
        
        # 剧情预测开关（放在右侧面板顶部）
        self.prediction_toggle = PredictionToggle()
        right_panel_layout.addWidget(self.prediction_toggle)
        
        # 创建垂直分割器包含润色结果面板和输出列表
        right_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        right_splitter.setObjectName("RightSplitter")
        right_splitter.setHandleWidth(3)
        right_splitter.addWidget(self.polish_result_panel)
        right_splitter.addWidget(self.output_list)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)
        right_splitter.setChildrenCollapsible(False)
        right_splitter.setSizes([300, 300])
        
        # 将分割器添加到右侧面板
        right_panel_layout.addWidget(right_splitter)
        
        # 将右侧面板添加到主分割器
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(0, 1)  # 文件浏览器占1份
        main_splitter.setStretchFactor(1, 2)  # 编辑器占2份
        main_splitter.setStretchFactor(2, 1)  # 右侧面板（含开关）占1份
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setSizes([250, 600, 300])

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
        self._select_export_dir_button = select_export_dir_button
        self._auto_export_status_label = auto_export_status_label
        self._export_button = export_button
        self._quick_reject_button = quick_reject_button
        self._message_label = message_label
        self._overlay = overlay
        self._kb_status_label = kb_status_label

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
        
        # 连接实时导出管理器信号
        self._auto_export_manager.export_started.connect(self._on_auto_export_started)
        self._auto_export_manager.export_completed.connect(self._on_auto_export_completed)
        self._auto_export_manager.export_failed.connect(self._on_auto_export_failed)
        self._auto_export_manager.export_status_changed.connect(self._on_auto_export_status_changed)
        
        # 连接文件浏览器信号
        self.file_explorer.fileOpened.connect(self._on_file_opened)
        self.file_explorer.newFileRequested.connect(self._on_new_file_requested)
        
        # 连接自动保存管理器信号
        self._auto_save_manager.save_completed.connect(self._on_auto_save_completed)
        
        # 连接编辑器文本变化到实时导出
        self.editor.textChanged.connect(self._on_editor_text_changed_for_export)
        
        # 连接剧情预测开关
        self.prediction_toggle.toggled.connect(self._on_prediction_toggle_changed)
        
        if self._theme_selector is not None:
            self._theme_selector.currentIndexChanged.connect(self._on_theme_selector_changed)
        if getattr(self, "_settings_button", None) is not None:
            self._settings_button.clicked.connect(self._on_settings_clicked)
        if getattr(self, "_select_export_dir_button", None) is not None:
            self._select_export_dir_button.clicked.connect(self._on_select_export_dir_clicked)
        if getattr(self, "_export_button", None) is not None:
            self._export_button.clicked.connect(self._on_export_clicked)
        if getattr(self, "_quick_reject_button", None) is not None:
            self._quick_reject_button.clicked.connect(self._on_quick_reject)
        self._message_timer.timeout.connect(self._clear_status_message)
        
        # 加载保存的导出配置
        self._load_export_config()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._overlay is not None and self._central_container is not None:
            self._overlay.resize(self._central_container.size())

    def _on_editor_enter(self) -> None:
        """处理Enter键：获取刚输入完成的行（上一行）并进行异步润色"""
        print(f"[DEBUG] Enter键被按下")
        # 清除所有预测结果（用户已经开始输入新内容）
        self.polish_result_panel.remove_all_predictions()
        
        cursor = self.editor.textCursor()
        current_block = cursor.blockNumber()
        print(f"[DEBUG] 当前行号: {current_block}")
        
        if current_block == 0:
            print(f"[DEBUG] 在第一行，不执行润色")
            return
        
        previous_block = current_block - 1
        previous_block_obj = self.editor.document().findBlockByNumber(previous_block)
        previous_line = previous_block_obj.text().strip()
        print(f"[DEBUG] 上一行内容: {previous_line}")
        
        if not previous_line:
            print(f"[DEBUG] 上一行为空，不执行润色")
            return
        
        full_text = self.editor.toPlainText()
        lines = full_text.splitlines()
        
        start_context = max(0, previous_block - 5)
        context_lines = lines[start_context:previous_block] if previous_block > 0 else []
        
        print(f"[DEBUG] 开始执行润色，上下文行数: {len(context_lines)}")
        request_id = self._polish_text_with_context_async(context_lines, previous_line, previous_block)
        self._current_polish_line = previous_block
        print(f"[DEBUG] 润色请求已发送，请求ID: {request_id}")

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
        
        dialog.exec()

    def _on_config_changed(self) -> None:
        """配置变化回调"""
        # 更新API客户端配置
        self._api_client.update_config(self._config_manager)
        self._show_message("配置已更新", duration_ms=2000, is_error=False)

    def _on_select_export_dir_clicked(self) -> None:
        """选择导出目录"""
        # 获取当前配置的导出目录作为默认路径
        current_export_dir = self._config_manager.get_export_config().export_directory
        default_dir = current_export_dir if current_export_dir and os.path.isdir(current_export_dir) else ""
        
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择实时导出目录",
            default_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder_path:
            # 保存导出目录到配置
            self._config_manager.update_export_config(
                export_directory=folder_path,
                auto_export_enabled=True
            )
            
            # 更新导出管理器
            self._auto_export_manager.set_export_directory(folder_path)
            
            # 立即执行一次导出
            text = self.editor.toPlainText()
            if text.strip():
                self._auto_export_manager.export_now(text)
            
            self._show_message(f"已设置实时导出目录: {Path(folder_path).name}", duration_ms=3000, is_error=False)
    
    def _on_export_clicked(self) -> None:
        """手动导出到用户选择的文件"""
        text = self.editor.toPlainText()
        if not text.strip():
            self._show_message("没有可导出的文本内容。", duration_ms=2000, is_error=True)
            return
        
        # 获取默认文件名和目录
        export_config = self._config_manager.get_export_config()
        default_filename = export_config.export_filename or "字见润新.txt"
        default_dir = export_config.export_directory if export_config.export_directory else ""
        default_path = os.path.join(default_dir, default_filename) if default_dir else default_filename
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "手动导出文本",
            default_path,
            "文本文件 (*.txt);;所有文件 (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                self._show_message(f"文本已成功导出到: {Path(file_path).name}", duration_ms=3000, is_error=False)
            except Exception as e:
                self._show_message(f"导出失败: {str(e)}", duration_ms=3000, is_error=True)
    
    def _load_export_config(self) -> None:
        """加载保存的导出配置"""
        export_config = self._config_manager.get_export_config()
        
        if export_config.export_directory:
            self._auto_export_manager.set_export_directory(export_config.export_directory)
            self._auto_export_manager.set_export_filename(export_config.export_filename)
            
            if export_config.auto_export_enabled:
                self._auto_export_manager.set_enabled(True)
    
    def _on_editor_text_changed_for_export(self) -> None:
        """编辑器文本变化时，请求实时导出"""
        text = self.editor.toPlainText()
        self._auto_export_manager.request_export(text)
    
    def _on_auto_export_started(self, file_path: str) -> None:
        """实时导出开始"""
        # 可以在这里显示导出开始的提示，但为了不干扰用户，暂时不显示
        pass
    
    def _on_auto_export_completed(self, file_path: str) -> None:
        """实时导出完成"""
        # 简短提示，不干扰用户
        filename = Path(file_path).name
        # 可以选择性地显示提示，或者只更新状态标签
        # self._show_message(f"已保存到: {filename}", duration_ms=1000, is_error=False)
    
    def _on_auto_export_failed(self, error_message: str) -> None:
        """实时导出失败"""
        self._show_message(f"实时导出失败: {error_message}", duration_ms=3000, is_error=True)
    
    def _on_auto_export_status_changed(self, enabled: bool) -> None:
        """实时导出状态变化"""
        if self._auto_export_status_label is not None:
            if enabled:
                export_path = self._auto_export_manager.get_export_path()
                if export_path:
                    folder_name = Path(export_path).parent.name
                    self._auto_export_status_label.setText(f"实时导出: {folder_name}")
            else:
                self._auto_export_status_label.setText("实时导出: 未启用")
    
    def _on_import_folder(self) -> None:
        """导入文件夹"""
        # 获取上次打开的文件夹作为默认路径
        workspace_config = self._config_manager.get_workspace_config()
        default_dir = workspace_config.last_opened_folder if workspace_config.last_opened_folder and os.path.isdir(workspace_config.last_opened_folder) else ""
        
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择文件夹",
            default_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if folder_path:
            self.file_explorer.load_folder(folder_path)
            # 保存文件夹路径到配置
            self._config_manager.update_last_opened_folder(folder_path)
            self._show_message(f"已导入文件夹: {Path(folder_path).name}", duration_ms=2000, is_error=False)
    
    def _on_create_knowledge_base(self) -> None:
        """创建知识库"""
        # 获取当前选中的文件夹
        current_folder = self.file_explorer.get_current_folder()
        if not current_folder:
            QtWidgets.QMessageBox.warning(
                self, "错误", 
                "请先导入文件夹并选中要创建知识库的目录。"
            )
            return
        
        # 检查向量化API配置
        api_config = self._config_manager.get_api_config()
        if not api_config.embedding_api_key:
            reply = QtWidgets.QMessageBox.question(
                self, "缺少配置",
                "尚未配置阿里云向量化API密钥，是否前往设置？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                self._on_settings_clicked()
            return
        
        # 显示加载提示
        self._show_message("正在连接API，请稍候...", duration_ms=0, is_error=False)
        QtWidgets.QApplication.processEvents()  # 强制刷新UI
        
        # 测试API连接
        self._kb_manager.set_embedding_client(
            api_config.embedding_api_key,
            api_config.embedding_model
        )
        
        success, message = self._kb_manager.test_embedding_connection()
        
        # 清除加载提示
        self._clear_status_message()
        
        if not success:
            reply = QtWidgets.QMessageBox.question(
                self, "API连接测试失败",
                f"{message}\n\n是否仍要继续创建知识库？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.No:
                return
        
        # 输入知识库名称
        kb_name, ok = QtWidgets.QInputDialog.getText(
            self, "创建知识库",
            "请输入知识库名称:"
        )
        
        if not ok or not kb_name.strip():
            return
        
        # 创建进度对话框
        progress_dialog = KnowledgeBaseProgressDialog(self)
        progress_dialog.set_theme(self._current_theme)
        
        # 向量化客户端已在测试连接时设置
        
        # 在后台线程创建知识库
        from PySide6.QtCore import QThread
        
        class KBCreationWorker(QThread):
            def __init__(self, kb_manager, name, folder, dialog):
                super().__init__()
                self.kb_manager = kb_manager
                self.name = name
                self.folder = folder
                self.dialog = dialog
                self.result = None
            
            def run(self):
                self.result = self.kb_manager.create_knowledge_base(
                    name=self.name,
                    folder_path=self.folder,
                    progress_callback=lambda c, t, m: self.dialog.update_progress(c, t, m),
                    error_callback=lambda e: self.dialog.log(f"错误: {e}")
                )
        
        worker = KBCreationWorker(self._kb_manager, kb_name.strip(), current_folder, progress_dialog)
        worker.finished.connect(lambda: self._on_kb_creation_finished(worker, progress_dialog))
        worker.start()
        
        progress_dialog.exec()
    
    def _on_kb_creation_finished(self, worker, dialog):
        """知识库创建完成"""
        if worker.result:
            dialog.set_completed(success=True)
            
            # 生成知识库的定制化提示词
            kb = worker.result
            self._generate_kb_prompts(kb, dialog)
            
            # 将新创建的知识库设置为活动知识库
            self._activate_knowledge_base(kb)
            
            self._show_message(
                f"知识库创建成功并已激活: {kb.name}，已生成定制化提示词", 
                duration_ms=4000, 
                is_error=False
            )
        else:
            dialog.set_completed(success=False)
            self._show_message("知识库创建失败", duration_ms=3000, is_error=True)
    
    def _generate_kb_prompts(self, kb, progress_dialog=None):
        """为知识库生成定制化提示词
        
        Args:
            kb: 知识库对象
            progress_dialog: 进度对话框（可选）
        """
        try:
            if progress_dialog:
                progress_dialog.log("正在分析文档特征...")
            
            # 导入提示词生成器
            from app.prompt_generator import PromptGenerator
            
            generator = PromptGenerator()
            
            # 提取文档特征
            features = generator.extract_features_from_documents(kb.documents, sample_size=50)
            
            # 输出特征提取结果（调试用）
            if progress_dialog:
                progress_dialog.log(f"✓ 特征提取完成：平均句长={features.get('avg_sentence_length', 0):.1f}字")
                style_info = features.get('writing_style', {})
                if style_info:
                    progress_dialog.log(f"  视角={style_info.get('narrative_perspective', '未知')}, "
                                      f"节奏={style_info.get('pacing', '未知')}, "
                                      f"描写={style_info.get('descriptive_level', '未知')}")
            
            print(f"[DEBUG] 提取的特征：")
            print(f"  - 平均句长: {features.get('avg_sentence_length', 0):.1f}")
            print(f"  - 词汇丰富度: {features.get('vocabulary_richness', 0):.2f}")
            print(f"  - 常见短语: {features.get('common_phrases', [])[:5]}")
            print(f"  - 句式模式: {features.get('common_patterns', [])}")
            print(f"  - 写作风格: {features.get('writing_style', {})}")
            
            if progress_dialog:
                progress_dialog.log("正在生成润色风格提示词...")
            
            # 生成润色风格提示词
            polish_prompt = generator.generate_polish_style_prompt(kb.name, features)
            
            # 输出润色提示词（调试用）
            print(f"\n[DEBUG] 生成的润色风格提示词：")
            print("=" * 60)
            print(polish_prompt)
            print("=" * 60)
            
            if progress_dialog:
                progress_dialog.log("正在生成预测提示词...")
            
            # 生成预测提示词
            prediction_prompt = generator.generate_prediction_prompt(kb.name, features)
            
            # 输出预测提示词（调试用）
            print(f"\n[DEBUG] 生成的预测提示词：")
            print("=" * 60)
            print(prediction_prompt)
            print("=" * 60)
            
            # 保存为自定义风格
            if progress_dialog:
                progress_dialog.log("正在保存提示词...")
            
            # 生成润色风格ID
            polish_style_id = f"kb_polish_{kb.id[:8]}"
            prediction_style_id = f"kb_prediction_{kb.id[:8]}"
            
            # 添加润色风格（注意：这是润色风格，用于按Enter时的润色）
            polish_style_added = self._style_manager.add_custom_style(
                PolishStyle(
                    id=polish_style_id,
                    name=f"{kb.name} - 润色风格",
                    prompt=polish_prompt,
                    is_preset=False,
                    parameters={}
                )
            )
            
            # 添加预测风格（注意：这也是作为润色风格保存，但在预测时使用）
            prediction_style_added = self._style_manager.add_custom_style(
                PolishStyle(
                    id=prediction_style_id,
                    name=f"{kb.name} - 预测风格",
                    prompt=prediction_prompt,
                    is_preset=False,
                    parameters={}
                )
            )
            
            # 更新知识库的提示词ID
            if polish_style_added and prediction_style_added:
                self._kb_manager.update_kb_prompt_ids(
                    kb.id,
                    polish_style_id=polish_style_id,
                    prediction_style_id=prediction_style_id
                )
                
                # 更新内存中的知识库对象
                kb.polish_style_id = polish_style_id
                kb.prediction_style_id = prediction_style_id
                
                if progress_dialog:
                    progress_dialog.log("✓ 定制化提示词生成成功")
                
                print(f"[INFO] 知识库提示词生成成功: 润色={polish_style_id}, 预测={prediction_style_id}")
            else:
                if progress_dialog:
                    progress_dialog.log("⚠ 提示词保存失败（ID可能已存在）")
                print(f"[WARN] 提示词保存失败")
        
        except Exception as e:
            if progress_dialog:
                progress_dialog.log(f"⚠ 提示词生成失败: {str(e)}")
            print(f"[ERROR] 生成知识库提示词失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _activate_knowledge_base(self, kb):
        """激活指定的知识库
        
        Args:
            kb: 知识库对象
        """
        self._active_kb = kb
        self._active_kb_id = kb.id
        
        # 初始化重排客户端（用于知识库增强预测）
        api_config = self._config_manager.get_api_config()
        if api_config.embedding_api_key:
            # 移除 "not self._rerank_client" 的检查，确保每次都尝试初始化
            from app.knowledge_base import RerankClient
            try:
                self._rerank_client = RerankClient(
                    api_key=api_config.embedding_api_key,
                    model="gte-rerank-v2"  # 使用阿里云的重排序模型
                )
                print(f"[INFO] 重排序客户端已初始化，模型: gte-rerank-v2")
                print(f"[INFO] 重排客户端对象: {self._rerank_client}")
            except Exception as e:
                print(f"[ERROR] 重排序客户端初始化失败: {e}")
                import traceback
                traceback.print_exc()
                self._rerank_client = None
        else:
            print(f"[WARN] 未配置阿里云API密钥，无法初始化重排客户端")
            self._rerank_client = None
        
        # 自动加载知识库关联的提示词
        self._load_kb_prompts(kb)
        
        # 更新UI状态
        if hasattr(self, '_kb_status_label') and self._kb_status_label:
            rerank_status = "已启用" if self._rerank_client else "未启用"
            self._kb_status_label.setText(f"知识库: {kb.name} (重排:{rerank_status})")
            print(f"[INFO] 已激活知识库: {kb.name}, 文档数: {len(kb.documents)}, 重排模型: {rerank_status}")
    
    def _load_kb_prompts(self, kb):
        """加载知识库关联的提示词
        
        Args:
            kb: 知识库对象
        """
        try:
            # 检查知识库是否有关联的润色提示词
            if kb.polish_style_id:
                # 验证提示词是否存在
                polish_style = self._style_manager.get_style_by_id(kb.polish_style_id)
                
                if polish_style:
                    # 自动选择该提示词（用于润色）
                    self._style_manager.set_selected_styles([kb.polish_style_id])
                    print(f"[INFO] 已自动加载知识库润色提示词: {polish_style.name}")
                    self._show_message(
                        f"已加载知识库润色风格: {polish_style.name}",
                        duration_ms=3000,
                        is_error=False
                    )
                else:
                    print(f"[WARN] 知识库关联的润色提示词不存在: {kb.polish_style_id}")
                    self._show_message(
                        "知识库的润色提示词已被删除，将使用当前选择的提示词",
                        duration_ms=3000,
                        is_error=False
                    )
            else:
                print(f"[INFO] 知识库未关联润色提示词，使用当前选择的提示词")
            
            # 预测提示词在调用预测时单独处理，不自动激活
            # （因为预测和润色使用不同的提示词）
            if kb.prediction_style_id:
                prediction_style = self._style_manager.get_style_by_id(kb.prediction_style_id)
                if prediction_style:
                    print(f"[INFO] 知识库预测提示词: {prediction_style.name}")
                else:
                    print(f"[WARN] 知识库关联的预测提示词不存在: {kb.prediction_style_id}")
        
        except Exception as e:
            print(f"[ERROR] 加载知识库提示词失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_select_knowledge_base(self):
        """选择知识库"""
        # 获取所有知识库列表
        kb_list = self._kb_manager.list_knowledge_bases()
        
        if not kb_list:
            QtWidgets.QMessageBox.information(
                self,
                "提示",
                "当前没有可用的知识库。\n\n请先创建一个知识库。"
            )
            return
        
        # 构建选择对话框
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("选择知识库")
        dialog.setModal(True)
        dialog.resize(600, 400)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # 添加说明标签
        info_label = QtWidgets.QLabel(
            "选择一个知识库用于增强剧情预测功能。\n"
            "激活知识库后，AI将基于知识库内容生成更准确的预测。"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 添加知识库列表
        list_widget = QtWidgets.QListWidget()
        list_widget.setObjectName("KBListWidget")
        
        for kb_info in kb_list:
            item_text = f"{kb_info['name']} ({kb_info['total_documents']} 个文档)"
            if self._active_kb_id and kb_info['id'] == self._active_kb_id:
                item_text += " [当前激活]"
            
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(QtCore.Qt.UserRole, kb_info)
            list_widget.addItem(item)
        
        layout.addWidget(list_widget)
        
        # 添加按钮
        button_layout = QtWidgets.QHBoxLayout()
        
        activate_button = QtWidgets.QPushButton("激活选中的知识库")
        activate_button.clicked.connect(lambda: self._on_activate_selected_kb(list_widget, dialog))
        
        deactivate_button = QtWidgets.QPushButton("停用知识库")
        deactivate_button.clicked.connect(lambda: self._on_deactivate_kb(dialog))
        
        cancel_button = QtWidgets.QPushButton("取消")
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addWidget(activate_button)
        button_layout.addWidget(deactivate_button)
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # 应用主题
        if hasattr(self, '_current_theme'):
            dialog.setStyleSheet(f"""
                QDialog {{
                    background-color: {self._current_theme.get('editorBackground', '#1e1e1e')};
                    color: {self._current_theme.get('editorForeground', '#d4d4d4')};
                }}
                QPushButton {{
                    background-color: {self._current_theme.get('buttonBackground', '#0e639c')};
                    color: {self._current_theme.get('buttonForeground', '#ffffff')};
                    border: 1px solid {self._current_theme.get('borderColor', '#3e3e42')};
                    border-radius: 3px;
                    padding: 6px 14px;
                }}
                QPushButton:hover {{
                    background-color: {self._current_theme.get('buttonHoverBackground', '#1177bb')};
                }}
                QListWidget {{
                    background-color: {self._current_theme.get('inputBackground', '#3c3c3c')};
                    color: {self._current_theme.get('inputForeground', '#ffffff')};
                    border: 1px solid {self._current_theme.get('borderColor', '#3e3e42')};
                    border-radius: 3px;
                }}
            """)
        
        dialog.exec()
    
    def _on_activate_selected_kb(self, list_widget, dialog):
        """激活选中的知识库"""
        current_item = list_widget.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.warning(
                dialog,
                "提示",
                "请先选择一个知识库。"
            )
            return
        
        kb_info = current_item.data(QtCore.Qt.UserRole)
        kb_id = kb_info['id']
        
        # 加载知识库
        try:
            kb = self._kb_manager.load_knowledge_base(kb_id)
            if not kb:
                QtWidgets.QMessageBox.warning(
                    dialog,
                    "错误",
                    f"无法加载知识库: {kb_info['name']}"
                )
                return
            
            # 激活知识库
            self._activate_knowledge_base(kb)
            
            QtWidgets.QMessageBox.information(
                dialog,
                "成功",
                f"已激活知识库: {kb.name}\n\n剧情预测功能将基于此知识库生成内容。"
            )
            
            dialog.accept()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                dialog,
                "错误",
                f"加载知识库失败：\n\n{str(e)}"
            )
    
    def _on_deactivate_kb(self, dialog):
        """停用知识库"""
        self._active_kb = None
        self._active_kb_id = None
        
        # 更新UI状态
        if hasattr(self, '_kb_status_label') and self._kb_status_label:
            self._kb_status_label.setText("知识库: 未激活")
        
        QtWidgets.QMessageBox.information(
            dialog,
            "成功",
            "已停用知识库。\n\n剧情预测功能将使用普通模式。"
        )
        
        print(f"[INFO] 已停用知识库")
        dialog.accept()
    
    def _polish_text_with_context_async(self, context_lines: list[str], target_line: str, line_number: int) -> str:
        """使用上下文异步润色文本（使用请求队列避免与预测冲突）"""
        import sys
        print(f"[DEBUG] _polish_text_with_context_async 被调用", flush=True)
        sys.stdout.flush()
        
        try:
            # 获取当前选中的风格组合提示词
            selected_styles = self._style_manager.get_selected_styles()
            style_prompt = self._style_manager.get_combined_prompt(selected_styles) if selected_styles else None
            print(f"[DEBUG] 风格提示词: {style_prompt}", flush=True)
            sys.stdout.flush()
            
            # 生成请求ID
            group_id = next(self._group_sequence)
            request_id = f"polish_{group_id}"
            self._pending_group_id = group_id
            
            # 使用请求队列管理器执行（高优先级，避免与预测冲突）
            # 注意：RequestType 和 RequestPriority 已在文件顶部导入
            
            # 捕获变量以避免闭包问题
            _target_line = target_line
            _line_number = line_number
            _context_lines = context_lines
            _style_prompt = style_prompt
            
            # 定义执行函数 - 直接调用API
            def execute_polish():
                print(f"[DEBUG] 队列中执行润色: {_target_line[:30]}", flush=True)
                return self._api_client.polish_last_line(_context_lines, _target_line, _style_prompt or "")
            
            # 定义成功回调（在主线程中执行）
            def on_success(polished_text):
                print(f"[DEBUG] 润色成功回调: {polished_text[:30] if polished_text else 'None'}", flush=True)
                # 使用QMetaObject.invokeMethod确保在主线程中调用
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "_handle_polish_success",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, polished_text),
                    QtCore.Q_ARG(str, _target_line),
                    QtCore.Q_ARG(int, _line_number)
                )
                print(f"[DEBUG] invokeMethod 已调用", flush=True)
            
            # 定义失败回调
            def on_error(error_message):
                print(f"[DEBUG] 润色失败回调: {error_message}", flush=True)
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "_handle_polish_error",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, error_message)
                )
            
            # 添加到请求队列（高优先级）
            self._request_queue_manager.add_request(
                request_id=request_id,
                request_type=RequestType.POLISH,
                priority=RequestPriority.HIGH,
                execute_func=execute_polish,
                on_success=on_success,
                on_error=on_error
            )
            
            print(f"[DEBUG] 润色请求已加入队列: {request_id}", flush=True)
            sys.stdout.flush()
            
            return request_id
        except Exception as e:
            print(f"[ERROR] _polish_text_with_context_async 发生异常: {e}", flush=True)
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            raise
    
    @QtCore.Slot(str, str, int)
    def _handle_polish_success(self, polished_text: str, original_text: str, line_number: int):
        """处理润色成功（Qt Slot，可从其他线程调用）"""
        print(f"[DEBUG] _handle_polish_success 被调用", flush=True)
        print(f"[DEBUG] 参数: polished_text={polished_text[:30]}, original_text={original_text[:20]}, line_number={line_number}", flush=True)
        try:
            self._on_context_polish_finished(polished_text, original_text, line_number)
        except Exception as e:
            print(f"[ERROR] _handle_polish_success 发生异常: {e}", flush=True)
            import traceback
            traceback.print_exc()
    
    @QtCore.Slot(str)
    def _handle_polish_error(self, error_message: str):
        """处理润色失败（Qt Slot，可从其他线程调用）"""
        print(f"[DEBUG] _handle_polish_error 被调用", flush=True)
        self._on_context_polish_error_wrapper(error_message)
    
    def _on_context_polish_finished_wrapper(self, polished_text: str, original_text: str, line_number: int) -> None:
        """上下文润色完成回调包装器（用于 partial）"""
        import sys
        print(f"[DEBUG] _on_context_polish_finished_wrapper 被调用", flush=True)
        print(f"[DEBUG] 参数: polished_text={polished_text[:30]}, original_text={original_text[:20]}, line_number={line_number}", flush=True)
        sys.stdout.flush()
        
        try:
            self._on_context_polish_finished(polished_text, original_text, line_number)
        except Exception as e:
            print(f"[ERROR] _on_context_polish_finished_wrapper 发生异常: {e}", flush=True)
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
    
    def _on_context_polish_finished(self, polished_text: str, original_text: str, line_number: int) -> None:
        """上下文润色完成回调"""
        import sys
        print(f"[DEBUG] _on_context_polish_finished 被调用", flush=True)
        print(f"[DEBUG] 润色完成 - 原文: {original_text[:20]}... 润色后: {polished_text[:20]}... 行号: {line_number}", flush=True)
        sys.stdout.flush()
        
        try:
            # 在润色结果面板显示结果
            print(f"[DEBUG] 调用 polish_result_panel.add_result", flush=True)
            sys.stdout.flush()
            
            self.polish_result_panel.add_result(original_text, polished_text, line_number)
            
            print(f"[DEBUG] add_result 完成", flush=True)
            sys.stdout.flush()
            
            # 不设置polish_state，保持界面可编辑
            # self._set_polish_state(False)
            self._pending_group_id = None
            
            # 简短提示，不干扰用户
            self._show_message("润色完成，按TAB键覆盖，按~键拒绝", duration_ms=2000, is_error=False)
            print(f"[DEBUG] _on_context_polish_finished 完成", flush=True)
            sys.stdout.flush()
        except Exception as e:
            print(f"[ERROR] _on_context_polish_finished 发生异常: {e}", flush=True)
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
    
    def _on_context_polish_error_wrapper(self, error_message: str) -> None:
        """上下文润色失败回调包装器（用于 partial）"""
        import sys
        print(f"[DEBUG] _on_context_polish_error_wrapper 被调用，错误: {error_message}", flush=True)
        sys.stdout.flush()
        
        try:
            self._on_context_polish_error(error_message)
        except Exception as e:
            print(f"[ERROR] _on_context_polish_error_wrapper 发生异常: {e}", flush=True)
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
    
    def _on_context_polish_error(self, error_message: str) -> None:
        """上下文润色失败回调"""
        import sys
        print(f"[DEBUG] _on_context_polish_error 被调用，错误: {error_message}", flush=True)
        sys.stdout.flush()
        
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
        1. 剧情预测开关已开启
        2. 用户停止输入达到3秒
        3. 文本内容不为空
        4. 没有待处理的预测结果（避免重复预测）
        """
        # 检查剧情预测开关是否开启
        if not hasattr(self, 'prediction_toggle') or not self.prediction_toggle.is_enabled():
            return
        
        # 获取当前编辑器中的全部文本
        full_text = self.editor.toPlainText().strip()
        
        # 如果文本为空，不触发预测
        if not full_text:
            return
        
        # 检查是否已有预测结果未处理（避免重复预测）
        if self.polish_result_panel.has_prediction_results():
            return
        
        # 异步调用剧情预测
        self._predict_plot_continuation_async(full_text)
    
    def _predict_plot_continuation_async(self, full_text: str) -> None:
        """异步预测剧情续写（使用请求队列避免与润色冲突）
        
        Args:
            full_text: 当前编辑器中的全部文本内容
        """
        # 优先使用知识库的预测提示词，如果不存在则使用当前选中的风格
        style_prompt = None
        
        if self._active_kb and self._active_kb.prediction_style_id:
            # 尝试获取知识库的预测提示词
            prediction_style = self._style_manager.get_style_by_id(self._active_kb.prediction_style_id)
            if prediction_style:
                style_prompt = prediction_style.prompt
                print(f"[INFO] 使用知识库预测提示词: {prediction_style.name}")
            else:
                print(f"[WARN] 知识库预测提示词不存在，回退到当前选中的风格")
        
        # 如果没有知识库预测提示词，使用当前选中的风格组合提示词
        if not style_prompt:
            selected_styles = self._style_manager.get_selected_styles()
            style_prompt = self._style_manager.get_combined_prompt(selected_styles) if selected_styles else None
        
        # 生成请求ID
        import time
        request_id = f"prediction_{int(time.time() * 1000)}"
        
        # 使用请求队列管理器执行（低优先级，让润色请求优先）
        # 注意：RequestType 和 RequestPriority 已在文件顶部导入
        
        # 捕获变量
        _full_text = full_text
        _style_prompt = style_prompt
        
        # 检查是否有活动的知识库
        has_kb = self._active_kb is not None and self._active_kb.documents
        
        # 定义执行函数
        def execute_prediction():
            if has_kb:
                # 使用知识库增强预测
                print(f"[INFO] 使用知识库增强预测，知识库: {self._active_kb.name}")
                print(f"[INFO] 重排客户端状态: {'已初始化' if self._rerank_client else '未初始化'}")
                if self._rerank_client:
                    print(f"[INFO] 重排客户端对象: {self._rerank_client}")
                
                # 确保向量化客户端已初始化
                api_config = self._config_manager.get_api_config()
                if api_config.embedding_api_key:
                    self._kb_manager.set_embedding_client(
                        api_config.embedding_api_key,
                        api_config.embedding_model
                    )
                
                # 提取当前上下文（最后1000字，用于知识库检索）
                from app.api_client import truncate_context
                current_context = truncate_context(_full_text, max_chars=1000)
                
                print(f"[INFO] 准备调用知识库增强预测，上下文长度: {len(current_context)}")
                
                # 调用知识库增强预测
                return self._api_client.predict_plot_continuation_with_kb(
                    current_context=current_context,
                    kb_manager=self._kb_manager,
                    kb=self._active_kb,
                    rerank_client=self._rerank_client,
                    style_prompt=_style_prompt or "",
                    min_relevance_threshold=0.25  # 使用用户调整后的阈值
                )
            else:
                # 使用普通预测（无知识库）
                print(f"[INFO] 使用普通预测（无活动知识库）")
                return self._api_client.predict_plot_continuation(_full_text, _style_prompt or "")
        
        # 定义成功回调（需要在主线程中执行）
        def on_success(predicted_text):
            print(f"[DEBUG] 预测成功回调", flush=True)
            QtCore.QMetaObject.invokeMethod(
                self,
                "_handle_prediction_success",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(str, predicted_text)
            )
            print(f"[DEBUG] 预测 invokeMethod 已调用", flush=True)
        
        # 定义失败回调
        def on_error(error_message):
            QtCore.QMetaObject.invokeMethod(
                self,
                "_handle_prediction_error",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(str, error_message)
            )
        
        # 添加到请求队列（低优先级，让润色请求先执行）
        self._request_queue_manager.add_request(
            request_id=request_id,
            request_type=RequestType.PREDICTION,
            priority=RequestPriority.LOW,
            execute_func=execute_prediction,
            on_success=on_success,
            on_error=on_error
        )
        
        # 显示简短提示，不干扰用户
        if has_kb:
            self._show_message(f"知识库增强预测已加入队列...", duration_ms=1500, is_error=False)
        else:
            self._show_message("剧情预测已加入队列...", duration_ms=1500, is_error=False)
    
    @QtCore.Slot(str)
    def _handle_prediction_success(self, predicted_text: str):
        """处理预测成功（Qt Slot，可从其他线程调用）"""
        print(f"[DEBUG] _handle_prediction_success 被调用", flush=True)
        self._on_plot_prediction_finished(predicted_text)
    
    @QtCore.Slot(str)
    def _handle_prediction_error(self, error_message: str):
        """处理预测失败（Qt Slot，可从其他线程调用）"""
        print(f"[DEBUG] _handle_prediction_error 被调用", flush=True)
        self._on_plot_prediction_error(error_message)
    
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
        result_count = self.polish_result_panel.get_result_count()
        if result_count == 0:
            self._show_message("没有可拒绝的润色结果", duration_ms=1500, is_error=True)
            return
        
        self.polish_result_panel.hide_result()
        self._show_message(f"已批量拒绝 {result_count} 个润色结果", duration_ms=1500, is_error=False)

    def _start_polish(self, context_lines: list[str], target_line: str) -> None:
        """开始润色（使用请求队列避免冲突）"""
        group_id = next(self._group_sequence)
        self._pending_group_id = group_id
        self._add_output_entry(text=target_line, is_original=True, group_id=group_id)
        self._set_polish_state(True)
        self._show_message("润色请求已加入队列…", duration_ms=0, is_error=False)

        # 获取当前选中的风格组合提示词
        selected_styles = self._style_manager.get_selected_styles()
        style_prompt = self._style_manager.get_combined_prompt(selected_styles) if selected_styles else None
        
        # 使用请求队列管理器执行
        # 注意：RequestType 和 RequestPriority 已在文件顶部导入
        
        request_id = f"polish_legacy_{group_id}"
        
        # 捕获变量
        _group_id = group_id
        _context_lines = context_lines
        _target_line = target_line
        _style_prompt = style_prompt
        
        # 定义执行函数
        def execute_polish():
            return self._api_client.polish_last_line(_context_lines, _target_line, _style_prompt or "")
        
        # 定义成功回调
        def on_success(polished_text):
            QtCore.QMetaObject.invokeMethod(
                self,
                "_handle_legacy_polish_success",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(int, _group_id),
                QtCore.Q_ARG(str, polished_text)
            )
        
        # 定义失败回调
        def on_error(error_message):
            QtCore.QMetaObject.invokeMethod(
                self,
                "_handle_legacy_polish_error",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(int, _group_id),
                QtCore.Q_ARG(str, error_message)
            )
        
        # 添加到请求队列（高优先级）
        self._request_queue_manager.add_request(
            request_id=request_id,
            request_type=RequestType.POLISH,
            priority=RequestPriority.HIGH,
            execute_func=execute_polish,
            on_success=on_success,
            on_error=on_error
        )

    @QtCore.Slot(int, str)
    def _handle_legacy_polish_success(self, group_id: int, polished_text: str):
        """处理旧版润色成功（Qt Slot，可从其他线程调用）"""
        print(f"[DEBUG] _handle_legacy_polish_success 被调用", flush=True)
        self._on_polish_finished(group_id, polished_text)
    
    @QtCore.Slot(int, str)
    def _handle_legacy_polish_error(self, group_id: int, error_message: str):
        """处理旧版润色失败（Qt Slot，可从其他线程调用）"""
        print(f"[DEBUG] _handle_legacy_polish_error 被调用", flush=True)
        self._on_polish_error(group_id, error_message)
    
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
                    "QPushButton#SelectExportDirButton {",
                    f"  background-color: {theme['buttonBackground']};",
                    f"  color: {theme['buttonForeground']};",
                    f"  border: 1px solid {theme['borderColor']};",
                    "  border-radius: 4px;",
                    "  padding: 6px 14px;",
                    "}",
                    "QPushButton#SelectExportDirButton:hover {",
                    f"  background-color: {theme['accent']};",
                    "  color: #ffffff;",
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
                    "QLabel#AutoExportStatusLabel {",
                    "  font-size: 11px;",
                    f"  color: {theme.get('accent', '#007acc')};",
                    "  padding: 4px 8px;",
                    f"  border: 1px solid {theme['borderColor']};",
                    "  border-radius: 3px;",
                    f"  background-color: {theme.get('panelBackground', '#2d2d30')};",
                    "}",
                    "QLabel#KBStatusLabel {",
                    "  font-size: 11px;",
                    f"  color: {theme.get('accent', '#007acc')};",
                    "  padding: 4px 8px;",
                    f"  border: 1px solid {theme['borderColor']};",
                    "  border-radius: 3px;",
                    f"  background-color: {theme.get('panelBackground', '#2d2d30')};",
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
        
        # 更新文件资源管理器主题
        if hasattr(self, 'file_explorer'):
            self.file_explorer.set_theme(self._current_theme)
        
        # 更新剧情预测开关主题
        if hasattr(self, 'prediction_toggle'):
            self.prediction_toggle.set_theme(self._current_theme)

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
    
    def _on_request_started(self, request_id: str, request_type: str):
        """请求开始处理"""
        # 可选：更新UI显示处理状态
        pass
    
    def _on_request_completed(self, request_id: str, result):
        """请求完成"""
        # 可选：记录完成状态
        pass
    
    def _on_request_failed(self, request_id: str, error_message: str):
        """请求失败"""
        # 可选：记录失败状态
        pass
    
    def _on_file_opened(self, file_path: str):
        """文件被打开"""
        print(f"[INFO] 打开文件: {file_path}", flush=True)
        
        # 读取文件内容
        content = DocumentHandler.read_document(file_path)
        
        if content is None:
            QtWidgets.QMessageBox.warning(
                self,
                "错误",
                f"无法读取文件：{file_path}\n\n请检查文件格式是否支持。"
            )
            return
        
        # 设置到编辑器
        self.editor.setPlainText(content)
        
        # 保存当前文件路径
        self._current_file_path = file_path
        
        # 启动自动保存
        self._auto_save_manager.start(
            file_path=file_path,
            get_content_func=lambda: self.editor.toPlainText(),
            save_func=DocumentHandler.write_document
        )
        
        self._show_message(f"已打开文件：{Path(file_path).name}，自动保存已启用", duration_ms=3000, is_error=False)
    
    def _on_new_file_requested(self, file_path: str):
        """创建新文件"""
        print(f"[INFO] 创建新文件: {file_path}", flush=True)
        
        # 创建新文件
        success = DocumentHandler.create_new_document(file_path, "# 新建文档\n\n开始您的创作...")
        
        if not success:
            QtWidgets.QMessageBox.warning(
                self,
                "错误",
                f"无法创建文件：{file_path}"
            )
            return
        
        # 读取并打开新文件
        self._on_file_opened(file_path)
        
        # 刷新文件浏览器
        self.file_explorer._refresh()
    
    def _on_auto_save_completed(self, success: bool, message: str):
        """自动保存完成"""
        if success:
            # 显示简短提示（不干扰用户）
            self._show_message(message, duration_ms=1500, is_error=False)
        else:
            # 显示错误
            self._show_message(f"自动保存失败: {message}", duration_ms=3000, is_error=True)
    
    def _on_batch_polish_clicked(self):
        """一键润色按钮点击 - 直接使用当前润色风格"""
        try:
            # 获取当前编辑器内容
            content = self.editor.toPlainText().strip()
            
            if not content:
                QtWidgets.QMessageBox.warning(
                    self,
                    "提示",
                    "编辑器内容为空，无法进行批量润色。\n\n请先输入或打开文档。"
                )
                return
            
            # 获取当前选中的润色风格
            try:
                selected_styles = self._style_manager.get_selected_styles()
            except Exception as e:
                print(f"[ERROR] 获取润色风格失败: {e}", flush=True)
                import traceback
                traceback.print_exc()
                QtWidgets.QMessageBox.critical(
                    self,
                    "错误",
                    f"获取润色风格失败：{str(e)}\n\n请检查设置或重启应用。"
                )
                return
            
            if not selected_styles:
                # 如果没有选择风格，提示用户先设置风格
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "未选择润色风格",
                    "您还未选择润色风格。\n\n"
                    "一键润色功能需要使用您在设置中选择的润色风格。\n"
                    "是否现在打开设置选择风格？",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes
                )
                
                if reply == QtWidgets.QMessageBox.Yes:
                    self._on_settings_clicked()
                return
            
            # 显示风格信息并确认
            try:
                style_names = [style.name for style in selected_styles]
                style_list = "、".join(style_names)
            except Exception as e:
                print(f"[ERROR] 处理风格名称失败: {e}", flush=True)
                import traceback
                traceback.print_exc()
                style_list = "未知风格"
            
            reply = QtWidgets.QMessageBox.question(
                self,
                "确认批量润色",
                f"将使用以下润色风格对整个文档进行润色：\n\n"
                f"【当前风格】{style_list}\n\n"
                f"文档字数：约 {len(content)} 字\n\n"
                f"⚠️ 注意：此操作将替换文档内容，建议先备份。\n\n"
                f"确定要继续吗？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                # 直接调用润色，不需要额外的需求输入
                self._on_batch_polish_requested("", content)
                
        except Exception as e:
            # 捕获所有未处理的异常，防止闪退
            print(f"[ERROR] 一键润色发生未知错误: {e}", flush=True)
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"一键润色功能发生错误：\n\n{str(e)}\n\n请查看控制台日志了解详情。"
            )
    
    def _on_batch_polish_requested(self, requirement: str, original_content: str):
        """执行批量润色
        
        Args:
            requirement: 额外的润色需求（可为空，空时仅使用当前选中的风格）
            original_content: 要润色的原始内容
        """
        try:
            print(f"[INFO] 开始批量润色，额外需求: {requirement[:50] if requirement else '无'}...", flush=True)
            
            # 获取用户当前设置的风格提示词（一键润色直接使用用户风格设置）
            try:
                selected_styles = self._style_manager.get_selected_styles()
                style_prompt = self._style_manager.get_combined_prompt(selected_styles) if selected_styles else ""
            except Exception as e:
                print(f"[ERROR] 获取风格提示词失败: {e}", flush=True)
                import traceback
                traceback.print_exc()
                style_prompt = ""
            
            # 构建最终的润色提示词
            if requirement:
                # 如果有额外需求，将风格和需求合并
                combined_requirement = f"【基础润色风格】\n{style_prompt}\n\n【额外需求】\n{requirement}" if style_prompt else requirement
            else:
                # 一键润色：只使用当前选中的风格，无需额外需求
                combined_requirement = style_prompt if style_prompt else "请润色以下文本，保持原意的同时提升表达质量。"
            
            print(f"[DEBUG] 使用当前风格进行润色，提示词长度: {len(combined_requirement)}", flush=True)
            
            # 显示进度对话框
            progress_dialog = QtWidgets.QProgressDialog(
                "正在润色文档...\n\n这可能需要一些时间，请耐心等待。",
                "取消",
                0,
                0,
                self
            )
            progress_dialog.setWindowTitle("批量润色中")
            progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.setValue(0)
            
            # 在后台线程中执行，使用合并后的提示词
            # 保存worker引用，防止被垃圾回收
            self._batch_polish_worker = BatchPolishWorker(self._api_client, original_content, combined_requirement)
            self._batch_polish_worker.finished.connect(lambda polished: self._on_batch_polish_finished(polished, progress_dialog))
            self._batch_polish_worker.error.connect(lambda error_msg: self._on_batch_polish_error(error_msg, progress_dialog))
            self._batch_polish_worker.start()
            
            # 显示进度对话框
            progress_dialog.show()
            
        except Exception as e:
            # 捕获所有未处理的异常，防止闪退
            print(f"[ERROR] 执行批量润色时发生错误: {e}", flush=True)
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"执行批量润色时发生错误：\n\n{str(e)}\n\n请查看控制台日志了解详情。"
            )
    
    def _on_batch_polish_finished(self, polished_content: str, progress_dialog):
        """批量润色完成"""
        try:
            progress_dialog.close()
            
            # 替换编辑器内容
            self.editor.setPlainText(polished_content)
            
            # 如果有打开的文件，立即保存
            if self._current_file_path and self._auto_save_manager.is_enabled:
                self._auto_save_manager.save_now()
            
            QtWidgets.QMessageBox.information(
                self,
                "润色完成",
                f"文档已成功润色！\n\n原文档字数：约{len(polished_content)}字"
            )
            
            self._show_message("批量润色完成", duration_ms=3000, is_error=False)
            
        except Exception as e:
            print(f"[ERROR] 处理润色完成时发生错误: {e}", flush=True)
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"处理润色结果时发生错误：\n\n{str(e)}"
            )
    
    def _on_batch_polish_error(self, error_message: str, progress_dialog):
        """批量润色失败"""
        try:
            progress_dialog.close()
            
            QtWidgets.QMessageBox.warning(
                self,
                "润色失败",
                f"批量润色失败：\n\n{error_message}"
            )
            
            self._show_message(f"批量润色失败: {error_message}", duration_ms=3000, is_error=True)
            
        except Exception as e:
            print(f"[ERROR] 处理润色错误时发生异常: {e}", flush=True)
            import traceback
            traceback.print_exc()
    
    def closeEvent(self, event):
        """窗口关闭事件 - 清理资源"""
        try:
            # 停止自动保存管理器
            if hasattr(self, '_auto_save_manager') and self._auto_save_manager:
                self._auto_save_manager.stop()
            
            # 停止请求队列管理器
            if hasattr(self, '_request_queue_manager') and self._request_queue_manager:
                self._request_queue_manager.stop()
            
            # 停止心跳管理器
            if hasattr(self, '_heartbeat_manager') and self._heartbeat_manager:
                self._heartbeat_manager.stop()
            
            # 停止异步润色处理器
            if hasattr(self, '_async_polish_processor') and self._async_polish_processor:
                if hasattr(self._async_polish_processor, 'worker') and self._async_polish_processor.worker:
                    self._async_polish_processor.worker.stop()
            
            # 关闭API客户端连接池
            if hasattr(self, '_api_client') and self._api_client:
                self._api_client.close()
            
            # 接受关闭事件
            event.accept()
        except Exception as e:
            # 即使出错也要关闭窗口
            print(f"[WARNING] 关闭时清理资源出错: {e}")
            event.accept()


def main() -> None:
    load_dotenv()
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("字见润新")
    app.setOrganizationName("GuojiRunse")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
