<!-- SPDX-License-Identifier: GPL-3.0-or-later OR CC-BY-NC-SA-4.0 -->

# paim (paintImproved) — Qt 6 版

**paim (paintImproved)** 是一个用 **Python + PyQt6 (Qt 6)** 实现的 Linux 轻量绘图应用。
它保留了经典画图软件的顺手交互，同时按 Linux 桌面习惯做了改进（例如 F11 为整个应用全屏、自动跟随系统深浅色主题）。

本仓库是原 GTK4 + Cairo 版本的 **Qt 6 移植版**：界面、画布、选区、文本、图标和文件读写全部改用 Qt 的
`QWidget` / `QPainter` / `QImage` 实现，不再依赖 GTK、PyGObject、Cairo 或 Pango。

浅色模式：

![paim 浅色模式](docs/screenshot.png)

深色模式（跟随系统主题）：

![paim 深色模式](docs/screenshot-dark.png)

## 运行

系统需要 Python 3 和 Qt 6 运行库；Python 依赖为 PyQt6（界面与绘制）和 Pillow（GIF/WebP 透明保存、
低位深 BMP 等少数格式兼容）。Arch Linux 上安装 Qt/X11 运行库：

```bash
sudo pacman -S --needed python python-pip qt6-base
```

克隆并安装：

```bash
git clone https://github.com/myLiLingyun/paim-qt.git
cd paim
./install.sh
```

`install.sh` 会：

- 如果系统 Python 已经能 `import PyQt6, PIL`，直接使用系统解释器，不额外下载依赖；
- 否则在项目目录创建 `.venv`，从 `requirements.txt` 安装 PyQt6 和 Pillow；
- 把启动器链接到 `~/.local/bin/paim`，并安装图标和桌面入口；桌面入口写入绝对 `Exec` 路径，因此不依赖图形会话的 `PATH`。

pip 默认使用阿里云 PyPI 镜像。如需换源，安装时设置 `PAIM_PIP_INDEX_URL`（或 `PIP_INDEX_URL`），例如：

```bash
PAIM_PIP_INDEX_URL=https://pypi.org/simple ./install.sh
```

如果希望在终端里直接运行，可把 `~/.local/bin` 加入 `PATH`，然后执行：

```bash
paim
```

界面语言跟随系统 locale（`LANGUAGE` / `LC_ALL` / `LC_MESSAGES` / `LANG`）。调试或强制语言时可设置 `PAIM_LANG=zh` 或 `PAIM_LANG=en`。

主题和快速访问工具栏配置保存在 `~/.config/paim/settings.json`，最近文件列表保存在
`~/.local/share/mspaint-linux/recent.json`（与原版保持兼容）。

也可以不安装，直接使用系统 Python 运行：

```bash
python3 -m mspaint
# 或使用项目自带的启动器
./paim
```

## 功能

- **工具**：铅笔、9 种刷子、用颜色填充、文本、橡皮擦、颜色选取器、放大镜
- **形状**：直线、曲线、椭圆、矩形、圆角矩形、三角形、直角三角形、菱形、五边形、六边形、四个方向箭头、四/五/六角星、三种标注、心形、闪电形
- **形状样式**：轮廓样式、填充样式、线宽
- **选区**：矩形/自由图形选择、移动、八向手柄缩放、透明选择、全选、反向选择、删除、裁剪
- **剪贴板**：剪切、复制、粘贴、粘贴来源、跨应用 PNG 剪贴板
- **图像**：旋转/翻转（整图或选区）、调整大小和倾斜、反色、属性、清除图像
- **透明图片**：棋盘格显示透明区域；编辑时保留 Alpha 通道；可在属性中启用透明背景，橡皮擦和删除会清除为透明，移动选区不会留下白色；PNG、GIF、WebP 保存保留透明度
- **文本**：字体、字号、粗体、斜体、下划线、不透明/透明背景
- **颜色**：20 色经典调色板、颜色 1/颜色 2、完整颜色选择器
- **文件**：新建、打开、保存、另存为、最近文件
- **拖放**：从文件管理器把图片拖到 paim 窗口即可打开，带拖放高亮提示
- **快速访问工具栏**：右键功能区命令可添加到工具栏，也可从下拉菜单自定义并持久保存
- **双语界面**：根据系统语言自动使用中文或英文
- **格式**：PNG、JPEG、BMP（1/4/8/24 位）、GIF、WebP、TIFF、DIB，以及 Qt/Pillow 支持的其他图片
- **打印**：打印、打印预览、页面设置（Qt PrintSupport）
- **视图**：10%–800% 缩放、标尺、网格线、缩略图、全屏、状态栏
- **主题**：应用内可选“跟随系统 / 浅色 / 深色”，选择持久保存；透明像素使用棋盘格显示
- **桌面集成**：设为桌面背景、邮件发送、最近文件列表
- **编辑**：50 步撤消/重做、快捷键

