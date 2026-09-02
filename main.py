"""
AdTok 入口文件
运行方式：python main.py
"""
import sys

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from config import AppConfig, HOTKEY_ID, HOTKEY_MOD, HOTKEY_VK, HOTKEY_DESC
from popup_window import PopupWindow
from hotkey import HotkeyManager


def create_tray(app: QApplication, window: PopupWindow) -> QSystemTrayIcon:
    """创建系统托盘图标和菜单"""
    icon = app.style().standardIcon(QStyle.SP_ComputerIcon)
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip(f"AdTok  老板键: {HOTKEY_DESC}")

    menu = QMenu()

    show_action = QAction("显示 / 隐藏", app)
    show_action.triggered.connect(window.toggle_visibility)
    menu.addAction(show_action)

    menu.addSeparator()

    quit_action = QAction("退出", app)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    # 左键单击托盘图标也切换显示
    tray.activated.connect(
        lambda reason: window.toggle_visibility()
        if reason == QSystemTrayIcon.Trigger
        else None
    )
    tray.show()
    return tray


def main():
    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("AdTok")
    app.setQuitOnLastWindowClosed(False)  # 关窗口不退出，保留托盘

    config = AppConfig()
    window = PopupWindow(config)
    window.show()

    # 系统托盘
    create_tray(app, window)

    # 全局热键（老板键）
    hotkey = HotkeyManager()
    hotkey.register(HOTKEY_ID, HOTKEY_MOD, HOTKEY_VK, window.toggle_visibility)

    # 退出时保存状态 + 清理热键
    def on_quit():
        config.window_geometry = window.geometry()
        config.current_url = window.web_view.url().toString()
        hotkey.cleanup()

    app.aboutToQuit.connect(on_quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
