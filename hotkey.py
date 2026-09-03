"""
Windows 全局热键管理（纯 Win32 API，不依赖 Qt）
创建隐藏消息窗口接收 WM_HOTKEY，在独立线程运行消息循环
"""
import ctypes
from ctypes import wintypes
import threading

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

# 64 位 Windows 上 LRESULT/WPARAM/LPARAM 都是 64 位
LRESULT = ctypes.c_ssize_t

# WNDPROC 类型
WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)

# 定义 DefWindowProcW 的参数和返回类型
user32.DefWindowProcW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
user32.DefWindowProcW.restype = LRESULT


# 自定义 WNDCLASSW 结构体（ctypes.wintypes 未提供）
class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", ctypes.c_void_p),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class HotkeyManager:
    """全局热键注册与监听"""

    def __init__(self):
        self._hwnd = None
        self._thread = None
        self._running = False
        self._wnd_proc_ref = None  # 防止被 GC
        self.callback = None
        self._hotkey_id = None
        self._modifiers = None
        self._vk = None

    def _window_proc(self, hwnd, msg, wparam, lparam):
        """窗口过程：处理 WM_HOTKEY"""
        if msg == WM_HOTKEY and wparam == self._hotkey_id:
            if self.callback:
                self.callback()
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _message_loop(self):
        """后台线程：创建隐藏窗口 + 消息循环"""
        # 注册窗口类
        self._wnd_proc_ref = WNDPROC(self._window_proc)
        hinstance = kernel32.GetModuleHandleW(None)

        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wnd_proc_ref
        wc.lpszClassName = "AdTokHotkeyMsgWindow"
        wc.hInstance = hinstance

        atom = user32.RegisterClassW(ctypes.byref(wc))

        # 创建隐藏窗口
        self._hwnd = user32.CreateWindowExW(
            0, atom, "AdTokHotkey", 0,
            0, 0, 0, 0, None, None, hinstance, None
        )

        # 注册热键
        user32.RegisterHotKey(self._hwnd, self._hotkey_id, self._modifiers, self._vk)

        # 消息循环
        msg = wintypes.MSG()
        while self._running:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0:  # WM_QUIT
                break
            if ret == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def register(self, hotkey_id: int, modifiers: int, vk: int, callback) -> bool:
        """
        注册全局热键
        :param hotkey_id: 热键标识 ID
        :param modifiers: 修饰键 (如 MOD_CONTROL=0x0002)
        :param vk: 虚拟键码 (如 VK_M=0x4D)
        :param callback: 热键触发时的回调函数
        :return: 是否注册成功
        """
        if self._running:
            self.unregister()

        self._hotkey_id = hotkey_id
        self._modifiers = modifiers
        self._vk = vk
        self.callback = callback
        self._running = True

        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()
        return True

    def unregister(self):
        """注销热键"""
        self._running = False
        if self._hwnd:
            user32.UnregisterHotKey(self._hwnd, self._hotkey_id)
            user32.PostMessageW(self._hwnd, WM_QUIT, 0, 0)
            self._hwnd = None
        self._hotkey_id = None
        self.callback = None

    def cleanup(self):
        """清理资源（程序退出时调用）"""
        self.unregister()
