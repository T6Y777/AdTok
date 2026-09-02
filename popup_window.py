"""
广告弹窗风格的主窗口
- 无边框、右下角定位、自定义标题栏
- 内嵌 QWebEngineView 加载抖音/B站网页版
- 标题栏可拖拽移动
- 默认大小为屏幕可用面积的 1/9，保持 16:10 比例
"""
import math

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

from config import (
    AppConfig, DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_MARGIN,
    WINDOW_ASPECT_RATIO, WINDOW_AREA_RATIO,
)


class TitleBar(QFrame):
    """自定义标题栏 —— 模拟广告弹窗的"热门推荐"样式"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setStyleSheet("""
            TitleBar {
                background-color: #f5f5f5;
                border-bottom: 1px solid #e0e0e0;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QLabel#titleLabel {
                color: #999999;
                font-size: 12px;
                padding-left: 12px;
            }
            QPushButton {
                border: none;
                background: transparent;
                color: #999999;
                font-size: 13px;
                width: 32px;
                height: 24px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                color: #333333;
            }
            QPushButton#closeBtn:hover {
                background-color: #e81123;
                color: white;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(0)

        # 左侧：广告弹窗风格标题
        self.title_label = QLabel("热门推荐")
        self.title_label.setObjectName("titleLabel")
        layout.addWidget(self.title_label)
        layout.addStretch()

        # 最小化按钮（隐藏到托盘）
        self.min_btn = QPushButton("—")
        self.min_btn.setToolTip("最小化到托盘")
        layout.addWidget(self.min_btn)

        # 关闭按钮（隐藏到托盘）
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setToolTip("关闭（隐藏到托盘）")
        layout.addWidget(self.close_btn)

        # 拖拽状态
        self._drag_offset = None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_offset = None


class PopupWindow(QWidget):
    """主弹窗窗口"""

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self._init_ui()
        self._init_web()
        self._position_window()

    def _init_ui(self):
        # 无边框 + Tool（不在任务栏显示）+ 可选置顶
        flags = Qt.FramelessWindowHint | Qt.Tool
        if self.config.always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(480, 300)
        self.resize(DEFAULT_WIDTH, DEFAULT_HEIGHT)

        # 最外层布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 圆角容器
        self.container = QFrame()
        self.container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # 标题栏
        self.title_bar = TitleBar()
        self.title_bar.close_btn.clicked.connect(self.hide)
        self.title_bar.min_btn.clicked.connect(self.hide)
        container_layout.addWidget(self.title_bar)

        # 网页区域容器
        self.web_container = QFrame()
        self.web_container.setStyleSheet(
            "QFrame { border: none; background: white; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; }"
        )
        web_layout = QVBoxLayout(self.web_container)
        web_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self.web_container)

        main_layout.addWidget(self.container)

    def _init_web(self):
        """初始化 WebEngine，使用持久化 profile 保存登录状态"""
        self.profile = QWebEngineProfile("AdTokProfile", self)
        self.profile.setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        self.web_view = QWebEngineView()
        self.page = QWebEnginePage(self.profile, self.web_view)
        self.web_view.setPage(self.page)
        self.web_view.setUrl(self.config.current_url)

        self.web_container.layout().addWidget(self.web_view)

    def _position_window(self):
        """定位窗口：有保存位置且尺寸合法就用，否则动态计算并放右下角"""
        saved = self.config.window_geometry
        if (
            saved.isValid()
            and saved.x() >= 0
            and saved.y() >= 0
            and saved.width() >= self.minimumWidth()
            and saved.height() >= self.minimumHeight()
        ):
            self.setGeometry(saved)
            return

        # 动态计算：面积为屏幕可用区域的 1/9，保持 16:10 比例
        screen = self.screen().availableGeometry()
        target_area = screen.width() * screen.height() * WINDOW_AREA_RATIO
        height = int(math.sqrt(target_area / WINDOW_ASPECT_RATIO))
        width = int(height * WINDOW_ASPECT_RATIO)

        self.resize(width, height)
        x = screen.right() - width - DEFAULT_MARGIN
        y = screen.bottom() - height - DEFAULT_MARGIN
        self.move(x, y)

    def toggle_visibility(self):
        """切换显示/隐藏（老板键用）"""
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def closeEvent(self, event):
        """关闭时保存窗口位置和当前网址"""
        self.config.window_geometry = self.geometry()
        self.config.current_url = self.web_view.url().toString()
        event.accept()
