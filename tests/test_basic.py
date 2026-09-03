"""
基础单元测试（方案A：pywebview 版本，无 Qt 依赖）
覆盖：配置管理、窗口几何、热键管理器、屏幕计算
"""
import os
import sys
import json
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    AppConfig, WindowGeometry, DEFAULT_URL, DEFAULT_ALWAYS_ON_TOP,
    WINDOW_ASPECT_RATIO, CONFIG_VERSION,
)
from hotkey import HotkeyManager
from main import calc_default_window, get_screen_workarea


# ============ WindowGeometry 测试 ============

class TestWindowGeometry:

    def test_default_is_invalid(self):
        geom = WindowGeometry()
        assert not geom.isValid()

    def test_valid_geometry(self):
        geom = WindowGeometry(100, 200, 800, 600)
        assert geom.isValid()
        assert geom.x == 100
        assert geom.y == 200
        assert geom.width == 800
        assert geom.height == 600

    def test_to_dict_and_back(self):
        geom = WindowGeometry(10, 20, 300, 400)
        d = geom.to_dict()
        geom2 = WindowGeometry.from_dict(d)
        assert geom2.x == 10
        assert geom2.y == 20
        assert geom2.width == 300
        assert geom2.height == 400

    def test_from_dict_missing_keys(self):
        geom = WindowGeometry.from_dict({})
        assert geom.x == 0
        assert geom.y == 0
        assert geom.width == 0
        assert geom.height == 0
        assert not geom.isValid()


# ============ 配置管理测试 ============

class TestAppConfig:

    def test_default_url(self):
        config = AppConfig()
        assert "douyin.com" in config.current_url

    def test_default_geometry_is_invalid(self):
        config = AppConfig()
        config._data.pop("window_geometry", None)
        geom = config.window_geometry
        assert not geom.isValid()

    def test_always_on_top_is_bool(self):
        config = AppConfig()
        assert isinstance(config.always_on_top, bool)

    def test_set_and_get_url(self):
        config = AppConfig()
        original = config.current_url
        test_url = "https://www.bilibili.com"
        config.current_url = test_url
        assert config.current_url == test_url
        config.current_url = original

    def test_set_and_get_geometry(self):
        config = AppConfig()
        test_geom = WindowGeometry(100, 200, 600, 400)
        config.window_geometry = test_geom
        saved = config.window_geometry
        assert saved.x == 100
        assert saved.y == 200
        assert saved.width == 600
        assert saved.height == 400

    def test_config_version_is_latest(self):
        config = AppConfig()
        assert config._data.get("config_version") == CONFIG_VERSION

    def test_config_persists_to_file(self):
        config = AppConfig()
        assert os.path.exists(config.config_file)
        with open(config.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "config_version" in data


# ============ 热键管理测试 ============

class TestHotkeyManager:

    def test_create_and_cleanup(self):
        manager = HotkeyManager()
        assert manager is not None
        assert manager.callback is None
        manager.cleanup()

    def test_register_and_unregister(self):
        manager = HotkeyManager()
        called = []

        def on_hotkey():
            called.append(True)

        manager.register(1, 0x0002, 0x4D, on_hotkey)
        assert manager.callback is not None
        assert manager._hotkey_id == 1
        # 等待消息循环线程启动
        import time
        time.sleep(0.2)
        assert manager._hwnd is not None

        manager.unregister()
        assert manager.callback is None
        assert manager._hotkey_id is None
        manager.cleanup()


# ============ 屏幕计算测试 ============

class TestScreenCalc:

    def test_get_workarea_returns_positive(self):
        x, y, w, h = get_screen_workarea()
        assert w > 0
        assert h > 0
        assert x >= 0
        assert y >= 0

    def test_calc_default_window_returns_reasonable_size(self):
        x, y, w, h = calc_default_window()
        assert w >= 480
        assert h >= 300
        # 比例接近 16:10
        ratio = w / h
        assert abs(ratio - WINDOW_ASPECT_RATIO) < 0.05
        # 位置在屏幕范围内
        screen_x, screen_y, screen_w, screen_h = get_screen_workarea()
        assert x >= screen_x
        assert y >= screen_y
        assert x + w <= screen_x + screen_w + 20  # 允许少量边缘溢出
