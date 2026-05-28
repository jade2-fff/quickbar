#!/usr/bin/env python3
"""屏幕 OCR 覆盖层
全局热键 / 侧边栏按钮触发 → 截屏 → RapidOCR 后台识别 →
全屏冻结画面 → 鼠标拖选 OCR 文字框 → 结果复制到剪贴板，
单击网址 / 邮箱框 → 直接用默认浏览器打开。
"""

from __future__ import annotations

import re
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox

IS_WINDOWS = sys.platform.startswith("win")

URL_RE = re.compile(
    r"(?:https?://|ftp://|www\.)[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def check_deps() -> list[str]:
    """返回缺失的依赖列表，空列表表示就绪。"""
    missing: list[str] = []
    try:
        import mss  # noqa: F401
    except Exception:
        missing.append("mss")
    try:
        from PIL import Image, ImageTk  # noqa: F401
    except Exception:
        missing.append("pillow")
    try:
        import numpy  # noqa: F401
    except Exception:
        missing.append("numpy")
    try:
        from rapidocr_onnxruntime import RapidOCR  # noqa: F401
    except Exception:
        missing.append("rapidocr-onnxruntime")
    return missing


_ocr_engine = None


def _get_ocr():
    """惰性加载 RapidOCR 引擎（首次约 1-2 秒）"""
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


class OCROverlay:
    """全屏冻结遮罩 + OCR 文字框选 + URL 直跳浏览器"""

    BOX_OUTLINE = "#89b4fa"
    BOX_URL     = "#94e2d5"
    BOX_HOVER   = "#cba6f7"
    BOX_SEL     = "#f9e2af"
    SEL_RECT    = "#cba6f7"
    HINT_FG     = "#c8d0f0"

    def __init__(self, parent: tk.Tk, font_family: str = "TkDefaultFont"):
        self.parent = parent
        self.font_family = font_family
        self.win: tk.Toplevel | None = None
        self.canvas: tk.Canvas | None = None
        self.image_tk = None
        self.boxes: list[dict] = []
        self.drag_start: tuple[int, int] | None = None
        self.drag_rect_id: int | None = None
        self.status_id: int | None = None
        self.scale: float = 1.0  # 物理像素 → Tk 逻辑像素 缩放比

    # ────────────────────────────── 入口 ──────────────────────────────
    def show(self):
        """主入口：检查依赖 → 隐藏宿主窗口 → 截屏 → 显示遮罩"""
        if self.win is not None:
            return  # 已打开

        missing = check_deps()
        if missing:
            messagebox.showerror(
                "缺少 OCR 依赖",
                "屏幕文字识别功能需要安装以下 Python 包：\n\n"
                f"    pip install {' '.join(missing)}\n\n"
                "安装后无需重启 QuickBar，再次点击「文字识别」即可使用。",
            )
            return

        # 临时隐藏 QuickBar 自身，避免被截进画面
        try:
            self.parent.withdraw()
        except Exception:
            pass
        # withdraw 不是同步的，留一帧让窗口管理器消化
        self.parent.update_idletasks()
        self.parent.after(120, self._capture_and_show)

    def _capture_and_show(self):
        try:
            import mss
            from PIL import Image
        except Exception as e:
            self._restore_parent()
            messagebox.showerror("OCR 失败", f"导入依赖失败: {e}")
            return

        try:
            with mss.mss() as sct:
                mon = sct.monitors[1]  # 主显示器
                shot = sct.grab(mon)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        except Exception as e:
            self._restore_parent()
            messagebox.showerror("截屏失败", str(e))
            return

        self._build_window(img)
        # 后台跑 OCR，避免阻塞 UI
        threading.Thread(
            target=self._run_ocr, args=(img,), daemon=True
        ).start()

    # ────────────────────────────── UI ──────────────────────────────
    def _build_window(self, img):
        from PIL import Image, ImageTk

        sw_log = self.parent.winfo_screenwidth()
        sh_log = self.parent.winfo_screenheight()
        # 物理像素 → Tk 逻辑像素的缩放比（处理 Windows 高 DPI 场景）
        self.scale = sw_log / img.width if img.width else 1.0
        if abs(self.scale - 1.0) > 0.001:
            display_img = img.resize((sw_log, sh_log), Image.LANCZOS)
        else:
            display_img = img

        self.win = tk.Toplevel(self.parent)
        self.win.attributes("-fullscreen", True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="black")
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        self.image_tk = ImageTk.PhotoImage(display_img)
        self.canvas = tk.Canvas(
            self.win, highlightthickness=0, bg="black", cursor="cross"
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self.image_tk, anchor="nw")
        # 半透明黑色遮罩，让识别框更显眼
        self.canvas.create_rectangle(
            0, 0, sw_log, sh_log,
            fill="black", stipple="gray25", outline="",
        )

        self.status_id = self.canvas.create_text(
            sw_log // 2, 30,
            text="正在识别屏幕文字...   Esc 退出",
            fill=self.HINT_FG, font=(self.font_family, 14, "bold"),
        )

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_motion)
        self.win.bind("<Escape>", lambda e: self.close())
        self.win.bind("<Key-q>", lambda e: self.close())
        self.win.bind("<Button-3>", lambda e: self.close())  # 右键退出
        self.win.focus_force()

    # ────────────────────────────── OCR 后台线程 ──────────────────────────────
    def _run_ocr(self, img):
        try:
            import numpy as np
            arr = np.array(img)            # RGB
            arr = arr[:, :, ::-1].copy()   # → BGR (RapidOCR 期望)
            engine = _get_ocr()
            result, _ = engine(arr)
            boxes: list[dict] = []
            if result:
                for entry in result:
                    pts, text, score = entry[0], entry[1], entry[2]
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    bbox = (min(xs), min(ys), max(xs), max(ys))
                    boxes.append({
                        "bbox": bbox,
                        "text": text,
                        "score": score,
                    })
            self.parent.after(0, self._render_boxes, boxes)
        except Exception as e:
            err = str(e)
            self.parent.after(0, lambda: self._fail(err))

    def _fail(self, err: str):
        messagebox.showerror("OCR 失败", err)
        self.close()

    def _render_boxes(self, boxes: list[dict]):
        if self.canvas is None:
            return
        if self.status_id is not None:
            self.canvas.delete(self.status_id)
            self.status_id = None
        s = self.scale
        for b in boxes:
            x1, y1, x2, y2 = b["bbox"]
            sx1, sy1, sx2, sy2 = x1 * s, y1 * s, x2 * s, y2 * s
            b["sbbox"] = (sx1, sy1, sx2, sy2)
            text = b["text"]
            is_url = bool(URL_RE.search(text)) or bool(EMAIL_RE.search(text))
            color = self.BOX_URL if is_url else self.BOX_OUTLINE
            rid = self.canvas.create_rectangle(
                sx1, sy1, sx2, sy2,
                outline=color, width=1, fill="",
            )
            b["id"] = rid
            b["is_url"] = is_url
        self.boxes = boxes
        self.canvas.create_text(
            10, 10, anchor="nw",
            text=f"已识别 {len(boxes)} 段  ·  拖选复制 / 单击网址打开 / "
                 f"Esc 或右键退出",
            fill=self.HINT_FG, font=(self.font_family, 10),
        )

    # ────────────────────────────── 鼠标交互 ──────────────────────────────
    def _on_press(self, e):
        self.drag_start = (e.x, e.y)
        if self.drag_rect_id is not None:
            self.canvas.delete(self.drag_rect_id)
        self.drag_rect_id = self.canvas.create_rectangle(
            e.x, e.y, e.x, e.y,
            outline=self.SEL_RECT, width=2,
            fill=self.SEL_RECT, stipple="gray25",
        )
        # 重置高亮
        for b in self.boxes:
            color = self.BOX_URL if b.get("is_url") else self.BOX_OUTLINE
            self.canvas.itemconfig(b["id"], outline=color, width=1)

    def _on_drag(self, e):
        if self.drag_start is None or self.drag_rect_id is None:
            return
        x0, y0 = self.drag_start
        self.canvas.coords(self.drag_rect_id, x0, y0, e.x, e.y)
        rx1, ry1 = min(x0, e.x), min(y0, e.y)
        rx2, ry2 = max(x0, e.x), max(y0, e.y)
        for b in self.boxes:
            x1, y1, x2, y2 = b["sbbox"]
            hit = x1 < rx2 and x2 > rx1 and y1 < ry2 and y2 > ry1
            if hit:
                self.canvas.itemconfig(b["id"], outline=self.BOX_SEL, width=2)
            else:
                color = self.BOX_URL if b["is_url"] else self.BOX_OUTLINE
                self.canvas.itemconfig(b["id"], outline=color, width=1)

    def _on_release(self, e):
        if self.drag_start is None:
            return
        x0, y0 = self.drag_start
        moved = abs(e.x - x0) + abs(e.y - y0)
        self.drag_start = None
        if self.drag_rect_id is not None:
            self.canvas.delete(self.drag_rect_id)
            self.drag_rect_id = None

        # 单击：命中网址框就打开浏览器；命中普通框就复制；都没命中则忽略
        if moved < 5:
            for b in self.boxes:
                x1, y1, x2, y2 = b["sbbox"]
                if x1 <= e.x <= x2 and y1 <= e.y <= y2:
                    if b["is_url"]:
                        self._open_url(b["text"])
                    else:
                        self._copy(b["text"])
                    self.close()
                    return
            return

        # 拖选：收集落在选区内的文字框，按行序拼接复制
        rx1, ry1 = min(x0, e.x), min(y0, e.y)
        rx2, ry2 = max(x0, e.x), max(y0, e.y)
        chosen = []
        for b in self.boxes:
            x1, y1, x2, y2 = b["sbbox"]
            if x1 < rx2 and x2 > rx1 and y1 < ry2 and y2 > ry1:
                chosen.append(b)
        chosen.sort(key=lambda b: (b["sbbox"][1], b["sbbox"][0]))
        if chosen:
            text = "\n".join(b["text"] for b in chosen)
            self._copy(text)
        self.close()

    def _on_motion(self, e):
        if self.drag_start is not None:
            return
        for b in self.boxes:
            x1, y1, x2, y2 = b["sbbox"]
            inside = x1 <= e.x <= x2 and y1 <= e.y <= y2
            if inside and b["is_url"]:
                self.canvas.itemconfig(b["id"], outline=self.BOX_HOVER, width=2)
            else:
                color = self.BOX_URL if b["is_url"] else self.BOX_OUTLINE
                self.canvas.itemconfig(b["id"], outline=color, width=1)

    # ────────────────────────────── 副作用 ──────────────────────────────
    def _open_url(self, text: str):
        m = URL_RE.search(text)
        if m:
            url = m.group(0).rstrip(".,;:)]}>'\"")
            if url.lower().startswith("www."):
                url = "http://" + url
            webbrowser.open(url)
            return
        m = EMAIL_RE.search(text)
        if m:
            webbrowser.open("mailto:" + m.group(0))

    def _copy(self, text: str):
        try:
            self.parent.clipboard_clear()
            self.parent.clipboard_append(text)
            self.parent.update()
        except Exception:
            pass

    # ────────────────────────────── 关闭 ──────────────────────────────
    def _restore_parent(self):
        try:
            self.parent.deiconify()
        except Exception:
            pass

    def close(self):
        if self.win is not None:
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win = None
        self.canvas = None
        self.boxes = []
        self.image_tk = None
        self.drag_start = None
        self.drag_rect_id = None
        self.status_id = None
        self._restore_parent()
