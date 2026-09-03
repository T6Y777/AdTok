"""
应用配置管理
使用 JSON 文件持久化，不依赖 Qt
配置文件位置：%LOCALAPPDATA%\\AdTok\\config.json
"""
import json
import os

# ===== 常量 =====
ORG_NAME = "AdTok"
APP_NAME = "AdTokPopup"

# 配置版本：窗口大小逻辑变更时递增，旧版本自动重置窗口几何
CONFIG_VERSION = 10

# 窗口比例保持 16:10
WINDOW_ASPECT_RATIO = 1280 / 800  # = 1.6
# 窗口面积占屏幕可用面积的比例
WINDOW_AREA_RATIO = 1 / 5
DEFAULT_MARGIN = 0  # 窗口默认与屏幕边缘的间距，0 = 完全贴边
DEFAULT_URL = "https://www.douyin.com"
DEFAULT_ALWAYS_ON_TOP = True

# 全局热键配置
HOTKEY_ID = 1
HOTKEY_MOD = 0x0002          # MOD_CONTROL (Ctrl)
HOTKEY_VK = 0x4D             # VK_M (M 键)
HOTKEY_DESC = "Ctrl + M"

# fallback 默认尺寸
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 800


class WindowGeometry:
    """窗口几何信息（替代 QRect，移除 Qt 依赖）"""

    def __init__(self, x=0, y=0, width=0, height=0):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def isValid(self):
        return self.width > 0 and self.height > 0

    def to_dict(self):
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("x", 0), d.get("y", 0), d.get("width", 0), d.get("height", 0))

    def __repr__(self):
        return f"WindowGeometry({self.x}, {self.y}, {self.width}, {self.height})"


class AppConfig:
    """基于 JSON 文件的持久化配置"""

    def __init__(self):
        self.config_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "AdTok",
        )
        self.config_file = os.path.join(self.config_dir, "config.json")
        self._data = {}
        self._load()

        # 配置版本不匹配时重置窗口几何
        if self._data.get("config_version", 0) != CONFIG_VERSION:
            self._data.pop("window_geometry", None)
            self._data["config_version"] = CONFIG_VERSION
            self._save()

    def _load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = {}

    def _save(self):
        os.makedirs(self.config_dir, exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    # ---- 窗口几何 ----
    @property
    def window_geometry(self) -> WindowGeometry:
        geom = self._data.get("window_geometry")
        if geom:
            return WindowGeometry.from_dict(geom)
        return WindowGeometry()  # 无效矩形，表示无保存配置

    @window_geometry.setter
    def window_geometry(self, geom: WindowGeometry):
        self._data["window_geometry"] = geom.to_dict()
        self._save()

    # ---- 置顶 ----
    @property
    def always_on_top(self) -> bool:
        return self._data.get("always_on_top", DEFAULT_ALWAYS_ON_TOP)

    @always_on_top.setter
    def always_on_top(self, value: bool):
        self._data["always_on_top"] = value
        self._save()

    # ---- 当前网址 ----
    @property
    def current_url(self) -> str:
        return self._data.get("current_url", DEFAULT_URL)

    @current_url.setter
    def current_url(self, url: str):
        self._data["current_url"] = url
        self._save()
