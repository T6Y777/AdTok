"""
Windows 全局热键管理
使用 Win32 API RegisterHotKey 注册系统级热键，
通过 Qt 的 nativeEventFilter 接收 WM_HOTKEY 消息。
无需管理员权限，不依赖第三方库。
"""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

user32 = ctypes.windll.user32
WM_HOTKEY = 0x0312


class HotkeyManager(QAbstractNativeEventFilter):
    """全局热键注册与监听"""

    def __init__(self):
        super().__init__()
        self._registered = False
        self._hotkey_id = None
        self.callback = None

    def register(self, hotkey_id: int, modifiers: int, vk: int, callback) -> bool:
        """
        注册全局热键
        :param hotkey_id: 热键标识 ID
        :param modifiers: 修饰键 (如 MOD_CONTROL=0x0002)
        :param vk: 虚拟键码 (如 VK_OEM_3=0xC0 对应 `~)
        :param callback: 热键触发时的回调函数
        :return: 是否注册成功
        """
        if self._registered:
            self.unregister()

        success = user32.RegisterHotKey(None, hotkey_id, modifiers, vk)
        if success:
            self._registered = True
            self._hotkey_id = hotkey_id
            self.callback = callback
            app = QCoreApplication.instance()
            if app:
                app.installNativeEventFilter(self)
        return success

    def unregister(self):
        """注销热键"""
        if self._registered and self._hotkey_id is not None:
            user32.UnregisterHotKey(None, self._hotkey_id)
            app = QCoreApplication.instance()
            if app:
                app.removeNativeEventFilter(self)
        self._registered = False
        self._hotkey_id = None
        self.callback = None

    def nativeEventFilter(self, eventType, message):
        """Qt 原生事件过滤器，捕获 WM_HOTKEY"""
        # Windows 上可能是两种事件类型，都要匹配
        if eventType in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                    if self.callback:
                        self.callback()
                    return True, 0
            except (OSError, ValueError, TypeError):
                pass
        return False, 0

    def cleanup(self):
        """清理资源（程序退出时调用）"""
        self.unregister()
