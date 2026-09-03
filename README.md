# AdTok

把抖音 / B 站网页版伪装成右下角广告弹窗的摸鱼神器。

## 技术栈

- **pywebview + WebView2**（Edge Chromium 内核，完整支持 H.264 视频解码）
- **pystray**（系统托盘）
- **纯 Win32 API**（全局热键，无第三方依赖）
- Python 3.13

## 功能

- 右下角弹窗样式，标题栏显示"热门推荐"，外观酷似广告弹窗
- WebView2 内核加载抖音网页版，支持登录、视频播放（H.264 硬解）
- 全局老板键 `Ctrl + M` 一键显示/隐藏
- 关闭/最小化都隐藏到系统托盘，不退出程序
- 标题栏可拖拽移动窗口
- 窗口位置和大小自动记忆
- 登录状态持久化保存

## 快速开始

### 1. 安装依赖（首次运行）

```bat
.venv\Scripts\pip install -r requirements.txt
```

### 2. 启动

双击 `run.bat`，或命令行执行：

```bat
.venv\Scripts\python main.py
```

> **注意**：Windows 10 可能需要安装 [WebView2 运行时](https://developer.microsoft.com/microsoft-edge/webview2/)，Windows 11 自带。

## 使用说明

| 操作 | 效果 |
|------|------|
| `Ctrl + M` | 显示 / 隐藏弹窗 |
| 左键单击托盘图标 | 显示 / 隐藏弹窗 |
| 右键托盘图标 | 菜单（显示/隐藏、退出） |
| 拖拽标题栏 | 移动窗口 |
| 点击 ✕ / — | 隐藏到托盘 |

## 切换到 B 站

在弹窗内的浏览器地址栏输入 `https://www.bilibili.com` 即可（后续版本会加平台切换按钮）。

## 项目结构

```
AdTok/
├── main.py           # 程序入口（pywebview 窗口 + 托盘 + 热键）
├── config.py         # 配置管理（JSON 持久化）
├── hotkey.py         # Windows 全局热键（纯 Win32 API）
├── requirements.txt  # 依赖
├── run.bat           # 双击启动脚本
└── tests/            # 单元测试
```

## 默认窗口大小

窗口面积为屏幕可用面积的 1/9，保持 16:10 比例，默认出现在屏幕右下角。
最小尺寸 480×300。
