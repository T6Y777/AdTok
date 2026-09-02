"""
应用配置管理
使用 QSettings 持久化窗口位置、大小等用户偏好
"""
from PySide6.QtCore import QSettings, QRect

ORG_NAME = "AdTok"
APP_NAME = "AdTokPopup"

# 配置版本：窗口大小逻辑变更时递增，旧版本自动重置窗口几何
CONFIG_VERSION = 3

# ===== 默认配置 =====
# 窗口比例保持 16:10（原 1280x800 的比例）
WINDOW_ASPECT_RATIO = 1280 / 800  # = 1.6
# 窗口面积占屏幕可用面积的比例（1/9 即长宽各约 1/3）
WINDOW_AREA_RATIO = 1 / 9
DEFAULT_MARGIN = 10          # 距屏幕边缘像素
DEFAULT_URL = "https://www.douyin.com"
DEFAULT_ALWAYS_ON_TOP = True

# fallback 默认尺寸（配置无效时使用，实际默认大小由屏幕动态计算）
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 800

# ===== 全局热键配置 =====
HOTKEY_ID = 1
HOTKEY_MOD = 0x0002          # MOD_CONTROL (Ctrl)
HOTKEY_VK = 0x4D             # VK_M (M 键)
HOTKEY_DESC = "Ctrl + M"     # 给用户看的热键描述


class AppConfig:
    """基于 QSettings 的持久化配置"""

    def __init__(self):
        self.settings = QSettings(ORG_NAME, APP_NAME)
        # 配置版本不匹配时重置窗口几何（适配默认大小逻辑变更）
        if self.settings.value("config_version", 0, type=int) != CONFIG_VERSION:
            self.settings.remove("window_geometry")
            self.settings.setValue("config_version", CONFIG_VERSION)

    # ---- 窗口几何 ----
    @property
    def window_geometry(self) -> QRect:
        """返回保存的窗口位置大小；没有保存时返回无效矩形（触发默认计算）"""
        saved = self.settings.value("window_geometry")
        if isinstance(saved, QRect) and saved.isValid():
            return saved
        return QRect()  # 无效矩形，表示无保存配置

    @window_geometry.setter
    def window_geometry(self, rect: QRect):
        self.settings.setValue("window_geometry", rect)

    # ---- 置顶 ----
    @property
    def always_on_top(self) -> bool:
        return self.settings.value("always_on_top", DEFAULT_ALWAYS_ON_TOP, type=bool)

    @always_on_top.setter
    def always_on_top(self, value: bool):
        self.settings.setValue("always_on_top", value)

    # ---- 当前网址 ----
    @property
    def current_url(self) -> str:
        return self.settings.value("current_url", DEFAULT_URL, type=str)

    @current_url.setter
    def current_url(self, url: str):
        self.settings.setValue("current_url", url)
