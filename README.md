# QuickBar

桌面通用快速启动栏。吸附屏幕边缘，鼠标靠近时丝滑滑出，QQ 风格。

支持 Windows / Linux / macOS，覆盖 7 种快捷方式：游戏、应用、文件、文件夹、代码项目、网址、命令。

## 特性

- 吸附屏幕任一边缘（左/右/顶/底），鼠标移到边缘自动滑出
- 分类侧边栏，拖拽卡片可在分类间移动
- 内置 Claude 终端启动 + 一键关闭浏览器
- 添加网址时可从 Chrome / Edge / Brave 收藏夹直接选取
- **屏幕文字识别（OCR）**：全局热键随时唤起，鼠标拖选复制，识别到的网址 / 邮箱单击直跳浏览器
- 键盘导航：`↑↓` 选择 · `Enter` 启动 · `Delete` 删除 · `Esc` 收起
- 全局热键 `Alt+\`` 切换显示
- 配置自动保存（每 30 秒 + 退出时 + 原子写入防损坏）
- 可选开机自启（Windows: `.lnk` / Linux: XDG `.desktop` / macOS: LaunchAgent plist）
- 运行时自动选择 CJK / Emoji 字体（Noto Sans CJK / PingFang / 微软雅黑等）

## 运行

需要 Python 3.10+（用了 `str | None` 联合类型语法）。核心功能仅依赖标准库。

**Windows**
```cmd
python game_bar.py
```
或双击 `run.bat`（带控制台）/ `run_silent.vbs`（静默后台）。

**Linux / macOS**
```bash
python3 game_bar.py
# 或
chmod +x run.sh && ./run.sh
```

### 创建桌面快捷方式

跨平台一键安装，运行后会在桌面创建 QuickBar 图标，双击即可启动：

```bash
# Windows
python install.py

# Linux / macOS
python3 install.py
```

- Windows: 在桌面生成 `QuickBar.lnk`，用 `pythonw.exe` 启动（无控制台黑窗）
- Linux: 在桌面和 `~/.local/share/applications/` 各放一份 `.desktop`，应用菜单里也能找到
- macOS: 在桌面生成 `QuickBar.command`

> 想开机自启？打开 QuickBar，点 ⚙ 设置 → 勾选「开机自启」。

Linux 桌面环境需要 X11 + 一个支持 `_NET_WM_STATE_ABOVE` 的窗口管理器（GNOME / KDE / XFCE 等都支持）。Wayland 下 Tk 通过 XWayland 兼容运行。

可选依赖：
- 一键关闭浏览器：Linux/macOS 需要 `pkill`
- Claude 终端启动：Linux 需要 `gnome-terminal` / `konsole` / `xfce4-terminal` / `alacritty` / `kitty` / `xterm` 之一
- CJK 显示：建议安装 `fonts-noto-cjk` / `wqy-microhei` 等中文字体包

## 屏幕文字识别（OCR）

需要安装可选依赖：
```bash
pip install mss pillow numpy rapidocr-onnxruntime keyboard
```

| 依赖 | 用途 | 缺失后果 |
| --- | --- | --- |
| `mss` | 跨平台截屏 | 功能不可用 |
| `pillow` | 图像缩放 / 显示 | 功能不可用 |
| `numpy` | 把 PIL 图像传给 OCR 引擎 | 功能不可用 |
| `rapidocr-onnxruntime` | OCR 推理（首次会下载约 50 MB 模型） | 功能不可用 |
| `keyboard` | OS 级全局热键，任意窗口都能呼出 | 仍可用，但仅当 QuickBar 有焦点时热键有效；可点侧边栏 🔍 按钮 |

未装依赖也不影响主程序，首次点击「文字识别」按钮才会提示并给出安装命令。

**使用方式**
1. 点侧边栏的 🔍「文字识别」按钮，或按 `Ctrl+Shift+Space`（可在设置里改）
2. 屏幕被冻结成半透明遮罩，后台开始 OCR（首次约 1–2 秒加载模型）
3. 屏幕上每段识别到的文字会出现一个识别框：
   - **拖选** 多个框 → 文字按行序拼接复制到剪贴板
   - **单击** 普通文字框 → 复制单段文字
   - **单击** 高亮（青色）的网址 / 邮箱框 → 直接用默认浏览器打开
   - `Esc` 或鼠标右键退出

> Linux 提示：`keyboard` 库注册全局热键需要 root 权限。若不想 sudo，可改用侧边栏按钮，或在系统设置里把自定义快捷键绑定到 `python3 /path/to/game_bar.py --ocr`（暂未提供 CLI 入口，可自行扩展）。

## 配置

首次运行会在脚本同目录生成 `items.json`。可参考 `items.example.json` 手动编辑，或直接通过 UI 的 `+` 按钮添加。

字段含义：

| 字段 | 说明 |
| --- | --- |
| `position` | 吸附位置：`right` / `left` / `top` / `bottom` |
| `hide_delay_ms` | 鼠标离开后多少毫秒收起 |
| `opacity` | 整体透明度，0.35 ~ 1.0 |
| `editor` | 打开 project 类型时使用的编辑器命令（默认 `code`） |
| `ocr_hotkey` | OCR 全局热键，留空禁用全局热键。格式见 [keyboard 文档](https://github.com/boppreh/keyboard#api) |
| `items[].type` | `game` / `app` / `file` / `folder` / `project` / `url` / `command` |

## License

MIT