## 快捷键

| 快捷键 | 功能 |
| --- | --- |
| `Ctrl+N/O/S` | 新建 / 打开 / 保存 |
| `F12` | 另存为 |
| `Ctrl+Z/Y` | 撤消 / 重做 |
| `Ctrl+X/C/V` | 剪切 / 复制 / 粘贴 |
| `Ctrl+A` | 全选 |
| `Ctrl+W` | 调整大小和倾斜 |
| `Ctrl+E` | 属性 |
| `Ctrl+Shift+X` | 裁剪 |
| `Ctrl+Shift+I` | 反色 |
| `Ctrl+Shift+N` | 清除图像 |
| `Ctrl+PgUp/PgDn` | 放大 / 缩小 |
| `F11` | 整个应用全屏 |
| `F1` | 帮助 |
| `Delete` / `Backspace` | 删除选定内容并用颜色 2 填充 |
| `Esc` | 取消选区/文字编辑 |

## 测试

测试默认使用 Qt 的 `offscreen` 平台，可在无显示器的环境直接运行；也可以在前面加 `xvfb-run -a`。
在项目根目录执行：

```bash
python3 tools/test_core.py        # 文档、笔刷、形状、格式读写
python3 tools/smoke_test.py       # 主窗口、保存、删除、缩放、主题、对话框
python3 tools/test_interactions.py # 鼠标绘制、选区移动、文本、取色、橡皮擦
python3 tools/test_dialogs.py     # 各对话框的取值与回调
python3 tools/test_features.py    # 快捷键、调色板、剪贴板、偏好持久化
python3 tools/test_transparency.py # Alpha 通道、透明选区、PNG/GIF 透明保存
python3 tools/test_i18n.py        # 中英文界面选择
python3 tools/test_drop.py        # 文件拖放打开
python3 tools/test_text_clip.py   # 文本工具与图片剪贴板
```

## 代码结构

```
mspaint/
├── app.py          # 主窗口、功能区、文件/打印/剪贴板、桌面集成
├── document.py     # QImage 画布、选区、撤消历史、图片读写
├── view.py         # 画布交互、工具状态、选区手柄、文字覆盖层
├── raster.py       # 笔刷、填充、形状渲染（QPainter）
├── shapes.py       # 所有形状的 QPainterPath 几何
├── text.py         # QFont/QPainter 文本渲染
├── icons.py        # QPainter 绘制的图标
├── dialogs.py      # 调整大小、属性、颜色、保存选项、页面设置等对话框
└── i18n.py         # 中英文界面字符串
```

## 许可证

- **程序代码**：GNU GPL v3 或更高版本（`GPL-3.0-or-later`），见 [LICENSE](LICENSE)。
- **文档、截图与图标**：双许可，`GPL-3.0-or-later` 或 `CC-BY-NC-SA-4.0` 二选一，见 [LICENSING.md](LICENSING.md) 和 [LICENSE-CC-BY-NC-SA-4.0](LICENSE-CC-BY-NC-SA-4.0)。

Copyright (C) 2026 paim contributors.
