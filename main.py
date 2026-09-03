"""
AdTok 入口文件（方案A：pywebview + WebView2）
- 无边框窗口，注入广告弹窗风格标题栏
- WebView2 内核，完整支持 H.264 视频解码
- 全局热键 Ctrl+M 显示/隐藏
- 系统托盘
"""
import json
import os
import sys
import threading
import ctypes
from ctypes import wintypes
import math

import webview
import pystray
from pystray import MenuItem as Item, Menu
from PIL import Image, ImageDraw

from config import (
    AppConfig, DEFAULT_URL, DEFAULT_MARGIN,
    WINDOW_ASPECT_RATIO, WINDOW_AREA_RATIO,
    HOTKEY_ID, HOTKEY_MOD, HOTKEY_VK, HOTKEY_DESC,
    WindowGeometry,
)
from hotkey import HotkeyManager


# ============ 屏幕工具 ============

def get_screen_workarea():
    """获取屏幕工作区（去掉任务栏）：返回 (x, y, width, height)"""
    user32 = ctypes.windll.user32
    rc = wintypes.RECT()
    # SPI_GETWORKAREA = 0x0030
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rc), 0)
    return rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top


def calc_default_window():
    """计算默认窗口大小和右下角位置（含最小尺寸兜底）"""
    screen_x, screen_y, screen_w, screen_h = get_screen_workarea()
    target_area = screen_w * screen_h * WINDOW_AREA_RATIO
    height = int(math.sqrt(target_area / WINDOW_ASPECT_RATIO))
    width = int(height * WINDOW_ASPECT_RATIO)

    # 最小尺寸兜底，保持比例
    MIN_W, MIN_H = 480, 300
    if width < MIN_W:
        width = MIN_W
        height = int(width / WINDOW_ASPECT_RATIO)
    if height < MIN_H:
        height = MIN_H
        width = int(height * WINDOW_ASPECT_RATIO)

    x = screen_x + screen_w - width - DEFAULT_MARGIN
    y = screen_y + screen_h - height - DEFAULT_MARGIN
    return x, y, width, height


# ============ 注入的标题栏 ============

TITLEBAR_CSS = """
#adtok-titlebar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 32px;
    background: #f5f5f5;
    border-bottom: 1px solid #e0e0e0;
    z-index: 999999;
    display: flex;
    align-items: center;
    padding: 0 4px 0 12px;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    -webkit-app-region: drag;
    app-region: drag;
}
#adtok-titlebar .adtok-title {
    color: #999;
    font-size: 12px;
    flex: 1;
    user-select: none;
}
#adtok-titlebar button {
    -webkit-app-region: no-drag;
    app-region: no-drag;
    border: none;
    background: transparent;
    color: #999;
    font-size: 13px;
    width: 32px;
    height: 24px;
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
}
#adtok-titlebar button:hover {
    background: #e0e0e0;
    color: #333;
}
#adtok-titlebar button.adtok-close:hover {
    background: #e81123;
    color: white;
}
body {
    padding-top: 32px !important;
}
"""

TITLEBAR_JS = """
(function() {
    function hideWindow() {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.js_close) {
            window.pywebview.api.js_close();
        } else {
            setTimeout(hideWindow, 100);
        }
    }

    function inject() {
        if (document.getElementById('adtok-titlebar')) return;
        if (!document.body) { setTimeout(inject, 100); return; }

        var bar = document.createElement('div');
        bar.id = 'adtok-titlebar';

        var title = document.createElement('span');
        title.className = 'adtok-title';
        title.textContent = '热门推荐';

        var btnMin = document.createElement('button');
        btnMin.innerHTML = '&#8212;';
        btnMin.title = '隐藏';
        btnMin.addEventListener('click', function(e) {
            e.stopPropagation();
            e.preventDefault();
            hideWindow();
        });

        var btnClose = document.createElement('button');
        btnClose.className = 'adtok-close';
        btnClose.innerHTML = '&#10005;';
        btnClose.title = '隐藏';
        btnClose.addEventListener('click', function(e) {
            e.stopPropagation();
            e.preventDefault();
            hideWindow();
        });

        bar.appendChild(title);
        bar.appendChild(btnMin);
        bar.appendChild(btnClose);
        document.body.appendChild(bar);

        // 标题栏可拖动窗口
        bar.addEventListener('mousedown', startWindowDrag);
    }

    // ===== 窗口拖动功能 =====
    var isWinDragging = false;
    var dragStartMouseX, dragStartMouseY;
    var dragStartWinX, dragStartWinY;
    var lastMoveTime = 0;

    function startWindowDrag(e) {
        if (e.button !== 0) return;
        if (e.target.closest('button')) return;
        if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.js_get_window_position) return;
        try {
            var pos = window.pywebview.api.js_get_window_position();
            dragStartWinX = pos[0];
            dragStartWinY = pos[1];
        } catch(err) { return; }
        isWinDragging = true;
        dragStartMouseX = e.screenX;
        dragStartMouseY = e.screenY;
        e.preventDefault();
        e.stopPropagation();
    }

    function onWindowDrag(e) {
        if (!isWinDragging) return;
        var now = Date.now();
        if (now - lastMoveTime < 16) return;
        lastMoveTime = now;
        var newX = dragStartWinX + (e.screenX - dragStartMouseX);
        var newY = dragStartWinY + (e.screenY - dragStartMouseY);
        if (isNaN(newX) || isNaN(newY)) return;
        try { window.pywebview.api.js_move_window(newX, newY); } catch(err) {}
    }

    function endWindowDrag(e) {
        if (e.button === 0) isWinDragging = false;
    }

    document.addEventListener('mousemove', onWindowDrag);
    document.addEventListener('mouseup', endWindowDrag);
    document.addEventListener('mouseleave', endWindowDrag);

    inject();
})();
"""

