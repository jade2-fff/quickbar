# launcher.py — 启动器（打开文件/URL/命令，关闭浏览器，启动 Claude）
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import webbrowser

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
POPEN_NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WINDOWS else {}


def open_path(path: str):
    """系统默认程序打开文件/文件夹"""
    if IS_WINDOWS:
        os.startfile(path)
    elif IS_MACOS:
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def launch_item(itype: str, path: str, editor: str = "code") -> str:
    """启动一项快捷方式，返回状态消息"""
    if not path:
        raise ValueError("未设置路径")
    try:
        if itype in ("game", "app", "file", "folder"):
            open_path(path)
        elif itype == "project":
            subprocess.Popen([editor, path])
        elif itype == "url":
            webbrowser.open(path if "://" in path else f"https://{path}")
        elif itype == "command":
            subprocess.Popen(path, shell=True)
        else:
            open_path(path)
        return "ok"
    except Exception as e:
        return str(e)[:120]


def launch_claude() -> str:
    """终端中启动 Claude"""
    try:
        if IS_WINDOWS:
            subprocess.Popen('start "Claude" cmd /k claude', shell=True, **POPEN_NO_WINDOW)
        elif IS_MACOS:
            subprocess.Popen(["osascript", "-e", 'tell app "Terminal" to do script "claude"'])
        else:
            cmd = "claude; exec bash"
            for term, args in (
                ("gnome-terminal", ["--", "bash", "-lic", cmd]),
                ("konsole", ["-e", "bash", "-lic", cmd]),
                ("xfce4-terminal", ["-e", f"bash -lic '{cmd}'"]),
                ("alacritty", ["-e", "bash", "-lic", cmd]),
                ("kitty", ["bash", "-lic", cmd]),
                ("xterm", ["-e", f"bash -lic '{cmd}'"]),
            ):
                if shutil.which(term):
                    subprocess.Popen([term, *args])
                    return "ok"
            return "未找到终端模拟器"
        return "ok"
    except Exception as e:
        return str(e)[:120]


def close_browsers() -> str:
    """关闭所有浏览器窗口"""
    try:
        if IS_WINDOWS:
            names = ["chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe"]
            cmd = ["taskkill", "/f"] + [a for n in names for a in ("/im", n)]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **POPEN_NO_WINDOW)
        else:
            for n in ("chrome", "chromium", "msedge", "firefox", "opera", "brave"):
                subprocess.Popen(["pkill", "-f", n], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "ok"
    except Exception as e:
        return str(e)[:120]
