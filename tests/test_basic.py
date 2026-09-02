"""
基础单元测试
覆盖：配置管理、热键管理器、窗口创建冒烟测试
"""
import os
import sys

import pytest

# 把项目根目录加入 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect

from config import (
    AppConfig, DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_URL,
    HOTKEY_ID, HOTKEY_MOD, HOTKEY_VK, WINDOW_ASPECT_RATIO,
)


@pytest.fixture(scope="session")
def qapp():
    """测试用 QApplication 单例"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


# ============ 配置管理测试 ============

class TestAppConfig:

    def test_default_url_is_douyin(self):
        config = AppConfig()
        assert "douyin.com" in config.current_url

    def test_default_geometry_size(self):
        config = AppConfig()
        geom = config.window_geometry
        assert geom.width() == DEFAULT_WIDTH
        assert geom.height() == DEFAULT_HEIGHT

    def test_always_on_top_is_bool(self):
        config = AppConfig()
        assert isinstance(config.always_on_top, bool)

    def test_set_and_get_url(self):
        config = AppConfig()
        original = config.current_url
        test_url = "https://www.bilibili.com"
        config.current_url = test_url
        assert config.current_url == test_url
        # 还原
        config.current_url = original

    def test_set_and_get_geometry(self):
        config = AppConfig()
        original = config.window_geometry
        test_rect = QRect(100, 200, 400, 700)
        config.window_geometry = test_rect
        saved = config.window_geometry
        assert saved.x() == 100
        assert saved.y() == 200
        assert saved.width() == 400
        assert saved.height() == 700
        # 还原
        config.window_geometry = original


# ============ 热键管理测试 ============

class TestHotkeyManager:

    def test_create_and_cleanup(self, qapp):
        from hotkey import HotkeyManager
        manager = HotkeyManager()
        assert manager is not None
        assert manager.callback is None
        manager.cleanup()

    def test_register_unregister(self, qapp):
        from hotkey import HotkeyManager
        manager = HotkeyManager()
        called = []

        def on_hotkey():
            called.append(True)

        success = manager.register(HOTKEY_ID, HOTKEY_MOD, HOTKEY_VK, on_hotkey)
        # 热键可能被占用，但创建/注销流程不应崩溃
        if success:
            assert manager.callback is not None
        manager.unregister()
        assert manager.callback is None
        manager.cleanup()


# ============ 窗口冒烟测试 ============

class TestPopupWindow:

    def test_window_creates_without_error(self, qapp):
        """窗口能正常创建并设置基本属性"""
        from popup_window import PopupWindow
        config = AppConfig()
        window = PopupWindow(config)

        # 基本属性验证
        assert window.minimumWidth() == 480
        assert window.minimumHeight() == 300
        # 默认大小由屏幕动态计算，保持 16:10 比例（误差 <= 1px）
        ratio = window.width() / window.height()
        assert abs(ratio - WINDOW_ASPECT_RATIO) < 0.02

        # 标题栏存在
        assert window.title_bar is not None
        assert window.title_bar.title_label.text() == "热门推荐"

        # WebView 存在且已加载 URL
        assert window.web_view is not None
        assert "douyin.com" in window.web_view.url().toString()

        window.close()

    def test_toggle_visibility(self, qapp):
        """切换显示/隐藏功能正常"""
        from popup_window import PopupWindow
        config = AppConfig()
        window = PopupWindow(config)
        window.show()
        assert window.isVisible() is True

        window.toggle_visibility()
        assert window.isVisible() is False

        window.toggle_visibility()
        assert window.isVisible() is True

        window.close()
