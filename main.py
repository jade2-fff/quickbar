# main.py — QuickBar v2 入口（pywebview 前端 + Python 后端）
from __future__ import annotations

import signal
import sys

from api import start_server
from config import Config


def main():
    # 加载配置和启动 API 服务器
    config = Config.load()
    server, port = start_server(0)
    url = f"http://127.0.0.1:{port}"

    print(f"QuickBar v2 — http://127.0.0.1:{port}")

    try:
        import webview
    except ImportError:
        print("请安装 pywebview: pip install pywebview")
        print(f"手动打开浏览器: {url}")
        try:
            signal.pause()
        except KeyboardInterrupt:
            pass
        finally:
            server.shutdown()
        return

    # 创建无边框透明窗口
    window = webview.create_window(
        title="QuickBar",
        url=url,
        width=440,
        height=720,
        frameless=True,
        transparent=True,
        always_on_top=True,
        on_top=True,
    )

    # 启动 pywebview（阻塞直到窗口关闭）
    webview.start(debug=False)

    # 退出时保存
    config.save()
    server.shutdown()


if __name__ == "__main__":
    main()
