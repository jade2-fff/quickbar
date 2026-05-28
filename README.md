# QuickBar

桌面通用快速启动栏。吸附屏幕边缘，鼠标靠近时丝滑滑出，QQ 风格。

支持 Windows / Linux / macOS，覆盖 7 种快捷方式：游戏、应用、文件、文件夹、代码项目、网址、命令。

## 特性

- 吸附屏幕任一边缘（左/右/顶/底），鼠标移到边缘自动滑出
- 分类侧边栏，拖拽卡片可在分类间移动
- 内置 Claude 终端启动 + 一键关闭浏览器
- 添加网址时可从 Chrome / Edge / Brave 收藏夹直接选取
- 键盘导航：`↑↓` 选择 · `Enter` 启动 · `Delete` 删除 · `Esc` 收起
- 全局热键 `Alt+\`` 切换显示
- 配置自动保存（每 30 秒 + 退出时 + 原子写入防损坏）
- 可选开机自启（Windows: `.lnk` / Linux: XDG `.desktop` / macOS: LaunchAgent plist）
- 运行时自动选择 CJK / Emoji 字体（Noto Sans CJK / PingFang / 微软雅黑等）

## 运行

需要 Python 3.10+（用了 `str | None` 联合类型语法）。仅依赖标准库，无需安装第三方包。

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

Linux 桌面环境需要 X11 + 一个支持 `_NET_WM_STATE_ABOVE` 的窗口管理器（GNOME / KDE / XFCE 等都支持）。Wayland 下 Tk 通过 XWayland 兼容运行。

可选依赖：
- 一键关闭浏览器：Linux/macOS 需要 `pkill`
- Claude 终端启动：Linux 需要 `gnome-terminal` / `konsole` / `xfce4-terminal` / `alacritty` / `kitty` / `xterm` 之一
- CJK 显示：建议安装 `fonts-noto-cjk` / `wqy-microhei` 等中文字体包

## 配置

首次运行会在脚本同目录生成 `items.json`。可参考 `items.example.json` 手动编辑，或直接通过 UI 的 `+` 按钮添加。

字段含义：

| 字段 | 说明 |
| --- | --- |
| `position` | 吸附位置：`right` / `left` / `top` / `bottom` |
| `hide_delay_ms` | 鼠标离开后多少毫秒收起 |
| `opacity` | 整体透明度，0.35 ~ 1.0 |
| `editor` | 打开 project 类型时使用的编辑器命令（默认 `code`） |
| `items[].type` | `game` / `app` / `file` / `folder` / `project` / `url` / `command` |

## License

MIT

