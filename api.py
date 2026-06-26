# api.py — HTTP 后端路由（配合 pywebview）
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

from config import Config, ITEM_TYPES
from launcher import launch_item, launch_claude, close_browsers

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


class APIHandler(BaseHTTPRequestHandler):
    config: Config = Config.load()

    def log_message(self, format, *args):
        pass  # 静默 HTTP 日志

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        # 静态文件
        if path == "/" or path == "":
            path = "/index.html"
        static_file = STATIC_DIR / path.lstrip("/")
        if static_file.is_file() and ".py" not in path:
            self._serve_file(static_file)
            return

        # API 路由
        routes = {
            "/api/config": self._get_config,
            "/api/items": self._get_items,
            "/api/item-types": self._get_item_types,
            "/api/bookmarks": self._get_bookmarks,
            "/api/autostart": self._get_autostart,
        }
        handler = routes.get(path)
        if handler:
            handler()
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        routes = {
            "/api/launch": lambda: self._launch(body),
            "/api/claude": lambda: self._launch_claude(),
            "/api/close-browsers": lambda: self._close_browsers(),
            "/api/items": lambda: self._add_item(body),
            "/api/ocr": self._do_ocr,
            "/api/autostart": lambda: self._toggle_autostart(body),
        }
        handler = routes.get(path)
        if handler:
            handler()
        else:
            self._send_json({"error": "not found"}, 404)

    def do_PUT(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if path == "/api/config":
            self._update_config(body)
        elif path.startswith("/api/items/"):
            parts = path.split("/")
            if len(parts) >= 4:
                idx = int(parts[3])
                if parts[-1] == "move":
                    self._move_item(idx, body.get("direction", 0))
                else:
                    self._edit_item(idx, body)
        else:
            self._send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path.startswith("/api/items/"):
            idx = int(path.split("/")[-1])
            self._delete_item(idx)
        else:
            self._send_json({"error": "not found"}, 404)

    # ── 静态文件 ──
    def _serve_file(self, path: Path):
        content = path.read_bytes()
        mime = {
            ".html": "text/html", ".css": "text/css", ".js": "application/javascript",
            ".png": "image/png", ".svg": "image/svg+xml", ".json": "application/json",
        }.get(path.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", f"{mime}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    # ── GET ──
    def _get_config(self):
        self._send_json(APIHandler.config.to_dict())

    def _get_item_types(self):
        self._send_json(ITEM_TYPES)

    def _get_items(self):
        self._send_json(APIHandler.config.items)

    def _get_bookmarks(self):
        bookmarks = _load_browser_bookmarks()
        self._send_json(bookmarks)

    def _get_autostart(self):
        self._send_json({"enabled": _autostart_check()})

    # ── POST ──
    def _launch(self, body: dict):
        itype = body.get("type", "command")
        path = body.get("path", "")
        try:
            result = launch_item(itype, path, APIHandler.config.editor)
            self._send_json({"ok": True, "msg": result})
        except ValueError as e:
            self._send_json({"ok": False, "msg": str(e)})

    def _launch_claude(self):
        result = launch_claude()
        self._send_json({"ok": result == "ok", "msg": result})

    def _close_browsers(self):
        result = close_browsers()
        self._send_json({"ok": result == "ok", "msg": result})

    def _add_item(self, body: dict):
        itype = body.get("type", "command")
        name = body.get("name", "").strip()
        path = body.get("path", "").strip()
        if not name:
            self._send_json({"ok": False, "msg": "名称不能为空"}, 400)
            return
        APIHandler.config.items.append({"type": itype, "name": name, "path": path})
        APIHandler.config.save()
        self._send_json({"ok": True, "idx": len(APIHandler.config.items) - 1})

    def _do_ocr(self):
        """屏幕 OCR — 阻塞式，返回识别结果"""
        try:
            results = _run_ocr()
            self._send_json({"ok": True, "results": results})
        except Exception as e:
            self._send_json({"ok": False, "msg": str(e)})

    # ── PUT ──
    def _update_config(self, body: dict):
        cfg = APIHandler.config
        for key in ("position", "editor", "opacity", "ocr_hotkey"):
            if key in body:
                setattr(cfg, key, body[key])
        cfg.save()
        self._send_json({"ok": True})

    def _edit_item(self, idx: int, body: dict):
        if idx < 0 or idx >= len(APIHandler.config.items):
            self._send_json({"ok": False, "msg": "索引越界"}, 404)
            return
        item = APIHandler.config.items[idx]
        if "name" in body:
            item["name"] = body["name"]
        if "path" in body:
            item["path"] = body["path"]
        if "type" in body:
            item["type"] = body["type"]
        APIHandler.config.save()
        self._send_json({"ok": True})

    def _move_item(self, idx: int, direction: int):
        if idx < 0 or idx >= len(APIHandler.config.items):
            self._send_json({"ok": False, "msg": "索引越界"}, 404)
            return
        n = idx + direction
        if 0 <= n < len(APIHandler.config.items):
            items = APIHandler.config.items
            items[idx], items[n] = items[n], items[idx]
            APIHandler.config.save()
            self._send_json({"ok": True})
        else:
            self._send_json({"ok": False, "msg": "不能移动"})

    # ── DELETE ──
    def _delete_item(self, idx: int):
        if idx < 0 or idx >= len(APIHandler.config.items):
            self._send_json({"ok": False, "msg": "索引越界"}, 404)
            return
        APIHandler.config.items.pop(idx)
        APIHandler.config.save()
        self._send_json({"ok": True})

    # ── 自启 ──
    def _toggle_autostart(self, body: dict):
        enable = body.get("enable", False)
        try:
            _autostart_toggle(enable)
            self._send_json({"ok": True, "enabled": enable})
        except Exception as e:
            self._send_json({"ok": False, "msg": str(e)})


# ═════════════════════════════════════
# 浏览器书签
# ═════════════════════════════════════
def _load_browser_bookmarks() -> list[dict]:
    bookmarks = []
    home = Path.home()

    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA", "")
        browsers = [
            Path(local) / "Google/Chrome/User Data/Default/Bookmarks",
            Path(local) / "Microsoft/Edge/User Data/Default/Bookmarks",
        ]
    elif IS_MACOS:
        browsers = [
            home / "Library/Application Support/Google/Chrome/Default/Bookmarks",
            home / "Library/Application Support/Microsoft Edge/Default/Bookmarks",
        ]
    else:
        browsers = [
            home / ".config/google-chrome/Default/Bookmarks",
            home / ".config/chromium/Default/Bookmarks",
            home / ".config/microsoft-edge/Default/Bookmarks",
            home / ".config/BraveSoftware/Brave-Browser/Default/Bookmarks",
        ]

    def walk(node, result):
        if node.get("type") == "url":
            result.append({"name": node.get("name", ""), "url": node.get("url", "")})
        for child in node.get("children", []):
            walk(child, result)

    for p in browsers:
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for key in ("bookmark_bar", "other"):
                root = data.get("roots", {}).get(key, {})
                walk(root, bookmarks)
        except Exception:
            pass
    return bookmarks


# ═════════════════════════════════════
# 开机自启
# ═════════════════════════════════════
def _autostart_path() -> Path:
    if IS_WINDOWS:
        return Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup/QuickBar.lnk"
    if IS_MACOS:
        return Path.home() / "Library/LaunchAgents/com.quickbar.plist"
    return Path.home() / ".config/autostart/quickbar.desktop"


def _autostart_check() -> bool:
    return _autostart_path().exists()


def _autostart_toggle(enable: bool):
    sp = _autostart_path()
    if not enable:
        if sp.exists():
            sp.unlink()
        return

    sp.parent.mkdir(parents=True, exist_ok=True)
    script = BASE_DIR / "main.py"

    if IS_WINDOWS:
        import tempfile
        ps = f"""
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("{sp}")
$sc.TargetPath = "{sys.executable}"
$sc.Arguments = '"{script}"'
$sc.WorkingDirectory = "{BASE_DIR}"
$sc.Save()
""".strip()
        t = tempfile.NamedTemporaryFile(suffix=".ps1", delete=False, mode="w", encoding="utf-8")
        t.write(ps)
        t.close()
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", t.name], capture_output=True)
        os.unlink(t.name)
    elif IS_MACOS:
        pl = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.quickbar</string>
  <key>ProgramArguments</key>
  <array><string>{sys.executable}</string><string>{script}</string></array>
  <key>WorkingDirectory</key><string>{BASE_DIR}</string>
  <key>RunAtLoad</key><true/>
</dict></plist>"""
        sp.write_text(pl, encoding="utf-8")
    else:
        desktop = (
            "[Desktop Entry]\nType=Application\nName=QuickBar\n"
            f"Exec={sys.executable} {script}\nPath={BASE_DIR}\n"
            "X-GNOME-Autostart-enabled=true\nTerminal=false\n"
        )
        sp.write_text(desktop, encoding="utf-8")
        sp.chmod(0o755)


# ═════════════════════════════════════
# OCR 引擎（惰性加载）
# ═════════════════════════════════════
_ocr_engine = None

def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


def _check_ocr_deps() -> str | None:
    """返回缺失的第一个依赖名，就绪返回 None"""
    for mod in ("mss", "PIL", "numpy", "rapidocr_onnxruntime"):
        try:
            __import__(mod)
        except ImportError:
            return mod
    return None


def _run_ocr() -> list[dict]:
    """全屏 OCR，返回识别结果列表"""
    missing = _check_ocr_deps()
    if missing:
        raise RuntimeError(f"缺少依赖: pip install mss pillow numpy rapidocr-onnxruntime")

    import mss
    import numpy as np
    from PIL import Image

    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])
    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    arr = np.array(img)[:, :, ::-1].copy()  # RGB → BGR

    engine = _get_ocr_engine()
    result, _ = engine(arr)

    boxes = []
    if result:
        for entry in result:
            pts, text, score = entry[0], entry[1], entry[2]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            boxes.append({
                "bbox": [min(xs), min(ys), max(xs), max(ys)],
                "text": text,
                "score": float(score),
            })
    return boxes


# ═════════════════════════════════════
# 服务器启动
# ═════════════════════════════════════
def start_server(port: int = 0) -> tuple[HTTPServer, int]:
    """启动 API 服务器，返回 (server, actual_port)"""
    server = HTTPServer(("127.0.0.1", port), APIHandler)
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, actual_port
