"""
启动画面组件
提供美观的启动加载界面，改善用户体验
"""

from PySide6 import QtCore, QtGui, QtWidgets


class SplashScreen(QtWidgets.QSplashScreen):
    """启动画面"""
    
    def __init__(self):
        super().__init__()
        
        # 创建启动画面图像
        pixmap = QtGui.QPixmap(500, 300)
        pixmap.fill(QtGui.QColor("#1e1e1e"))  # 深色背景
        
        # 绘制内容
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # 绘制应用名称
        font = QtGui.QFont("Microsoft YaHei", 28, QtGui.QFont.Bold)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#ffffff"))
        painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, "字见润新")
        
        # 绘制版本信息
        font_small = QtGui.QFont("Microsoft YaHei", 10)
        painter.setFont(font_small)
        painter.setPen(QtGui.QColor("#888888"))
        version_rect = QtCore.QRect(0, pixmap.height() - 60, pixmap.width(), 30)
        painter.drawText(version_rect, QtCore.Qt.AlignCenter, "Version 1.3")
        
        # 绘制加载提示
        loading_rect = QtCore.QRect(0, pixmap.height() - 35, pixmap.width(), 30)
        painter.drawText(loading_rect, QtCore.Qt.AlignCenter, "正在加载...")
        
        painter.end()
        
        self.setPixmap(pixmap)
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
        
        # 设置消息显示位置和样式
        self.setStyleSheet("""
            QSplashScreen {
                border: 2px solid #333333;
                border-radius: 10px;
            }
        """)
    
    def showMessage(self, message: str):
        """显示加载消息"""
        super().showMessage(
            message,
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignHCenter,
            QtGui.QColor("#00aaff")
        )
        QtWidgets.QApplication.processEvents()  # 立即刷新显示


class ModernSplashScreen(QtWidgets.QWidget):
    """现代化启动画面（带进度条）"""
    
    def __init__(self):
        super().__init__()
        
        # 设置窗口属性
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint | 
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        # 设置固定大小
        self.setFixedSize(500, 300)
        
        # 居中显示
        self._center_on_screen()
        
        # 创建UI
        self._setup_ui()
        
    def _center_on_screen(self):
        """在屏幕中央显示"""
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
    
    def _setup_ui(self):
        """设置UI"""
        # 主布局
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 内容容器（用于背景和圆角）
        container = QtWidgets.QFrame()
        container.setObjectName("SplashContainer")
        container.setStyleSheet("""
            #SplashContainer {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e,
                    stop:1 #16213e
                );
                border-radius: 15px;
                border: 2px solid #0f3460;
            }
        """)
        
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(40, 40, 40, 40)
        container_layout.setSpacing(20)
        
        # Logo/图标区域（可以替换为实际logo）
        icon_label = QtWidgets.QLabel("✨")
        icon_label.setAlignment(QtCore.Qt.AlignCenter)
        icon_label.setStyleSheet("""
            font-size: 48px;
            color: #00d4ff;
        """)
        container_layout.addWidget(icon_label)
        
        # 应用名称
        title_label = QtWidgets.QLabel("字见润新")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 32px;
            font-weight: bold;
            color: #ffffff;
            font-family: 'Microsoft YaHei';
        """)
        container_layout.addWidget(title_label)
        
        # 版本信息
        version_label = QtWidgets.QLabel("Version 1.3")
        version_label.setAlignment(QtCore.Qt.AlignCenter)
        version_label.setStyleSheet("""
            font-size: 12px;
            color: #888888;
        """)
        container_layout.addWidget(version_label)
        
        # 间隔
        container_layout.addStretch()
        
        # 状态标签
        self.status_label = QtWidgets.QLabel("正在初始化...")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            font-size: 14px;
            color: #aaaaaa;
            padding: 5px;
        """)
        container_layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1a1a2e;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00d4ff,
                    stop:1 #00aaff
                );
                border-radius: 2px;
            }
        """)
        container_layout.addWidget(self.progress_bar)
        
        layout.addWidget(container)
    
    def update_progress(self, value: int, message: str = ""):
        """更新进度
        
        Args:
            value: 进度值（0-100）
            message: 状态消息
        """
        self.progress_bar.setValue(value)
        if message:
            self.status_label.setText(message)
        QtWidgets.QApplication.processEvents()
    
    def set_message(self, message: str):
        """设置状态消息"""
        self.status_label.setText(message)
        QtWidgets.QApplication.processEvents()
    
    def paintEvent(self, event):
        """绘制半透明背景"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # 绘制阴影效果
        shadow_rect = self.rect().adjusted(5, 5, -5, -5)
        painter.setBrush(QtGui.QColor(0, 0, 0, 100))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(shadow_rect, 15, 15)


