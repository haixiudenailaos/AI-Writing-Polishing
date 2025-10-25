""" 
润色结果面板组件
专用于显示和编辑润色结果的UI组件，支持累积显示多个润色结果
实现与左侧编辑器的行号同步机制
支持用户选择和替换特定润色结果
"""

from typing import Dict, Optional, Callable, List
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSignal, QTimer
from dataclasses import dataclass


@dataclass
class PolishResultItem:
    """润色结果项数据类"""
    original_text: str  # 原始文本
    polished_text: str  # 润色后的文本
    line_number: int  # 对应的行号
    timestamp: float  # 创建时间戳
    is_selected: bool = False  # 是否被选中
    current_text: str = ""  # 当前编辑后的文本（可能被用户修改）
    is_prediction: bool = False  # 是否为AI预测的剧情续写
    
    def __post_init__(self):
        if not self.current_text:
            self.current_text = self.polished_text


class PolishResultPanel(QtWidgets.QWidget):
    """润色结果面板 - 累积显示多个润色结果并提供编辑和操作功能"""
    
    # 信号定义
    acceptResult = pyqtSignal()  # TAB键一键覆盖信号
    rejectResult = pyqtSignal()  # ~键一键拒绝信号
    resultEdited = pyqtSignal(str)  # 结果编辑信号
    
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._current_theme: Dict[str, str] = {}
        self._result_items: List[PolishResultItem] = []  # 润色结果队列
        self._current_selected_index: int = -1  # 当前选中的结果索引
        self._is_visible: bool = False
        self._left_editor = None  # 左侧编辑器引用，用于同步滚动
        
        self.setObjectName("PolishResultPanel")
        self._setup_ui()
        self._connect_signals()
        
        # 默认隐藏面板
        self.hide()
    
    def _setup_ui(self) -> None:
        """设置UI布局 - 累积显示多个润色结果"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 配置编辑器字体（与左侧编辑器保持一致）
        editor_font = QtGui.QFont()
        editor_font.setFamily("Cascadia Code")
        editor_font.setPointSize(12)
        editor_font.setStyleHint(QtGui.QFont.Monospace)
        editor_font.setFixedPitch(True)
        
        # 润色结果累积显示区（支持多个结果）
        self._result_editor = QtWidgets.QPlainTextEdit()
        self._result_editor.setObjectName("ResultEditor")
        self._result_editor.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self._result_editor.setFont(editor_font)
        self._result_editor.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
        
        # 设置占位符文本
        self._result_editor.setPlaceholderText("润色结果将在此累积显示，格式为 [L行号] 文本内容，按TAB键替换到左侧，按~键拒绝")
        
        # 设置与左侧编辑器相同的Tab宽度
        metrics = QtGui.QFontMetrics(editor_font)
        self._result_editor.setTabStopDistance(metrics.horizontalAdvance(" ") * 4)
        
        layout.addWidget(self._result_editor)
        
        # 设置面板样式
        self.setStyleSheet("""
            QWidget#PolishResultPanel {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                border-radius: 4px;
            }
        """)
    
    def _connect_signals(self) -> None:
        """连接信号槽"""
        self._result_editor.textChanged.connect(self._on_text_changed)
    

    
    def _on_text_changed(self) -> None:
        """处理文本变化 - 用户编辑了润色结果"""
        # 用户编辑后，触发编辑信号
        current_text = self._result_editor.toPlainText()
        self.resultEdited.emit(current_text)
    
    def add_result(self, original_text: str, polished_text: str, line_number: int = -1, is_prediction: bool = False) -> None:
        """添加润色结果到累积队列
        
        Args:
            original_text: 原始文本
            polished_text: 润色后的文本
            line_number: 对应的行号，用于对齐
            is_prediction: 是否为AI预测的剧情续写
        """
        import time
        
        # 检查是否已存在相同行号的润色结果，如果存在则删除旧的
        if line_number >= 0:
            # 查找并删除相同行号的旧结果
            old_result_indices = [i for i, item in enumerate(self._result_items) if item.line_number == line_number]
            # 从后往前删除，避免索引错位
            for idx in reversed(old_result_indices):
                self._result_items.pop(idx)
        
        # 创建新的结果项
        result_item = PolishResultItem(
            original_text=original_text,
            polished_text=polished_text,
            line_number=line_number,
            timestamp=time.time(),
            is_prediction=is_prediction
        )
        
        # 添加到队列
        self._result_items.append(result_item)
        
        # 更新显示
        self._refresh_display()
        
        # 显示面板
        if not self._is_visible:
            self._is_visible = True
            self.show()
        
        # 自动选中最新添加的结果
        self._select_result(len(self._result_items) - 1)
    
    def _refresh_display(self) -> None:
        """刷新显示所有累积的润色结果（显示行号，预测类型标记）"""
        if not self._result_items:
            self._result_editor.clear()
            return
        
        # 构建显示文本：每个结果占一行，格式为 "[行号] 润色文本" 或 "[预测L行号] 预测文本"
        display_lines = []
        for item in self._result_items:
            if item.is_prediction:
                # 预测类型：显示 "[预测L行号] 文本"
                line_number_prefix = f"[预测L{item.line_number + 1}] "
            else:
                # 普通润色：显示 "[L行号] 文本"
                line_number_prefix = f"[L{item.line_number + 1}] "
            display_lines.append(line_number_prefix + item.current_text)
        
        # 更新编辑器内容
        self._result_editor.blockSignals(True)
        self._result_editor.setPlainText("\n".join(display_lines))
        self._result_editor.blockSignals(False)
    
    def _select_result(self, index: int) -> None:
        """选中指定索引的结果
        
        Args:
            index: 结果索引
        """
        if index < 0 or index >= len(self._result_items):
            return
        
        # 取消上一个选中项
        if 0 <= self._current_selected_index < len(self._result_items):
            self._result_items[self._current_selected_index].is_selected = False
        
        # 设置当前选中
        self._current_selected_index = index
        self._result_items[index].is_selected = True
        
        # 高亮显示选中行（将光标移动到该行）
        cursor = self._result_editor.textCursor()
        cursor.movePosition(QtGui.QTextCursor.Start)
        for i in range(index):
            cursor.movePosition(QtGui.QTextCursor.Down)
        
        # 选中整行
        cursor.movePosition(QtGui.QTextCursor.StartOfBlock)
        cursor.movePosition(QtGui.QTextCursor.EndOfBlock, QtGui.QTextCursor.KeepAnchor)
        self._result_editor.setTextCursor(cursor)
    
    def get_current_text(self) -> Optional[str]:
        """获取当前选中的润色结果文本
        
        Returns:
            当前选中的结果文本，没有选中则返回 None
        """
        selected_result = self.get_current_selected_result()
        return selected_result.current_text if selected_result else None
    
    def get_current_selected_result(self) -> Optional[PolishResultItem]:
        """获取当前选中的润色结果
        
        Returns:
            当前选中的结果项，没有选中则返回 None
        """
        if 0 <= self._current_selected_index < len(self._result_items):
            # 获取选中行的当前文本（可能已被编辑）
            selected_item = self._result_items[self._current_selected_index]
            
            # 更新 current_text 为编辑器中的实际内容
            cursor = self._result_editor.textCursor()
            cursor.movePosition(QtGui.QTextCursor.Start)
            for i in range(self._current_selected_index):
                cursor.movePosition(QtGui.QTextCursor.Down)
            cursor.movePosition(QtGui.QTextCursor.StartOfBlock)
            cursor.movePosition(QtGui.QTextCursor.EndOfBlock, QtGui.QTextCursor.KeepAnchor)
            line_text = cursor.selectedText()
            
            # 解析行号前缀 "[L行号] 文本内容" 或 "[预测L行号] 文本内容"
            import re
            match = re.match(r'^\[(预测)?L\d+\]\s*(.*)$', line_text)
            if match:
                selected_item.current_text = match.group(2).strip()
            else:
                selected_item.current_text = line_text.strip()
            
            return selected_item
        return None
    
    def get_all_results(self) -> List[PolishResultItem]:
        """获取所有累积的润色结果
        
        Returns:
            所有结果项的列表
        """
        # 更新所有结果的 current_text 为编辑器中的实际内容
        editor_lines = self._result_editor.toPlainText().splitlines()
        
        import re
        for idx, item in enumerate(self._result_items):
            if idx < len(editor_lines):
                # 解析行号前缀 "[L行号] 文本内容" 或 "[预测L行号] 文本内容"
                match = re.match(r'^\[(预测)?L\d+\]\s*(.*)$', editor_lines[idx])
                if match:
                    item.current_text = match.group(2).strip()
                else:
                    item.current_text = editor_lines[idx].strip()
        
        return self._result_items.copy()
    
    def remove_current_result(self) -> None:
        """移除当前选中的结果"""
        if 0 <= self._current_selected_index < len(self._result_items):
            self._result_items.pop(self._current_selected_index)
            
            # 如果队列为空，隐藏面板
            if not self._result_items:
                self.hide_result()
                return
            
            # 调整选中索引
            if self._current_selected_index >= len(self._result_items):
                self._current_selected_index = len(self._result_items) - 1
            
            # 刷新显示
            self._refresh_display()
            self._select_result(self._current_selected_index)
    
    def adjust_line_numbers(self, changed_line: int, delta: int) -> None:
        """
        调整润色结果的行号（当用户插入/删除行时）
        
        Args:
            changed_line: 发生变化的行号（从0开始）
            delta: 行数变化量（正数表示插入，负数表示删除）
        
        逻辑说明：
        - 插入新行：在第N行插入时，所有行号 >= N 的润色结果行号都应 +1
        - 删除行：删除第N行时，所有行号 >= N 的润色结果行号都应 -1
        """
        for item in self._result_items:
            # 调整变化行及之后的所有结果（使用 >= 而非 >）
            if item.line_number >= changed_line:
                item.line_number += delta
                # 确保行号不为负
                if item.line_number < 0:
                    item.line_number = 0
        
        # 刷新显示以反映行号变化
        self._refresh_display()
    
    def hide_result(self) -> None:
        """隐藏润色结果面板并清空所有累积结果"""
        if self._is_visible:
            self._is_visible = False
            self.hide()
            self._result_editor.clear()
            self._result_items.clear()
            self._current_selected_index = -1
    
    def set_left_editor(self, editor) -> None:
        """
        设置左侧编辑器引用，用于同步滚动
        
        Args:
            editor: 左侧编辑器实例
        """
        self._left_editor = editor
    
    def get_result_count(self) -> int:
        """获取累积的润色结果数量"""
        return len(self._result_items)
    
    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """处理键盘事件"""
        if event.key() == QtCore.Qt.Key_Tab and event.modifiers() == QtCore.Qt.NoModifier:
            self.acceptResult.emit()
            event.accept()
            return
        elif event.key() in (QtCore.Qt.Key_QuoteLeft, QtCore.Qt.Key_AsciiTilde) and event.modifiers() == QtCore.Qt.NoModifier:
            self.rejectResult.emit()
            event.accept()
            return
        elif event.key() == QtCore.Qt.Key_Up and event.modifiers() == QtCore.Qt.NoModifier:
            # 上箭头：选中上一个结果
            if self._current_selected_index > 0:
                self._select_result(self._current_selected_index - 1)
            event.accept()
            return
        elif event.key() == QtCore.Qt.Key_Down and event.modifiers() == QtCore.Qt.NoModifier:
            # 下箭头：选中下一个结果
            if self._current_selected_index < len(self._result_items) - 1:
                self._select_result(self._current_selected_index + 1)
            event.accept()
            return
        super().keyPressEvent(event)
    
    def update_theme(self, theme: Dict[str, str]) -> None:
        """更新主题样式"""
        self._current_theme = dict(theme)
        
        # 面板背景色
        panel_bg = theme.get('panelBackground', '#2d2d30')
        border_color = theme.get('borderColor', '#3e3e42')
        
        # 编辑器颜色
        editor_bg = theme.get('editorBackground', '#1e1e1e')
        editor_fg = theme.get('editorForeground', '#d4d4d4')
        
        panel_stylesheet = f"""
            QWidget#PolishResultPanel {{
                background-color: {panel_bg};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            
            QPlainTextEdit#ResultEditor {{
                background-color: {editor_bg};
                color: {editor_fg};
                border: none;
                border-radius: 4px;
                padding: 0px;
                selection-background-color: {theme.get('selection', '#264f78')};
            }}
        """
        
        self.setStyleSheet(panel_stylesheet)
        
        # 更新编辑器调色板
        palette = self._result_editor.palette()
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(editor_bg))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor(editor_fg))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(theme.get('selection', '#264f78')))
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor('#ffffff'))
        self._result_editor.setPalette(palette)