# QuickBar v2

桌面通用快速启动栏 — pywebview + Vue 3 毛玻璃前端

支持 Windows / Linux / macOS，覆盖 7 种快捷方式：游戏、应用、文件、文件夹、代码项目、网址、命令。

## 快速开始

```bash
# 装依赖
pip install pywebview

# 跑
python main.py
```

OCR 功能可选：

```bash
pip install mss pillow numpy rapidocr-onnxruntime
```

## 特性

- 侧边栏分类导航 + 拖拽换类
- Vue 3 响应式 UI + CSS 毛玻璃 + GPU 加速动画
- 键盘导航：↑↓ Enter Delete Ctrl+N
- 内置 Claude 终端启动 + 一键关浏览器
- 屏幕 OCR 识别并复制
- 配置原子写入防损坏
- 开机自启（设置里勾）

## 项目结构

```
main.py          # 入口，pywebview 窗口
api.py           # HTTP REST API + OCR + 书签 + 自启
config.py        # 配置模型 + 原子写入
launcher.py      # 启动器（打开文件/URL/命令/Claude）
static/
  index.html     # Vue 3 SPA 前端
items.example.json
```

## 配置

首次运行自动生成 `items.json`。格式与 v1 兼容，直接复用。

## License

MIT
