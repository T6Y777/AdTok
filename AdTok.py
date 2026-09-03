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


# ============ 单实例锁 ============

def ensure_single_instance():
    """确保只有一个 AdTok 实例运行，返回 True 表示是第一个实例。
    多实例会导致全局热键注册冲突（RegisterHotKey 重复注册失败）。"""
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    CreateMutexW = kernel32.CreateMutexW
    CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    CreateMutexW.restype = wintypes.HANDLE

    mutex_name = "AdTok_SingleInstance_Mutex"
    mutex = CreateMutexW(None, False, mutex_name)
    last_error = ctypes.get_last_error()

    ERROR_ALREADY_EXISTS = 183
    if last_error == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(mutex)
        return False
    return True


# ============ 屏幕工具 ============

def get_screen_workarea():
    """获取屏幕工作区（去掉任务栏）：返回 (x, y, width, height)"""
    user32 = ctypes.windll.user32
    rc = wintypes.RECT()
    # SPI_GETWORKAREA = 0x0030
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rc), 0)
    return rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top


def calc_default_window():
    """计算默认窗口大小和右下角位置（16:9，默认高度190）"""
    screen_x, screen_y, screen_w, screen_h = get_screen_workarea()
    # 默认高度190，宽度按16:9计算
    height = 190
    width = int(height * WINDOW_ASPECT_RATIO)  # ≈338

    x = screen_x + screen_w - width - DEFAULT_MARGIN
    y = screen_y + screen_h - height - DEFAULT_MARGIN
    return x, y, width, height


# ============ 注入的标题栏 ============

TITLEBAR_CSS = """
/* 标题栏已移除，内容占满整个窗口 */
body {
    margin: 0 !important;
    padding: 0 !important;
}
"""