# 中键拖动平移页面：按住鼠标中键拖动，平移整个网页内容，查看被窗口裁剪的部分
PAN_JS = """
(function() {
    if (window.__adtok_pan_enabled) return;
    window.__adtok_pan_enabled = true;

    var isDragging = false;
    var startX, startY;
    var offsetX = 0, offsetY = 0;
    var baseX = 0, baseY = 0;

    document.addEventListener('mousedown', function(e) {
        if (e.button === 1) { // 鼠标中键
            e.preventDefault();
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            baseX = offsetX;
            baseY = offsetY;
            document.body.style.cursor = 'grabbing';
            document.body.style.userSelect = 'none';
        }
    });

    document.addEventListener('mousemove', function(e) {
        if (!isDragging) return;
        offsetX = baseX + (e.clientX - startX);
        offsetY = baseY + (e.clientY - startY);
        document.body.style.transform = 'translate(' + offsetX + 'px, ' + offsetY + 'px)';
    });

    function endDrag(e) {
        if (e.button === 1 && isDragging) {
            isDragging = false;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    }
    document.addEventListener('mouseup', endDrag);
    document.addEventListener('mouseleave', endDrag);

    // 禁用中键默认的自动滚动和点击行为
    document.addEventListener('auxclick', function(e) {
        if (e.button === 1) e.preventDefault();
    });
    document.addEventListener('mousedown', function(e) {
        if (e.button === 1) e.preventDefault();
    }, true);
})();
"""


# ============ JS 暴露函数（避免 js_api 对象的递归遍历 bug） ============

_window_ref = None

def js_close():
    """JS 可调用：隐藏窗口到托盘（与老板键 Ctrl+M 相同效果）"""
    if _window_ref:
        _window_ref.hide()

def js_get_window_position():
    """JS 可调用：获取窗口当前位置 (x, y)，用于拖动"""
    if _window_ref:
        x = _window_ref.x if _window_ref.x is not None else 0
        y = _window_ref.y if _window_ref.y is not None else 0
        return (int(x), int(y))
    return (0, 0)

def js_move_window(x, y):
    """JS 可调用：移动窗口到指定位置，用于拖动"""
    if _window_ref and x is not None and y is not None:
        try:
            _window_ref.move(int(x), int(y))
        except (ValueError, TypeError):
            pass

# ============ 全局状态 ============

_window_visible = True
_tray_icon = None


def toggle_window(window):
    """切换窗口显示/隐藏（热键和托盘共用）"""
    global _window_visible
    if _window_visible:
        window.hide()
        _window_visible = False
    else:
        window.show()
        _window_visible = True


# ============ 托盘图标 ============

def create_tray_image():
    """创建托盘图标（简单的 A 字母图标）"""
    image = Image.new('RGB', (64, 64), color='#f5f5f5')
    draw = ImageDraw.Draw(image)
    draw.rectangle([14, 14, 50, 50], fill='#666666')
    draw.rectangle([18, 18, 46, 46], fill='#f5f5f5')
    draw.text((24, 22), "A", fill='#666666')
    return image


def save_config_on_exit(config, window):
    """退出时保存窗口位置和当前网址"""
    try:
        geom = WindowGeometry(
            x=window.x, y=window.y,
            width=window.width, height=window.height,
        )
        config.window_geometry = geom
    except Exception:
        pass
    try:
        url = window.get_current_url()
        if url:
            config.current_url = url
    except Exception:
        pass


# ============ 主函数 ============

def main():
    config = AppConfig()

    # 确定窗口位置和大小
    saved = config.window_geometry
    if (
        saved.isValid()
        and saved.x >= 0
        and saved.y >= 0
        and saved.width >= 480
        and saved.height >= 300
    ):
        x, y, width, height = saved.x, saved.y, saved.width, saved.height
    else:
        x, y, width, height = calc_default_window()

    # 创建无边框窗口
    window = webview.create_window(
        title='热门推荐',
        url=config.current_url,
        width=width,
        height=height,
        x=x,
        y=y,
        frameless=True,
        easy_drag=False,
        background_color='#ffffff',
        on_top=config.always_on_top,
    )
    global _window_ref
    _window_ref = window
    # 用 expose 单独暴露函数，避免 js_api 对象的递归遍历 bug
    window.expose(js_close, js_get_window_position, js_move_window)

    # 页面加载完成后注入标题栏和中键拖动平移
    def on_loaded():
        css_json = json.dumps(TITLEBAR_CSS)
        js_code = f"""
        (function() {{
            var style = document.createElement('style');
            style.textContent = {css_json};
            document.head.appendChild(style);
            {TITLEBAR_JS}
            {PAN_JS}
        }})();
        """
        window.evaluate_js(js_code)

    window.events.loaded += on_loaded

    # 全局热键
    hotkey = HotkeyManager()
    hotkey.register(HOTKEY_ID, HOTKEY_MOD, HOTKEY_VK, lambda: toggle_window(window))

    # 系统托盘
    def on_tray_show_hide(icon, item):
        toggle_window(window)

    def on_tray_quit(icon, item):
        save_config_on_exit(config, window)
        hotkey.cleanup()
        icon.stop()
        window.destroy()
        os._exit(0)

    menu = Menu(
        Item('显示 / 隐藏', on_tray_show_hide),
        Item('退出', on_tray_quit),
    )
    global _tray_icon
    _tray_icon = pystray.Icon(
        'AdTok', create_tray_image(),
        f'AdTok  老板键: {HOTKEY_DESC}', menu
    )
    threading.Thread(target=_tray_icon.run, daemon=True).start()

    # 启动（阻塞主线程）
    webview.start()


if __name__ == '__main__':
    main()
