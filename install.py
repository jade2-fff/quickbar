#!/usr/bin/env python3
"""QuickBar 桌面快捷方式安装器
Windows  → 桌面 QuickBar.lnk（用 pythonw 启动，无黑窗口）
Linux    → 桌面 QuickBar.desktop + ~/.local/share/applications/quickbar.desktop
macOS    → 桌面 QuickBar.command
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
SCRIPT = BASE / "game_bar.py"

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
IS_LIN = sys.platform.startswith("linux")


def install_windows() -> Path:
    # pythonw.exe 没有控制台黑窗；找不到就退回 python.exe
    pyw = Path(sys.executable).with_name("pythonw.exe")
    if not pyw.exists():
        pyw = Path(sys.executable)

    # 让 PowerShell 自己解析真实桌面路径，能正确处理 OneDrive 重定向、本地化目录名
    ps = f"""
$ErrorActionPreference = 'Stop'
$desktop = [Environment]::GetFolderPath('Desktop')
$target  = Join-Path $desktop 'QuickBar.lnk'
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($target)
$sc.TargetPath       = '{pyw}'
$sc.Arguments        = '"{SCRIPT}"'
$sc.WorkingDirectory = '{BASE}'
$sc.IconLocation     = 'shell32.dll,14'
$sc.Description      = 'QuickBar - 桌面快速启动栏'
$sc.Save()
Write-Output $target
""".strip()

    with tempfile.NamedTemporaryFile(suffix=".ps1", delete=False,
                                     mode="w", encoding="utf-8") as f:
        f.write(ps)
        tmp = f.name
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", tmp],
            capture_output=True, text=True,
        )
    finally:
        os.unlink(tmp)

    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return Path(r.stdout.strip().splitlines()[-1])


def install_linux() -> Path:
    desktop = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    target = desktop / "QuickBar.desktop"

    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=QuickBar\n"
        "Comment=桌面快速启动栏\n"
        f"Exec={sys.executable} {SCRIPT}\n"
        f"Path={BASE}\n"
        "Icon=applications-utilities\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        "StartupNotify=false\n"
    )
    target.write_text(content, encoding="utf-8")
    target.chmod(0o755)

    # 同步一份到应用菜单
    apps = Path.home() / ".local" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    (apps / "quickbar.desktop").write_text(content, encoding="utf-8")

    # GNOME 旧版用 metadata::trusted 标记可信任；新版被弃用但调用无害
    try:
        subprocess.run(
            ["gio", "set", str(target), "metadata::trusted", "true"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass
    return target


def install_macos() -> Path:
    desktop = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    target = desktop / "QuickBar.command"
    target.write_text(
        "#!/usr/bin/env bash\n"
        f'cd "{BASE}"\n'
        f'exec "{sys.executable}" "{SCRIPT}"\n',
        encoding="utf-8",
    )
    target.chmod(0o755)
    return target


def main() -> int:
    print("QuickBar 桌面快捷方式安装器")
    print(f"  Python: {sys.executable}")
    print(f"  脚本  : {SCRIPT}")

    if not SCRIPT.exists():
        print(f"找不到 game_bar.py，请在仓库根目录运行此脚本（当前: {BASE}）")
        return 1

    try:
        if IS_WIN:
            target = install_windows()
        elif IS_MAC:
            target = install_macos()
        elif IS_LIN:
            target = install_linux()
        else:
            print(f"不支持的平台: {sys.platform}")
            return 1
    except Exception as e:
        print(f"安装失败: {e}")
        return 1

    print(f"已创建: {target}")
    if IS_LIN:
        print("提示: GNOME 首次双击可能要求「允许启动」，右键 → 允许启动 即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
