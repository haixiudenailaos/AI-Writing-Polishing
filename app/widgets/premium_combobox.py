"""
专业级下拉列表组件
参考 Figma、Linear、Vercel 等顶级产品设计
"""

from typing import Dict, Optional
from PySide6 import QtWidgets, QtCore, QtGui


class PremiumComboBox(QtWidgets.QComboBox):
    """大厂级设计的下拉列表组件
    
    设计特点：
    - 微妙的渐变和阴影
    - 流畅的动画过渡
    - 精致的图标和间距
    - 高对比度的选中状态
    - 响应式的 hover 效果
    """
    
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._current_theme: Dict[str, str] = {}
        self._is_hovered = False
        self._is_focused = False
        
        # 设置基础属性
        self.setMinimumHeight(32)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        
        # 安装事件过滤器以捕获 hover 状态
        self.installEventFilter(self)
        
        # 创建自定义下拉视图
        self._setup_view()
    
    def _setup_view(self):
        """设置下拉视图的高级样式"""
        view = QtWidgets.QListView(self)
        view.setObjectName("PremiumComboBoxView")
        
        # 设置视图属性
        view.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        view.setUniformItemSizes(True)
        
        # 启用平滑滚动
        view.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        self.setView(view)
        
        # 设置下拉列表的项目代理以自定义渲染
        delegate = PremiumItemDelegate(self)
        self.setItemDelegate(delegate)
    
    def set_theme(self, theme: Dict[str, str]):
        """设置主题"""
        self._current_theme = theme
        self._apply_theme()
        
        # 更新代理主题
        if self.itemDelegate():
            self.itemDelegate().set_theme(theme)
    
    def _apply_theme(self):
        """应用专业级主题样式"""
        if not self._current_theme:
            return
        
        # 提取主题颜色
        bg = self._current_theme.get('inputBackground', '#1e1e1e')
        fg = self._current_theme.get('inputForeground', '#cccccc')
        border = self._current_theme.get('inputBorder', '#3c3c3c')
        hover_bg = self._current_theme.get('listHoverBackground', '#2a2a2a')
        focus_border = self._current_theme.get('focusBorder', '#007acc')
        accent = self._current_theme.get('accent', '#007acc')
        dropdown_bg = self._current_theme.get('dropdownBackground', '#252526')
        selected_bg = self._current_theme.get('listActiveSelectionBackground', '#094771')
        
        # 计算微妙的渐变色
        bg_color = QtGui.QColor(bg)
        gradient_start = bg_color.lighter(105).name()
        gradient_end = bg_color.darker(105).name()
        
        style_sheet = f"""
        /* 主容器 */
        PremiumComboBox {{
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 {gradient_start},
                stop:1 {bg}
            );
            border: 1px solid {border};
            border-radius: 6px;
            padding: 6px 32px 6px 12px;
            color: {fg};
            font-size: 13px;
            font-weight: 500;
            selection-background-color: {accent};
            min-height: 32px;
        }}
        
        /* Hover 状态 */
        PremiumComboBox:hover {{
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 {gradient_start},
                stop:1 {hover_bg}
            );
            border-color: {QtGui.QColor(border).lighter(130).name()};
        }}
        
        /* 聚焦状态 */
        PremiumComboBox:focus {{
            border: 2px solid {focus_border};
            padding: 5px 31px 5px 11px;
            background: {bg};
        }}
        
        /* 按下状态 */
        PremiumComboBox:pressed {{
            background: {QtGui.QColor(bg).darker(110).name()};
        }}
        
        /* 禁用状态 */
        PremiumComboBox:disabled {{
            background: {QtGui.QColor(bg).darker(120).name()};
            color: {QtGui.QColor(fg).darker(150).name()};
            border-color: {QtGui.QColor(border).darker(110).name()};
        }}
        
        /* 下拉按钮区域 */
        PremiumComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 28px;
            border: none;
            border-left: 1px solid {QtGui.QColor(border).lighter(110).name()};
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
            background: transparent;
        }}
        
        PremiumComboBox::drop-down:hover {{
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 transparent,
                stop:1 {QtGui.QColor(accent).darker(300).name()}
            );
        }}
        
        PremiumComboBox::drop-down:pressed {{
            background: {QtGui.QColor(accent).darker(200).name()};
        }}
        
        /* 下拉箭头 - 使用现代化的 chevron 图标 */
        PremiumComboBox::down-arrow {{
            image: none;
            width: 0;
            height: 0;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {fg};
            margin-right: 8px;
        }}
        
        PremiumComboBox::down-arrow:hover {{
            border-top-color: {accent};
        }}
        
        PremiumComboBox::down-arrow:on {{
            /* 展开时旋转箭头 */
            border-top: 6px solid {accent};
        }}
        
        /* 下拉列表容器 */
        QAbstractItemView#PremiumComboBoxView {{
            background-color: {dropdown_bg};
            border: 1px solid {focus_border};
            border-radius: 8px;
            outline: none;
            padding: 4px;
            /* 添加阴影效果（通过边框模拟） */
            margin-top: 2px;
        }}
        
        /* 列表项 */
        QAbstractItemView#PremiumComboBoxView::item {{
            background-color: transparent;
            color: {fg};
            border: none;
            border-radius: 4px;
            padding: 8px 12px;
            margin: 1px 0;
            min-height: 32px;
        }}
        
        /* 列表项 Hover */
        QAbstractItemView#PremiumComboBoxView::item:hover {{
            background-color: {hover_bg};
            color: {QtGui.QColor(fg).lighter(110).name()};
        }}
        
        /* 列表项选中 */
        QAbstractItemView#PremiumComboBoxView::item:selected {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 {selected_bg},
                stop:1 {QtGui.QColor(selected_bg).lighter(120).name()}
            );
            color: #ffffff;
            font-weight: 600;
        }}
        
        /* 滚动条 */
        QAbstractItemView#PremiumComboBoxView QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            border: none;
            margin: 0;
        }}
        
        QAbstractItemView#PremiumComboBoxView QScrollBar::handle:vertical {{
            background: {QtGui.QColor(fg).darker(300).name()};
            border-radius: 5px;
            min-height: 20px;
            margin: 2px;
        }}
        
        QAbstractItemView#PremiumComboBoxView QScrollBar::handle:vertical:hover {{
            background: {QtGui.QColor(fg).darker(200).name()};
        }}
        
        QAbstractItemView#PremiumComboBoxView QScrollBar::add-line:vertical,
        QAbstractItemView#PremiumComboBoxView QScrollBar::sub-line:vertical {{
            height: 0;
            border: none;
        }}
        
        QAbstractItemView#PremiumComboBoxView QScrollBar::add-page:vertical,
        QAbstractItemView#PremiumComboBoxView QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        """
        
        self.setStyleSheet(style_sheet)
    
    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """事件过滤器 - 捕获 hover 和 focus"""
        if obj == self:
            if event.type() == QtCore.QEvent.Enter:
                self._is_hovered = True
                self.update()
            elif event.type() == QtCore.QEvent.Leave:
                self._is_hovered = False
                self.update()
            elif event.type() == QtCore.QEvent.FocusIn:
                self._is_focused = True
                self.update()
            elif event.type() == QtCore.QEvent.FocusOut:
                self._is_focused = False
                self.update()
        
        return super().eventFilter(obj, event)
    
    def showPopup(self):
        """显示下拉列表时添加动画"""
        super().showPopup()
        
        # 获取弹出视图
        popup = self.view().parentWidget()
        if popup:
            # 添加淡入动画
            effect = QtWidgets.QGraphicsOpacityEffect(popup)
            popup.setGraphicsEffect(effect)
            
            anim = QtCore.QPropertyAnimation(effect, b"opacity")
            anim.setDuration(150)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
            
            # 保存动画引用避免被垃圾回收
            popup._fade_anim = anim