TITLEBAR_JS = """
(function() {
    // ===== 窗口拖动功能（顶部20px隐形区域） =====
    var DRAG_ZONE_HEIGHT = 20;
    var isWinDragging = false;
    var dragStartMouseX, dragStartMouseY;
    var dragStartWinX, dragStartWinY;
    var lastMoveTime = 0;

    async function startWindowDrag(e) {
        if (e.button !== 0) return;
        if (e.clientY > DRAG_ZONE_HEIGHT) return;
        // 标题栏已移除，无需排除按钮区域
        if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.js_get_window_position) return;

        try {
            var pos = await window.pywebview.api.js_get_window_position();
            dragStartWinX = pos[0];
            dragStartWinY = pos[1];
        } catch(err) { return; }

        isWinDragging = true;
        dragStartMouseX = e.screenX;
        dragStartMouseY = e.screenY;
        try { e.target.setPointerCapture(e.pointerId); } catch(err) {}
        e.preventDefault();
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
        e.preventDefault();
    }

    function endWindowDrag(e) {
        if (e.button === 0 && isWinDragging) {
            isWinDragging = false;
            try { e.target.releasePointerCapture(e.pointerId); } catch(err) {}
        }
    }

    function inject() {
        // 标题栏已移除，无需创建元素
    }

    // 全局捕获阶段监听，基于坐标判断是否在标题栏区域
    window.addEventListener('pointerdown', startWindowDrag, true);
    window.addEventListener('pointermove', onWindowDrag, true);
    window.addEventListener('pointerup', endWindowDrag, true);
    window.addEventListener('pointercancel', endWindowDrag, true);



    // ===== 页面缩放（Ctrl+滚轮 / Ctrl+加减号 / Ctrl+0） =====
    var currentZoom = window.__adtok_saved_zoom || 0.3;
    var MIN_ZOOM = 0.3;
    var MAX_ZOOM = 3.0;
    var ZOOM_STEP = 0.1;
    var VIDEO_ZOOM = 0.7;  // 视频页默认缩放比例（缩小3次）
    var lastUrl = window.location.href;
    var homeZoom = window.__adtok_saved_zoom || 0.3;  // 主页/非视频页的缩放比例

    function applyZoom(z) {
        currentZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, z));
        document.documentElement.style.zoom = currentZoom;
        try {
            if (window.pywebview && window.pywebview.api && window.pywebview.api.js_save_zoom) {
                window.pywebview.api.js_save_zoom(currentZoom);
            }
        } catch(err) {}
    }

    // 监听 URL 变化（抖音是 SPA，页面切换不刷新）
    function checkUrlChange() {
        var currentUrl = window.location.href;
        if (currentUrl !== lastUrl) {
            var wasVideoPage = lastUrl.indexOf('/video/') !== -1;
            var isVideoPage = currentUrl.indexOf('/video/') !== -1;
            lastUrl = currentUrl;

            if (isVideoPage && !wasVideoPage) {
                // 刚进入视频页：保存主页缩放，应用视频页默认缩放
                homeZoom = currentZoom;
                applyZoom(VIDEO_ZOOM);
            } else if (!isVideoPage && wasVideoPage) {
                // 刚离开视频页：恢复主页缩放
                applyZoom(homeZoom);
            }
        }
    }
    setInterval(checkUrlChange, 500);

    // Ctrl+滚轮缩放窗口大小（保持16:9比例）
    window.addEventListener('wheel', function(e) {
        if (e.ctrlKey) {
            e.preventDefault();
            var delta = e.deltaY < 0 ? 20 : -20;  // 向上滚增大，向下滚缩小
            try {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.js_resize_window) {
                    window.pywebview.api.js_resize_window(delta);
                }
            } catch(err) {}
        }
    }, { passive: false });

    // Ctrl+加号/减号/0 快捷键缩放
    window.addEventListener('keydown', function(e) {
        if (e.ctrlKey) {
            if (e.key === '=' || e.key === '+') {
                e.preventDefault();
                applyZoom(currentZoom + ZOOM_STEP);
            } else if (e.key === '-' || e.key === '_') {
                e.preventDefault();
                applyZoom(currentZoom - ZOOM_STEP);
            } else if (e.key === '0') {
                e.preventDefault();
                applyZoom(1.0);
            }
        }
    });

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
_config_ref = None

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

def js_resize_window(delta_height):
    """JS 可调用：调整窗口大小，保持16:9比例（Ctrl+滚轮）"""
    if not _window_ref:
        return
    try:
        current_h = _window_ref.height if _window_ref.height else 190
        new_h = int(current_h) + int(delta_height)
        # 最小高度100，最大高度为屏幕工作区高度的90%
        _, _, _, screen_h = get_screen_workarea()
        new_h = max(100, min(new_h, int(screen_h * 0.9)))
        new_w = int(new_h * WINDOW_ASPECT_RATIO)

        _window_ref.resize(new_w, new_h)

        # 保存到配置
        if _config_ref:
            _config_ref.window_geometry.width = new_w
            _config_ref.window_geometry.height = new_h
            _config_ref.window_geometry.x = _window_ref.x if _window_ref.x is not None else 0
            _config_ref.window_geometry.y = _window_ref.y if _window_ref.y is not None else 0
            _config_ref.save()
    except (ValueError, TypeError):
        pass

def js_save_zoom(zoom_value):
    """JS 可调用：保存页面缩放比例"""
    try:
        config_ref.zoom = float(zoom_value)
    except (ValueError, TypeError):
        pass


# ============ 全局状态 ============

_window_visible = True
_tray_icon = None


def toggle_window(window):
    """切换窗口显示/隐藏（热键和托盘共用），隐藏时自动暂停视频"""
    global _window_visible
    if _window_visible:
        # 隐藏窗口时暂停所有视频
        try:
            window.evaluate_js("document.querySelectorAll('video').forEach(function(v){v.pause();});")
        except Exception:
            pass
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
        # 确保窗口大小有效，避免保存0,0,0,0
        w = window.width if window.width and window.width > 0 else config.window_geometry.width
        h = window.height if window.height and window.height > 0 else config.window_geometry.height
        x = window.x if window.x is not None else config.window_geometry.x
        y = window.y if window.y is not None else config.window_geometry.y
        if w and w > 0 and h and h > 0:
            geom = WindowGeometry(x=x, y=y, width=w, height=h)
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
    # 单实例检测：防止多实例导致全局热键冲突
    if not ensure_single_instance():
        print("AdTok 已在运行中，请勿重复启动。")
        return
    config = AppConfig()

    # 确定窗口位置和大小
    saved = config.window_geometry
    if (
        saved.isValid()
        and saved.x >= 0
        and saved.y >= 0
        and saved.width >= 200
        and saved.height >= 113
    ):
        x, y, width, height = saved.x, saved.y, saved.width, saved.height
    else:
        x, y, width, height = calc_default_window()

    # 创建无边框窗口
    window = webview.create_window(
        title='AdTok',
        url=config.current_url,
        width=width,
        height=height,
        x=x,
        y=y,
        frameless=True,
        easy_drag=False,
        resizable=True,
        background_color='#ffffff',
        on_top=False,  # 不置顶，允许被其他窗口遮挡
    )
    global _window_ref, _config_ref
    _window_ref = window
    _config_ref = config
    # 用 expose 单独暴露函数，避免 js_api 对象的递归遍历 bug
    window.expose(js_close, js_get_window_position, js_move_window, js_save_zoom, js_resize_window)

    # 页面加载完成后注入标题栏和中键拖动平移
    def on_loaded():
        css_json = json.dumps(TITLEBAR_CSS)
        zoom_json = json.dumps(config.zoom)
        js_code = f"""
        (function() {{
            var style = document.createElement('style');
            style.textContent = {css_json};
            document.head.appendChild(style);
            // 恢复保存的缩放比例（总是应用，包括默认值）
            var savedZoom = {zoom_json};
            if (savedZoom) {{
                document.documentElement.style.zoom = savedZoom;
                // 同步 currentZoom 变量（在 TITLEBAR_JS 闭包中通过全局变量传递）
                window.__adtok_saved_zoom = savedZoom;
            }}
            {TITLEBAR_JS}
            {PAN_JS}
        }})();
        """
        window.evaluate_js(js_code)

        # 强制设置窗口大小（WebView2初始化后可能自动调整窗口大小）
        # 仅当配置中的窗口大小无效时，才强制使用默认值
        saved_geom = config.window_geometry
        if (not saved_geom.isValid() or saved_geom.width <= 0 or saved_geom.height <= 0):
            _, _, default_w, default_h = calc_default_window()
            def _force_resize():
                try:
                    window.resize(default_w, default_h)
                    # 保存到配置，避免下次再次强制resize
                    config.window_geometry = WindowGeometry(
                        x=window.x if window.x is not None else 0,
                        y=window.y if window.y is not None else 0,
                        width=default_w, height=default_h
                    )
                except Exception:
                    pass
            # 延迟1秒，确保WebView2完成所有初始化后再设置窗口大小
            threading.Timer(1.0, _force_resize).start()

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
        Menu.SEPARATOR,
        Item('退出', on_tray_quit),
    )
    global _tray_icon
    _tray_icon = pystray.Icon(
        'AdTok', create_tray_image(),
        f'AdTok  老板键: {HOTKEY_DESC}', menu
    )
    threading.Thread(target=_tray_icon.run, daemon=True).start()

    # 启动（阻塞主线程）
    webview.start(private_mode=False)


if __name__ == '__main__':
    main()