class PremiumItemDelegate(QtWidgets.QStyledItemDelegate):
    """自定义项目代理 - 实现更精致的列表项渲染"""
    
    def __init__(self, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._current_theme: Dict[str, str] = {}
    
    def set_theme(self, theme: Dict[str, str]):
        """设置主题"""
        self._current_theme = theme
    
    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, 
              index: QtCore.QModelIndex):
        """自定义绘制 - 添加图标、徽章等"""
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # 使用默认绘制
        super().paint(painter, option, index)
        
        # 如果是选中项，绘制一个小指示器
        if option.state & QtWidgets.QStyle.State_Selected:
            accent = self._current_theme.get('accent', '#007acc')
            indicator_color = QtGui.QColor(accent)
            
            # 绘制左侧指示条
            indicator_rect = QtCore.QRect(
                option.rect.left() + 4,
                option.rect.top() + option.rect.height() // 2 - 8,
                3,
                16
            )
            painter.setBrush(indicator_color)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRoundedRect(indicator_rect, 1.5, 1.5)
        
        painter.restore()
    
    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, 
                 index: QtCore.QModelIndex) -> QtCore.QSize:
        """返回项目的建议尺寸"""
        size = super().sizeHint(option, index)
        # 确保足够的高度以提供舒适的点击区域
        size.setHeight(max(size.height(), 36))
        return size


def upgrade_combobox_to_premium(combobox: QtWidgets.QComboBox, 
                                 theme: Optional[Dict[str, str]] = None) -> PremiumComboBox:
    """将普通 QComboBox 升级为 PremiumComboBox
    
    Args:
        combobox: 要升级的 QComboBox
        theme: 主题字典
        
    Returns:
        新的 PremiumComboBox 实例
    """
    # 创建新的 PremiumComboBox
    premium = PremiumComboBox(combobox.parent())
    
    # 复制属性
    premium.setObjectName(combobox.objectName())
    premium.setEditable(combobox.isEditable())
    premium.setMinimumHeight(combobox.minimumHeight())
    
    # 复制所有项目
    for i in range(combobox.count()):
        premium.addItem(combobox.itemText(i), combobox.itemData(i))
    
    # 设置当前项
    premium.setCurrentIndex(combobox.currentIndex())
    
    # 应用主题
    if theme:
        premium.set_theme(theme)
    
    # 复制布局位置
    if combobox.parent() and combobox.parent().layout():
        layout = combobox.parent().layout()
        index = layout.indexOf(combobox)
        if index >= 0:
            # 替换原有组件
            layout.removeWidget(combobox)
            layout.insertWidget(index, premium)
            combobox.deleteLater()
    
    return premium

