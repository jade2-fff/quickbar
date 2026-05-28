#!/usr/bin/env python3
"""QuickBar — 桌面通用快速启动栏
QQ 风格：吸附屏幕边缘，鼠标靠近时丝滑滑出。
支持游戏、应用、文件、文件夹、代码项目、URL、命令。
"""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import json
import os
import subprocess
import sys
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CFG_FILE = os.path.join(BASE_DIR, "items.json")
OLD_CFG_FILE = os.path.join(BASE_DIR, "games.json")

ITEM_TYPES = {
    "game":    {"icon": "🎮", "color": "#f38ba8", "label": "游戏"},
    "app":     {"icon": "💻", "color": "#89b4fa", "label": "应用"},
    "file":    {"icon": "📄", "color": "#a6e3a1", "label": "文件"},
    "folder":  {"icon": "📁", "color": "#fab387", "label": "文件夹"},
    "project": {"icon": "🔧", "color": "#cba6f7", "label": "项目"},
    "url":     {"icon": "🌐", "color": "#94e2d5", "label": "网址"},
    "command": {"icon": "⚡", "color": "#bac2de", "label": "命令"},
}

# 分组显示顺序
TYPE_ORDER = ["game", "app", "url", "folder", "project", "file", "command"]

# ── 配色 ─────────────────────────────────────────────
C_BG   = "#1a1b26"
C_BAR  = "#1a1b26"
C_CARD = "#282b3d"
C_HOVER = "#313554"
C_TEXT = "#c8d0f0"
C_SUB  = "#6b7398"
C_ACC  = "#89b4fa"
C_RED  = "#f38ba8"
C_HANDLE = "#89b4fa"
C_SEL = "#3a3f5c"

FONT_NAME  = ("Microsoft YaHei UI", 11)
FONT_BOLD  = ("Microsoft YaHei UI", 12, "bold")
FONT_SMALL = ("Microsoft YaHei UI", 10)

BAR_W      = 440
SIDEBAR_W  = 56        # 左侧分类导航宽度
HANDLE_W   = 12        # 隐藏时露出的把手宽度
ANIM_FRAMES = 8        # 动画帧数
ANIM_MS    = 10        # 每帧间隔


class GameBar:
    def __init__(self):
        self.cfg = self._load_config()
        self.items: list[dict] = self.cfg.get("items", [])
        self.position = self.cfg.get("position", "right")
        self.hide_delay_ms = self.cfg.get("hide_delay_ms", 900)
        self.editor = self.cfg.get("editor", "code")
        self.opacity = self.cfg.get("opacity", 0.82)

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.wm_attributes("-alpha", self.opacity)
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()

        self._visible = False
        self._animating = False
        self._hide_timer = None
        self._anim_job: str | None = None
        self._sel_idx = -1
        self._card_rows: dict[int, tk.Frame] = {}
        self._card_map: list[int] = []   # visual row index → item index
        self._scroll_target: str = ""     # 当前滚动目标分类，空串=全部
        self._group_headers: dict[str, tk.Frame] = {}  # 分类分组标题引用
        self._sidebar_btns: dict[str, tk.Frame] = {}
        self._drag_item: int = -1        # 正在拖拽的项目 index
        self._drag_start: tuple = (0, 0) # 拖拽起始坐标
        self._dragging: bool = False     # 是否正在拖拽
        self._drag_hover: str = ""       # 拖拽时悬停的分类 key
        self._drag_float: tk.Toplevel | None = None  # 拖拽时的浮动窗口

        self._build_ui()
        self._go_hidden()
        self.root.deiconify()

        # 窗口关闭时自动保存（覆盖 Alt+F4、系统关机等所有退出方式）
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.bind("<Destroy>", lambda e: self._on_destroy(e))

        # 定时自动保存：每 30 秒存一次，防崩溃/断电丢失
        self._auto_save_timer = self.root.after(30000, self._auto_save_loop)

    # ════════════════════════════════════════════
    # 配置
    # ════════════════════════════════════════════
    def _load_config(self):
        if os.path.exists(OLD_CFG_FILE) and not os.path.exists(CFG_FILE):
            self._migrate()
        if os.path.exists(CFG_FILE):
            try:
                with open(CFG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"position": "right", "hide_delay_ms": 900, "editor": "code", "items": []}

    def _migrate(self):
        try:
            with open(OLD_CFG_FILE, "r", encoding="utf-8") as f:
                old = json.load(f)
            items = [{"type": "game", "name": g["name"], "path": g["path"]}
                     for g in old.get("games", [])]
            cfg = {"position": old.get("position", "right"),
                   "hide_delay_ms": old.get("hide_delay_ms", 900),
                   "editor": "code", "items": items}
            with open(CFG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            os.rename(OLD_CFG_FILE, OLD_CFG_FILE + ".bak")
        except Exception:
            pass

    def _save(self):
        """原子写入：先写临时文件再替换，防止断电/崩溃损坏配置"""
        self.cfg.update(position=self.position, hide_delay_ms=self.hide_delay_ms,
                        editor=self.editor, opacity=self.opacity, items=self.items)
        try:
            tmp = CFG_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, ensure_ascii=False, indent=2)
            os.replace(tmp, CFG_FILE)  # 原子替换
        except Exception:
            pass

    def _auto_save_loop(self):
        """每 30 秒自动保存一次，防崩溃丢失数据"""
        self._save()
        self._auto_save_timer = self.root.after(30000, self._auto_save_loop)

    # ════════════════════════════════════════════
    # 几何计算
    # ════════════════════════════════════════════
    def _bar_h(self):
        n = len(self.items)
        types = set(it.get("type", "command") for it in self.items)
        groups = sum(1 for t in TYPE_ORDER if t in types)
        return min(170 + groups * 26 + n * 62, int(self.sh * 0.72))

    def _geo(self, visible):
        """返回 (w, h, x, y)"""
        w, h = BAR_W, self._bar_h()
        if self.position == "right":
            x = self.sw - (BAR_W if visible else HANDLE_W)
            y = (self.sh - h) // 2
        elif self.position == "left":
            x = 0 if visible else HANDLE_W - BAR_W
            y = (self.sh - h) // 2
        elif self.position == "top":
            x = (self.sw - BAR_W) // 2
            y = 0 if visible else HANDLE_W - h
        else:  # bottom
            x = (self.sw - BAR_W) // 2
            y = self.sh - h if visible else self.sh - HANDLE_W
        return w, h, x, y

    def _apply_geo(self, visible):
        w, h, x, y = self._geo(visible)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _go_hidden(self):
        self._apply_geo(False)
        self._visible = False

    # ════════════════════════════════════════════
    # 动画
    # ════════════════════════════════════════════
    def _cancel_anim(self):
        if self._anim_job:
            self.root.after_cancel(self._anim_job)
            self._anim_job = None
        self._animating = False

    def _slide_in(self):
        if self._visible or self._animating:
            return
        self._cancel_anim()
        self._cancel_hide_timer()
        self._animating = True

        w, h, _, _ = self._geo(True)
        _, _, sx, sy = self._geo(False)
        _, _, ex, ey = self._geo(True)
        n = ANIM_FRAMES

        def step(i=0):
            if i > n:
                self.root.geometry(f"{w}x{h}+{ex}+{ey}")
                self._animating = False
                self._visible = True
                self._anim_job = None
                self._sel_idx = -1
                self._refresh_highlight()
                self._update_status()
                return
            t = i / n
            e = 1 - (1 - t) ** 3
            cx = int(sx + (ex - sx) * e)
            cy = int(sy + (ey - sy) * e)
            self.root.geometry(f"{w}x{h}+{cx}+{cy}")
            self._anim_job = self.root.after(ANIM_MS, step, i + 1)

        step()

    def _slide_out(self):
        if not self._visible or self._animating:
            return
        self._cancel_anim()
        self._cancel_hide_timer()
        self._animating = True
        self._sel_idx = -1
        self._refresh_highlight()

        w, h, _, _ = self._geo(True)
        _, _, sx, sy = self._geo(True)
        _, _, ex, ey = self._geo(False)
        n = ANIM_FRAMES

        def step(i=0):
            if i > n:
                self.root.geometry(f"{w}x{h}+{ex}+{ey}")
                self._animating = False
                self._visible = False
                self._anim_job = None
                return
            t = i / n
            e = 1 - (1 - t) ** 3
            cx = int(sx + (ex - sx) * e)
            cy = int(sy + (ey - sy) * e)
            self.root.geometry(f"{w}x{h}+{cx}+{cy}")
            self._anim_job = self.root.after(ANIM_MS, step, i + 1)

        step()

    def _toggle(self):
        if self._animating:
            return
        if self._visible:
            self._slide_out()
        else:
            self._slide_in()

    # ════════════════════════════════════════════
    # 鼠标交互
    # ════════════════════════════════════════════
    def _on_enter(self, event):
        if self._animating:
            return
        self._cancel_hide_timer()
        if not self._visible:
            self._slide_in()

    def _on_leave(self, event):
        if self._animating or self._dragging:
            return
        # 确认真的离开
        rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        mx, my = self.root.winfo_pointerxy()
        if rx <= mx <= rx + rw and ry <= my <= ry + rh:
            return
        self._schedule_hide()

    def _schedule_hide(self):
        self._cancel_hide_timer()
        self._hide_timer = self.root.after(self.hide_delay_ms, self._slide_out)

    def _cancel_hide_timer(self):
        if self._hide_timer:
            self.root.after_cancel(self._hide_timer)
            self._hide_timer = None

    # ════════════════════════════════════════════
    # 拖拽移动分类
    # ════════════════════════════════════════════
    def _on_drag_start(self, event, idx, item):
        self._drag_item = idx
        self._drag_start = (event.x_root, event.y_root)
        self._dragging = False

    def _on_drag_motion(self, event):
        if self._drag_item < 0:
            return
        dx = event.x_root - self._drag_start[0]
        dy = event.y_root - self._drag_start[1]
        if not self._dragging and (abs(dx) > 8 or abs(dy) > 8):
            self._dragging = True
            self._start_drag_float(event)
        if self._dragging:
            self._move_drag_float(event.x_root, event.y_root)
            self._highlight_drop_target(event.x_root, event.y_root)

    def _start_drag_float(self, event):
        """创建拖拽浮动窗口"""
        item = self.items[self._drag_item]
        info = ITEM_TYPES.get(item.get("type", "command"), ITEM_TYPES["command"])
        name = item.get("name", "?")

        fw = tk.Toplevel(self.root)
        fw.overrideredirect(True)
        fw.wm_attributes("-topmost", True)
        fw.wm_attributes("-alpha", 0.75)
        fw.configure(bg=C_CARD)

        inner = tk.Frame(fw, bg=C_CARD)
        inner.pack(padx=16, pady=10)

        # 小图标 + 名称
        tk.Label(inner, text=info["icon"], bg=C_CARD,
                 font=("Segoe UI Emoji", 14)).pack(side="left", padx=(0, 8))
        tk.Label(inner, text=name, bg=C_CARD, fg=C_TEXT,
                 font=FONT_BOLD).pack(side="left")

        fw.update_idletasks()
        fw.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")

        # 原卡片变暗
        if self._drag_item in self._card_rows:
            self._set_bg(self._card_rows[self._drag_item], "#1e2030")

        self._drag_float = fw

    def _move_drag_float(self, rx, ry):
        """移动浮动窗口跟随鼠标"""
        if self._drag_float:
            try:
                self._drag_float.geometry(f"+{rx + 12}+{ry + 12}")
            except Exception:
                pass

    def _on_drag_stop(self, event, idx, item):
        drag_idx = self._drag_item
        if drag_idx < 0:
            return
        self.root.config(cursor="")
        self._clear_drop_highlights()

        # 销毁浮动窗口
        if self._drag_float:
            try:
                self._drag_float.destroy()
            except Exception:
                pass
            self._drag_float = None

        if self._dragging:
            target = self._find_drop_target(event.x_root, event.y_root)
            if target and target not in ("all", ""):
                old_type = self.items[drag_idx].get("type", "")
                if target != old_type:
                    self.items[drag_idx]["type"] = target
                    self._save()
                    self._refresh_entries()
                    info = ITEM_TYPES.get(target, {})
                    self._flash(f"已移至「{info.get('label', target)}」")
                else:
                    self._refresh_entries()
            else:
                self._refresh_entries()
        else:
            self._launch(self.items[drag_idx])

        self._drag_item = -1
        self._dragging = False

    def _find_drop_target(self, rx, ry):
        """根据屏幕坐标找到鼠标所在的侧边栏分类"""
        for key, btn in self._sidebar_btns.items():
            try:
                bx = btn.winfo_rootx()
                by = btn.winfo_rooty()
                bw = btn.winfo_width()
                bh = btn.winfo_height()
                if bx <= rx <= bx + bw and by <= ry <= by + bh:
                    return key
            except Exception:
                pass
        return None

    def _highlight_drop_target(self, rx, ry):
        """拖拽经过侧边栏按钮时高亮目标"""
        target = self._find_drop_target(rx, ry) or ""
        if target == self._drag_hover:
            return
        # 恢复上一个
        if self._drag_hover and self._drag_hover in self._sidebar_btns:
            self._restore_sidebar_btn(self._drag_hover)
        # 高亮新目标
        self._drag_hover = target
        if target and target != "all" and target in self._sidebar_btns:
            self._set_bg(self._sidebar_btns[target], "#3a3f60")

    def _restore_sidebar_btn(self, key):
        """恢复单个侧边栏按钮的默认背景"""
        btn = self._sidebar_btns.get(key)
        if not btn:
            return
        active = key == (self._scroll_target or "all")
        self._set_bg(btn, "#2a2d40" if active else "#1e2030")

    def _on_global_release(self, event):
        """全局松手 — 处理拖出窗口外的释放"""
        if self._dragging and self._drag_item >= 0:
            self.root.config(cursor="")
            self._clear_drop_highlights()
            if self._drag_float:
                try:
                    self._drag_float.destroy()
                except Exception:
                    pass
                self._drag_float = None
            self._refresh_entries()
            self._drag_item = -1
            self._dragging = False

    def _clear_drop_highlights(self):
        """清除拖拽高亮，恢复侧边栏"""
        if self._drag_hover and self._drag_hover in self._sidebar_btns:
            self._restore_sidebar_btn(self._drag_hover)
        self._drag_hover = ""

    # ════════════════════════════════════════════
    # 键盘
    # ════════════════════════════════════════════
    def _on_key(self, event):
        if not self._visible or self._animating:
            return
        n = len(self._card_map)
        if n == 0:
            return
        k = event.keysym
        if k == "Up":
            self._sel_idx = n - 1 if self._sel_idx < 0 else (self._sel_idx - 1) % n
            self._refresh_highlight()
            self._scroll_to_sel()
        elif k == "Down":
            self._sel_idx = 0 if self._sel_idx >= n - 1 else (self._sel_idx + 1) % n
            self._refresh_highlight()
            self._scroll_to_sel()
        elif k == "Return" and self._sel_idx >= 0:
            item_idx = self._card_map[self._sel_idx]
            self._launch(self.items[item_idx])
        elif k == "Delete" and self._sel_idx >= 0:
            item_idx = self._card_map[self._sel_idx]
            self._delete_item(item_idx)
        elif k == "Escape":
            self._slide_out()

    def _refresh_highlight(self):
        for vi, item_idx in enumerate(self._card_map):
            row = self._card_rows[item_idx]
            self._set_bg(row, C_SEL if vi == self._sel_idx else C_CARD)

    def _scroll_to_sel(self):
        if self._sel_idx < 0 or not self._card_map:
            return
        item_idx = self._card_map[self._sel_idx]
        row = self._card_rows[item_idx]
        self.entries_frame.update_idletasks()
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        yt, yb = row.winfo_y(), row.winfo_y() + row.winfo_height()
        ch = self.canvas.winfo_height()
        ct = self.canvas.canvasy(0)
        cb = ct + ch
        if yt < ct:
            self.canvas.yview_moveto(yt / bbox[3])
        elif yb > cb:
            self.canvas.yview_moveto((yb - ch) / bbox[3])

    # ════════════════════════════════════════════
    # UI 构建
    # ════════════════════════════════════════════
    def _build_ui(self):
        root = self.root
        root.overrideredirect(True)
        root.wm_attributes("-topmost", True)
        try:
            root.wm_attributes("-toolwindow", True)
        except Exception:
            pass
        root.configure(bg=C_BAR)

        root.bind("<Enter>", self._on_enter)
        root.bind("<Leave>", self._on_leave)
        root.bind("<Up>", self._on_key)
        root.bind("<Down>", self._on_key)
        root.bind("<Return>", self._on_key)
        root.bind("<Delete>", self._on_key)
        root.bind("<Escape>", self._on_key)
        root.bind_all("<Alt-grave>", lambda e: self._toggle())
        root.bind_all("<ButtonRelease-1>", self._on_global_release)

        # 主容器 — 左边留 HANDLE_W 做把手
        main = tk.Frame(root, bg=C_BAR, highlightthickness=0)
        main.pack(fill="both", expand=True, padx=(HANDLE_W, 0))

        # ── 把手（始终露出一条色带） ──
        handle = tk.Canvas(root, width=HANDLE_W, bg=C_BAR, highlightthickness=0)
        handle.place(x=0, y=0, relheight=1.0)
        for i in range(HANDLE_W):
            shade = f"#{int(0x89 - i * 4):02x}{int(0xb4 - i * 3):02x}{int(0xfa - i * 5):02x}"
            handle.create_line(i, 0, i, 2000, fill=shade, width=1)
        handle.bind("<Enter>", self._on_enter)

        # ── 标题 ──
        tb = tk.Frame(main, bg=C_BAR, height=38)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        tk.Label(tb, text="QuickBar", bg=C_BAR, fg=C_ACC,
                 font=FONT_BOLD).pack(side="left", padx=10, pady=6)

        btns = tk.Frame(tb, bg=C_BAR)
        btns.pack(side="right", padx=4)
        for t, c, cmd in [("+", C_ACC, self._add_item),
                          ("⚙", C_TEXT, self._open_settings),
                          ("✕", C_RED, self._quit)]:
            tk.Button(btns, text=t, bg=C_BAR, fg=c, bd=0,
                      font=("Arial", 13), activebackground=C_HOVER,
                      activeforeground=c, cursor="hand2",
                      command=cmd).pack(side="left", padx=3)

        # ── 分隔线 ──
        tk.Frame(main, bg="#313550", height=1).pack(fill="x", padx=10)

        # ── 主体：侧边栏 + 内容区 ──
        body = tk.Frame(main, bg=C_BAR)
        body.pack(fill="both", expand=True)

        # 左侧分类导航（可滚动）
        self.sidebar = tk.Frame(body, bg="#1e2030", width=SIDEBAR_W)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.sidebar_canvas = tk.Canvas(self.sidebar, bg="#1e2030",
                                        highlightthickness=0, width=SIDEBAR_W)
        self.sidebar_canvas.pack(side="left", fill="both", expand=True)

        self.sidebar_inner = tk.Frame(self.sidebar_canvas, bg="#1e2030")
        self.sidebar_cw = self.sidebar_canvas.create_window(
            (0, 0), window=self.sidebar_inner, anchor="nw", tags="sbar")

        self.sidebar_inner.bind("<Configure>",
            lambda e: self.sidebar_canvas.configure(
                scrollregion=self.sidebar_canvas.bbox("all")))
        self.sidebar_canvas.bind("<Configure>",
            lambda e: self.sidebar_canvas.itemconfig(self.sidebar_cw, width=e.width))
        self._build_sidebar()

        # 右侧内容区
        content = tk.Frame(body, bg=C_BAR)
        content.pack(side="left", fill="both", expand=True)

        # 分类标题
        self.cat_lbl = tk.Label(content, text="", bg=C_BAR, fg=C_TEXT,
                                font=FONT_BOLD, anchor="w")
        self.cat_lbl.pack(fill="x", padx=14, pady=(8, 2))

        self.canvas = tk.Canvas(content, bg=C_BAR, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(content, orient="vertical",
                                      command=self._on_scrollbar)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.entries_frame = tk.Frame(self.canvas, bg=C_BAR)
        self.cw = self.canvas.create_window((0, 0), window=self.entries_frame,
                                            anchor="nw", tags="ef")

        self.entries_frame.bind("<Configure>",
                                lambda e: (self.canvas.configure(
                                    scrollregion=self.canvas.bbox("all")),
                                    self._check_scrollbar()))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfig(self.cw, width=e.width))
        self.canvas.pack(side="left", fill="both", expand=True)

        # ── 底栏 ──
        sf = tk.Frame(main, bg=C_BAR, height=24)
        sf.pack(fill="x")
        sf.pack_propagate(False)
        tk.Frame(main, bg="#313550", height=1).pack(fill="x", padx=10)
        self.status_lbl = tk.Label(sf, text="", bg=C_BAR, fg=C_SUB,
                                   font=(FONT_NAME[0], 8), anchor="w")
        self.status_lbl.pack(fill="x", padx=10, pady=2)

        # 统一滚轮调度：根据鼠标位置判断滚动侧边栏还是内容区
        self.root.bind_all("<MouseWheel>", self._on_global_wheel)

        self._refresh_sidebar()
        self._refresh_entries()

    def _build_sidebar(self):
        """构建侧边栏分类按钮"""
        sb = self.sidebar_inner
        # Claude 快捷入口
        claude_btn = tk.Frame(sb, bg="#1e2030", cursor="hand2")
        claude_inner = tk.Frame(claude_btn, bg="#1e2030")
        claude_inner.pack(padx=8, pady=(10, 4))

        c_circle = tk.Canvas(claude_inner, width=36, height=36, bg="#1e2030",
                             highlightthickness=0)
        c_circle.create_oval(2, 2, 34, 34, fill="#cba6f7", outline="")
        c_circle.create_text(18, 18, text="🧠", font=("Segoe UI Emoji", 14))
        c_circle.pack()

        tk.Label(claude_inner, text="Claude", bg="#1e2030", fg="#cba6f7",
                 font=(FONT_NAME[0], 8, "bold"), anchor="center").pack(pady=(2, 0))

        for w in (claude_btn, claude_inner, c_circle):
            w.bind("<Button-1>", lambda e: self._launch_claude())
            w.bind("<Enter>", lambda e: self._simple_hover(claude_btn, True))
            w.bind("<Leave>", lambda e: self._simple_hover(claude_btn, False))

        claude_btn.pack(pady=(6, 2))

        tk.Frame(sb, bg="#2a2d40", height=1).pack(fill="x", padx=8, pady=4)

        # 「全部」按钮
        all_btn = self._make_sidebar_btn("all", "📋", "#c0caf5", "全部")
        all_btn.pack(pady=(2, 2))

        tk.Frame(sb, bg="#2a2d40", height=1).pack(fill="x", padx=8, pady=4)

        # 各分类按钮
        for t in TYPE_ORDER:
            info = ITEM_TYPES[t]
            btn = self._make_sidebar_btn(t, info["icon"], info["color"], info["label"])
            btn.pack(pady=2)

        # ── 底部操作区 ──
        tk.Frame(sb, bg="#2a2d40", height=1).pack(fill="x", padx=8, pady=4)

        # 一键关闭浏览器按钮
        kill_btn = tk.Frame(sb, bg="#1e2030", cursor="hand2")
        kill_inner = tk.Frame(kill_btn, bg="#1e2030")
        kill_inner.pack(padx=8, pady=4)

        k_circle = tk.Canvas(kill_inner, width=36, height=36, bg="#1e2030", highlightthickness=0)
        k_circle.create_oval(2, 2, 34, 34, fill="#f38ba8", outline="")
        k_circle.create_text(18, 18, text="🌐", font=("Segoe UI Emoji", 13))
        k_circle.pack()

        tk.Label(kill_inner, text="关闭网页", bg="#1e2030", fg=C_RED,
                 font=(FONT_NAME[0], 8), anchor="center").pack(pady=(2, 0))

        for w in (kill_btn, kill_inner, k_circle):
            w.bind("<Button-1>", lambda e: self._close_browsers())
            w.bind("<Enter>", lambda e: self._simple_hover(kill_btn, True))
            w.bind("<Leave>", lambda e: self._simple_hover(kill_btn, False))

        kill_btn.pack(side="bottom", pady=(2, 10))
        self._kill_btn = kill_btn

    def _make_sidebar_btn(self, key, icon, color, label):
        """创建一个侧边栏导航按钮"""
        btn = tk.Frame(self.sidebar_inner, bg="#1e2030", cursor="hand2")
        inner = tk.Frame(btn, bg="#1e2030")
        inner.pack(padx=8, pady=4)

        circle = tk.Canvas(inner, width=36, height=36, bg="#1e2030", highlightthickness=0)
        circle.create_oval(2, 2, 34, 34, fill=color, outline="")
        circle.create_text(18, 18, text=icon, font=("Segoe UI Emoji", 14))
        circle.pack()

        tk.Label(inner, text=label, bg="#1e2030", fg=C_SUB,
                 font=(FONT_NAME[0], 8), anchor="center").pack(pady=(2, 0))

        for w in (btn, inner, circle):
            w.bind("<Button-1>", lambda e: self._on_sidebar_click(key))
            w.bind("<Enter>", lambda e: self._sidebar_hover(btn, True))
            w.bind("<Leave>", lambda e: self._sidebar_hover(btn, False))

        self._sidebar_btns[key] = btn
        return btn

    def _sidebar_hover(self, btn, entering):
        is_active = self._sidebar_btns.get(self._scroll_target if self._scroll_target else "all") == btn
        self._set_bg(btn, "#2a2d40" if entering or is_active else "#1e2030")

    def _simple_hover(self, btn, entering):
        self._set_bg(btn, "#2a2d40" if entering else "#1e2030")

    def _launch_claude(self):
        """在终端中启动 Claude"""
        try:
            subprocess.Popen('start "Claude" cmd /k claude', shell=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            self._flash("Claude 已启动")
        except Exception as e:
            self._flash(f"启动 Claude 失败: {e}")

    def _close_browsers(self):
        """一键关闭所有浏览器窗口"""
        browsers = ["chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe"]
        # 合并为一条命令，隐藏控制台窗口
        cmd = ["taskkill", "/f"] + [arg for b in browsers for arg in ("/im", b)]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            self._flash("正在关闭浏览器...")
        except Exception as e:
            self._flash(f"关闭失败: {e}")

    def _on_sidebar_click(self, key):
        new_target = "" if key == "all" else key
        # 卡片列表与分类无关（始终全部分组渲染），只需更新高亮 + 滚动
        if new_target == self._scroll_target:
            if new_target:
                self._scroll_to_group(new_target)
            else:
                self.canvas.yview_moveto(0)
            return
        self._scroll_target = new_target
        self._sel_idx = -1
        self._refresh_sidebar()
        if new_target:
            info = ITEM_TYPES[new_target]
            self.cat_lbl.configure(text=f"{info['icon']}  {info['label']}",
                                   fg=info["color"])
        else:
            self.cat_lbl.configure(text="📋  全部", fg=C_TEXT)
        self._refresh_highlight()
        if new_target:
            self.root.after(20, lambda: self._scroll_to_group(new_target))
        else:
            self.canvas.yview_moveto(0)

    def _refresh_sidebar(self):
        """更新侧边栏高亮状态"""
        active_key = self._scroll_target if self._scroll_target else "all"
        for key, btn in self._sidebar_btns.items():
            self._set_bg(btn, "#2a2d40" if key == active_key else "#1e2030")

    def _set_bg(self, widget, bg):
        """递归设置 widget 及所有子代的背景色（忽略不支持 bg 的控件）"""
        try:
            widget.configure(bg=bg)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._set_bg(child, bg)

    def _is_inside(self, widget, ancestor):
        """检查 widget 是否为 ancestor 的后代"""
        w = widget
        while w:
            if w is ancestor:
                return True
            w = w.master
        return False

    def _on_global_wheel(self, event):
        """统一滚轮：鼠标在侧边栏滚动侧边栏，否则滚动内容区"""
        if self._is_inside(event.widget, self.sidebar):
            self.sidebar_canvas.yview_scroll(int(-event.delta / 120), "units")
        else:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_scrollbar(self, *args):
        self.canvas.yview(*args)
        self._check_scrollbar()

    def _check_scrollbar(self):
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        need = bbox[3] > self.canvas.winfo_height()
        has = self.scrollbar.winfo_ismapped()
        if need and not has:
            self.canvas.pack_forget()
            self.scrollbar.pack(side="right", fill="y")
            self.canvas.pack(side="left", fill="both", expand=True)
        elif not need and has:
            self.scrollbar.pack_forget()
            self.canvas.pack(side="left", fill="both", expand=True)

    # ════════════════════════════════════════════
    # 条目列表
    # ════════════════════════════════════════════
    def _refresh_entries(self):
        self._card_rows.clear()
        self._card_map.clear()
        for w in self.entries_frame.winfo_children():
            w.destroy()

        if not self.items:
            self.cat_lbl.configure(text="")
            empty = tk.Frame(self.entries_frame, bg=C_BAR)
            empty.pack(fill="x", padx=16, pady=40)
            tk.Label(empty, text="还没有添加快捷方式", bg=C_BAR, fg=C_SUB,
                     font=FONT_NAME).pack()
            tk.Label(empty, text="点击 ＋ 添加", bg=C_BAR, fg="#454a65",
                     font=FONT_SMALL).pack(pady=(6, 0))
            self._resize_bar()
            self._update_status()
            return

        # 分组
        groups: dict[str, list[int]] = {}
        for i, item in enumerate(self.items):
            t = item.get("type", "command")
            groups.setdefault(t, []).append(i)

        # 分类标题
        if self._scroll_target:
            info = ITEM_TYPES[self._scroll_target]
            self.cat_lbl.configure(text=f"{info['icon']}  {info['label']}",
                                   fg=info["color"])
        else:
            self.cat_lbl.configure(text="📋  全部", fg=C_TEXT)

        self._group_headers.clear()

        for t in TYPE_ORDER:
            if t not in groups:
                continue
            info = ITEM_TYPES[t]
            # 始终显示分组标题
            hdr = tk.Frame(self.entries_frame, bg=C_BAR)
            hdr.pack(fill="x", padx=14, pady=(10, 2))
            tk.Label(hdr, text=f"{info['icon']}  {info['label']}",
                     bg=C_BAR, fg=info["color"], font=FONT_SMALL).pack(side="left")
            tk.Frame(hdr, bg=info["color"], height=1).pack(side="left", fill="x",
                                                           expand=True, padx=(10, 4))
            self._group_headers[t] = hdr
            for idx in groups[t]:
                self._create_card(idx, self.items[idx])
                self._card_map.append(idx)

        if self._scroll_target:
            self.root.after(20, lambda: self._scroll_to_group(self._scroll_target))
        else:
            self.canvas.yview_moveto(0)
        self._resize_bar()
        self._update_status()

    def _scroll_to_group(self, target):
        """滚动内容区到指定分类的分组标题位置"""
        self.canvas.update_idletasks()
        hdr = self._group_headers.get(target)
        if hdr is None:
            return
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        # 分组标题在 entries_frame 中的 y 坐标
        hdr_y = hdr.winfo_y()
        content_h = bbox[3] - bbox[1]
        if content_h <= 0:
            return
        # 留一点顶部边距，避免标题贴顶
        fraction = max(0.0, min(1.0, (hdr_y - 10) / content_h))
        self.canvas.yview_moveto(fraction)

    def _create_card(self, idx, item):
        itype = item.get("type", "game")
        name = item.get("name", f"条目 {idx + 1}")
        path = item.get("path", "")
        info = ITEM_TYPES.get(itype, ITEM_TYPES["command"])

        row = tk.Frame(self.entries_frame, bg=C_CARD, cursor="hand2")
        row.pack(fill="x", padx=10, pady=(3, 3), ipady=8)
        self._card_rows[idx] = row

        drag_evs = {
            "<ButtonPress-1>": lambda e, i=idx, it=item: self._on_drag_start(e, i, it),
            "<B1-Motion>": lambda e: self._on_drag_motion(e),
            "<ButtonRelease-1>": lambda e, i=idx, it=item: self._on_drag_stop(e, i, it),
            "<Button-3>": lambda e, i=idx: self._entry_menu(e, i),
            "<Enter>": self._hover_in(idx),
            "<Leave>": self._hover_out(idx),
        }
        for ev, cb in drag_evs.items():
            row.bind(ev, cb)

        # ── 头像 ──
        av_size = 42
        av = tk.Canvas(row, width=av_size + 4, height=av_size + 4,
                       bg=C_CARD, highlightthickness=0)
        av.pack(side="left", padx=(14, 12), pady=8)
        av.create_oval(2, 2, av_size + 2, av_size + 2,
                       fill="", outline=info["color"], width=2)
        av.create_oval(4, 4, av_size, av_size,
                       fill=info["color"], outline="")
        av.create_text(av_size / 2 + 2, av_size / 2 + 2,
                       text=name[0] if name else "?",
                       fill=C_BAR, font=("Microsoft YaHei UI", 15, "bold"))

        # ── 文字 ──
        txt = tk.Frame(row, bg=C_CARD)
        txt.pack(side="left", fill="x", expand=True, pady=(6, 4))
        tk.Label(txt, text=name, bg=C_CARD, fg=C_TEXT,
                 font=FONT_BOLD, anchor="w").pack(fill="x")
        sub = path if path else "未设置"
        if len(sub) > 36:
            sub = sub[:34] + "..."
        tk.Label(txt, text=f"{info['icon']}  {info['label']}  ·  {sub}",
                 bg=C_CARD, fg=C_SUB, font=FONT_SMALL, anchor="w").pack(fill="x", pady=(2, 0))

        # ── 删除按钮 ──
        dbtn = tk.Label(row, text="✕", bg=C_CARD, fg=C_SUB,
                        font=("Arial", 10), cursor="hand2")
        dbtn.pack(side="right", padx=(0, 12), pady=8)
        dbtn.bind("<Button-1>", lambda e, i=idx: self._delete_item(i))
        dbtn.bind("<Enter>", lambda e, d=dbtn, r=row:
                  (d.configure(bg=C_RED, fg=C_BAR), r.configure(bg=C_HOVER)))
        dbtn.bind("<Leave>", self._hover_out(idx))

        # 递归绑定所有子控件（删除按钮除外），确保点击任意位置都触发启动
        self._bind_descendants(row, drag_evs, exclude={dbtn})

    def _bind_descendants(self, widget, events, exclude):
        """递归为所有子控件绑定事件，确保点击任意位置都响应"""
        for child in widget.winfo_children():
            if child in exclude:
                continue
            for ev, cb in events.items():
                # 不覆盖子控件已有的同类型绑定
                if not child.bind(ev):
                    child.bind(ev, cb)
            self._bind_descendants(child, events, exclude)

    def _hover_in(self, idx):
        def fn(event):
            if self._sel_idx >= 0 and self._card_map[self._sel_idx] == idx:
                return
            self._set_bg(self._card_rows[idx], C_HOVER)
        return fn

    def _hover_out(self, idx):
        def fn(event):
            row = self._card_rows[idx]
            sel = self._sel_idx >= 0 and self._card_map[self._sel_idx] == idx
            bg = C_SEL if sel else C_CARD
            self._set_bg(row, bg)
            for child in row.winfo_children():
                if isinstance(child, tk.Label) and child.cget("text") == "✕":
                    child.configure(fg=C_SUB)
        return fn

    def _entry_menu(self, event, idx):
        menu = tk.Menu(self.root, tearoff=0, bg=C_CARD, fg=C_TEXT,
                       activebackground=C_HOVER, activeforeground=C_TEXT,
                       font=FONT_SMALL)
        menu.add_command(label="编辑", command=lambda: self._edit_item(idx))
        menu.add_command(label="上移", command=lambda: self._move_item(idx, -1))
        menu.add_command(label="下移", command=lambda: self._move_item(idx, 1))
        menu.add_separator()
        menu.add_command(label="删除", command=lambda: self._delete_item(idx))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ════════════════════════════════════════════
    # 启动
    # ════════════════════════════════════════════
    def _launch(self, item):
        path = item.get("path", "")
        itype = item.get("type", "game")
        if not path:
            messagebox.showwarning("QuickBar", "请先设置路径")
            return

        self._flash(f"正在启动 {item['name']}...")
        try:
            if itype in ("game", "app", "file", "folder"):
                os.startfile(path)
            elif itype == "project":
                subprocess.Popen(f'code "{path}"', shell=True)
            elif itype == "url":
                webbrowser.open(path if "://" in path else f"https://{path}")
            elif itype == "command":
                subprocess.Popen(path, shell=True)
            else:
                os.startfile(path)
        except Exception as e:
            self._flash(f"启动失败: {str(e)[:50]}")

    # ════════════════════════════════════════════
    # 浏览器书签
    # ════════════════════════════════════════════
    def _load_browser_bookmarks(self):
        """读取 Chrome / Edge 书签，返回 [(name, url), ...]"""
        bookmarks = []
        browsers = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         r"Google\Chrome\User Data\Default\Bookmarks"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         r"Microsoft\Edge\User Data\Default\Bookmarks"),
        ]

        def _walk(node, result):
            if node.get("type") == "url":
                result.append((node.get("name", ""), node.get("url", "")))
            for child in node.get("children", []):
                _walk(child, result)

        for path in browsers:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                roots = data.get("roots", {})
                for root_key in ("bookmark_bar", "other"):
                    root = roots.get(root_key, {})
                    _walk(root, bookmarks)
            except Exception:
                pass

        return bookmarks

    def _show_url_dialog(self, name):
        """显示 URL 输入对话框，支持从浏览器收藏夹选取"""
        w = tk.Toplevel(self.root)
        w.title("添加网址")
        w.geometry("460x420")
        w.configure(bg=C_BAR)
        w.resizable(False, False)
        try:
            w.wm_attributes("-topmost", True)
        except Exception:
            pass
        w.geometry(f"+{(self.sw - 460) // 2}+{(self.sh - 420) // 2}")

        tk.Label(w, text=f"添加网址 — {name}", bg=C_BAR, fg=C_ACC,
                 font=FONT_BOLD).pack(pady=(12, 8))

        # 手动输入
        input_frame = tk.Frame(w, bg=C_BAR)
        input_frame.pack(fill="x", padx=28, pady=(0, 6))
        tk.Label(input_frame, text="网址:", bg=C_BAR, fg=C_TEXT,
                 font=FONT_NAME).pack(side="left")
        url_var = tk.StringVar()
        tk.Entry(input_frame, textvariable=url_var, bg=C_CARD, fg=C_TEXT,
                 font=FONT_NAME, bd=0, width=36).pack(side="left", padx=8, ipady=3)

        # 书签列表
        tk.Label(w, text="或从收藏夹选择:", bg=C_BAR, fg=C_SUB,
                 font=FONT_SMALL, anchor="w").pack(fill="x", padx=28, pady=(8, 2))

        list_frame = tk.Frame(w, bg=C_BAR)
        list_frame.pack(fill="both", expand=True, padx=28, pady=(0, 8))

        lb = tk.Listbox(list_frame, bg=C_CARD, fg=C_TEXT, font=FONT_SMALL,
                        selectbackground=C_HOVER, selectforeground=C_TEXT,
                        bd=0, highlightthickness=0, activestyle="none")
        lb.pack(side="left", fill="both", expand=True)

        scroll = tk.Scrollbar(list_frame, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        bookmarks = self._load_browser_bookmarks()
        for bm_name, bm_url in bookmarks:
            lb.insert("end", f"  {bm_name}  —  {bm_url}")

        lb.bind("<<ListboxSelect>>",
                lambda e: self._on_bookmark_select(lb, bookmarks, url_var))

        # 空状态
        if not bookmarks:
            lb.insert("end", "  未检测到浏览器书签")
            lb.configure(fg=C_SUB)

        # 按钮
        btn_frame = tk.Frame(w, bg=C_BAR)
        btn_frame.pack(pady=(0, 14))
        result = {"url": ""}

        def confirm():
            url = url_var.get().strip()
            if url:
                result["url"] = url
                w.destroy()

        def cancel():
            w.destroy()

        tk.Button(btn_frame, text="确定", command=confirm, bg=C_ACC, fg=C_BAR,
                  font=FONT_NAME, bd=0, padx=20, pady=4, cursor="hand2",
                  activebackground=C_HOVER).pack(side="left", padx=6)
        tk.Button(btn_frame, text="取消", command=cancel, bg=C_CARD, fg=C_TEXT,
                  font=FONT_NAME, bd=0, padx=20, pady=4, cursor="hand2",
                  activebackground=C_HOVER).pack(side="left", padx=6)

        w.grab_set()
        self.root.wait_window(w)
        return result["url"]

    def _on_bookmark_select(self, lb, bookmarks, url_var):
        sel = lb.curselection()
        if sel:
            idx = sel[0]
            if idx < len(bookmarks):
                url_var.set(bookmarks[idx][1])

    # ════════════════════════════════════════════
    # 增删改
    # ════════════════════════════════════════════
    def _add_item(self):
        # 在分类视图下直接使用当前分类类型
        if self._scroll_target and self._scroll_target in ITEM_TYPES:
            itype = self._scroll_target
        else:
            tmenu = tk.Menu(self.root, tearoff=0, bg=C_CARD, fg=C_TEXT,
                            activebackground=C_HOVER, activeforeground=C_TEXT, font=FONT_SMALL)
            chosen = tk.StringVar(value="")
            done = tk.BooleanVar(value=False)

            def pick(k):
                if not done.get():
                    done.set(True)
                    chosen.set(k)
                tmenu.unpost()

            for k, v in ITEM_TYPES.items():
                tmenu.add_command(label=f"{v['icon']}  {v['label']}", command=lambda k=k: pick(k))

            tmenu.bind("<Unmap>",
                       lambda e: self.root.after(80, lambda: done.get() or chosen.set("")))

            tmenu.tk_popup(self.root.winfo_rootx() + 48, self.root.winfo_rooty() + 48)
            self.root.wait_variable(chosen)
            tmenu.grab_release()
            tmenu.destroy()

            itype = chosen.get()
        if not itype:
            return
        info = ITEM_TYPES[itype]

        name = simpledialog.askstring(f"添加{info['label']}", f"{info['label']}名称:",
                                      parent=self.root)
        if not name:
            return

        path = ""
        if itype in ("game", "app"):
            path = filedialog.askopenfilename(
                title=f"选择{info['label']}程序",
                filetypes=[("可执行/快捷方式", "*.exe;*.lnk"), ("所有", "*.*")],
                parent=self.root)
            if not path:
                path = simpledialog.askstring(f"{info['label']}路径",
                                              "也可输入路径或 Steam URL:", parent=self.root)
        elif itype == "file":
            path = filedialog.askopenfilename(title="选择文件", parent=self.root)
        elif itype == "folder":
            path = filedialog.askdirectory(title="选择文件夹", parent=self.root)
        elif itype == "project":
            # 项目默认从用户目录开始选择
            start_dir = os.path.expanduser("~")
            # 尝试更合理的默认路径
            for d in [r"D:\Projects", r"D:\Code", r"D:\project",
                      os.path.join(os.path.expanduser("~"), "Projects"),
                      os.path.join(os.path.expanduser("~"), "Code")]:
                if os.path.isdir(d):
                    start_dir = d
                    break
            path = filedialog.askdirectory(
                title="选择项目文件夹（将用 VS Code 打开）",
                initialdir=start_dir, parent=self.root)
        elif itype == "command":
            path = simpledialog.askstring("命令", "输入命令:", parent=self.root)
        elif itype == "url":
            path = self._show_url_dialog(name)

        if not path:
            return
        self.items.append({"type": itype, "name": name, "path": path})
        self._save()
        self._refresh_entries()

    def _edit_item(self, idx):
        item = self.items[idx]
        info = ITEM_TYPES.get(item["type"], ITEM_TYPES["command"])
        nm = simpledialog.askstring(f"编辑{info['label']}", "名称:",
                                    initialvalue=item["name"], parent=self.root)
        if nm is not None:
            item["name"] = nm
        np_ = simpledialog.askstring("编辑路径", "路径:",
                                     initialvalue=item["path"], parent=self.root)
        if np_ is not None:
            item["path"] = np_
        self._save()
        self._refresh_entries()

    def _delete_item(self, idx):
        if idx < 0 or idx >= len(self.items):
            return
        item = self.items[idx]
        if messagebox.askyesno("确认", f"移除「{item['name']}」？", parent=self.root):
            self.items.pop(idx)
            self._sel_idx = -1
            self._save()
            self._refresh_entries()

    def _move_item(self, idx, d):
        n = idx + d
        if 0 <= n < len(self.items):
            self.items[idx], self.items[n] = self.items[n], self.items[idx]
            self._save()
            self._refresh_entries()

    # ════════════════════════════════════════════
    # 状态栏 / 尺寸
    # ════════════════════════════════════════════
    def _update_status(self):
        if not self.items:
            self.status_lbl.configure(text="暂无快捷方式  |  点击 ＋ 添加")
            return
        cnt = {}
        for it in self.items:
            t = it.get("type", "game")
            cnt[t] = cnt.get(t, 0) + 1
        parts = [f"{ITEM_TYPES[t]['icon']} {cnt[t]}" for t in sorted(cnt)]
        self.status_lbl.configure(text="  ·  ".join(parts))

    def _flash(self, text):
        self.status_lbl.configure(text=text, fg=C_ACC)
        self.root.after(1800, lambda: (self.status_lbl.configure(fg=C_SUB),
                                       self._update_status()))

    def _resize_bar(self):
        self._apply_geo(self._visible)
        self.root.after(60, self._check_scrollbar)

    # ════════════════════════════════════════════
    # 设置
    # ════════════════════════════════════════════
    def _open_settings(self):
        w = tk.Toplevel(self.root)
        w.title("QuickBar 设置")
        w.geometry("420x410")
        w.configure(bg=C_BAR)
        w.resizable(False, False)
        try:
            w.wm_attributes("-topmost", True)
        except Exception:
            pass
        w.geometry(f"+{(self.sw - 420) // 2}+{(self.sh - 410) // 2}")

        tk.Label(w, text="QuickBar 设置", bg=C_BAR, fg=C_ACC,
                 font=FONT_BOLD).pack(pady=(12, 10))

        # 位置
        pf = tk.Frame(w, bg=C_BAR)
        pf.pack(fill="x", padx=28, pady=5)
        tk.Label(pf, text="吸附位置", bg=C_BAR, fg=C_TEXT, font=FONT_NAME).pack(side="left")
        pv = tk.StringVar(value=self.position)
        for lbl, val in [("右", "right"), ("左", "left"), ("顶", "top"), ("底", "bottom")]:
            tk.Radiobutton(pf, text=lbl, variable=pv, value=val, bg=C_BAR, fg=C_TEXT,
                           selectcolor=C_CARD, activebackground=C_BAR, activeforeground=C_ACC,
                           font=FONT_NAME,
                           command=lambda: self._on_set("position", pv.get())
                           ).pack(side="left", padx=4)

        # 延迟
        df = tk.Frame(w, bg=C_BAR)
        df.pack(fill="x", padx=28, pady=5)
        tk.Label(df, text="收起延迟", bg=C_BAR, fg=C_TEXT, font=FONT_NAME).pack(side="left")
        dv = tk.IntVar(value=self.hide_delay_ms)
        tk.Scale(df, from_=200, to=2000, resolution=100, orient="horizontal",
                 variable=dv, bg=C_BAR, fg=C_TEXT, highlightthickness=0,
                 troughcolor=C_CARD, activebackground=C_HOVER, length=160,
                 command=lambda v: self._on_set("delay", int(v))).pack(side="right")

        # 透明度
        of = tk.Frame(w, bg=C_BAR)
        of.pack(fill="x", padx=28, pady=5)
        tk.Label(of, text="背景透明度", bg=C_BAR, fg=C_TEXT, font=FONT_NAME).pack(side="left")
        ov = tk.DoubleVar(value=self.opacity)
        tk.Scale(of, from_=0.35, to=1.0, resolution=0.05, orient="horizontal",
                 variable=ov, bg=C_BAR, fg=C_TEXT, highlightthickness=0,
                 troughcolor=C_CARD, activebackground=C_HOVER, length=160,
                 command=lambda v: self._on_set("opacity", float(v))).pack(side="right")

        # 编辑器
        ef = tk.Frame(w, bg=C_BAR)
        ef.pack(fill="x", padx=28, pady=5)
        tk.Label(ef, text="代码编辑器", bg=C_BAR, fg=C_TEXT, font=FONT_NAME).pack(side="left")
        ev = tk.StringVar(value=self.editor)
        tk.Entry(ef, textvariable=ev, bg=C_CARD, fg=C_TEXT, font=FONT_NAME, bd=0,
                 width=18).pack(side="right")
        tk.Button(ef, text="保存", bg=C_CARD, fg=C_TEXT, font=FONT_SMALL, bd=0,
                  cursor="hand2", activebackground=C_HOVER,
                  command=lambda: self._on_set("editor", ev.get())).pack(side="right", padx=4)

        # 开机自启
        af = tk.Frame(w, bg=C_BAR)
        af.pack(fill="x", padx=28, pady=5)
        tk.Label(af, text="开机自启", bg=C_BAR, fg=C_TEXT, font=FONT_NAME).pack(side="left")
        auto = tk.BooleanVar(value=self._autostart_check())
        tk.Checkbutton(af, variable=auto, bg=C_BAR, fg=C_ACC, selectcolor=C_CARD,
                       activebackground=C_BAR, activeforeground=C_ACC,
                       command=lambda: self._autostart_toggle(auto.get())
                       ).pack(side="right")

        tk.Label(w, text="鼠标移到屏幕边缘唤出  |  Alt+` 切换\n↑↓ 选择  Enter 启动  Esc 收起  Delete 删除",
                 bg=C_BAR, fg=C_SUB, font=(FONT_NAME[0], 8), justify="center"
                 ).pack(pady=(14, 4))

        tk.Button(w, text="关闭", command=w.destroy, bg=C_CARD, fg=C_TEXT,
                  font=FONT_NAME, bd=0, padx=32, pady=5, cursor="hand2",
                  activebackground=C_HOVER).pack(pady=6)

    def _on_set(self, key, val):
        if key == "position":
            self.position = val
            self._apply_geo(self._visible)
        elif key == "delay":
            self.hide_delay_ms = val
        elif key == "editor":
            self.editor = val
        elif key == "opacity":
            self.opacity = float(val)
            self.root.wm_attributes("-alpha", self.opacity)
        self._save()

    # ════════════════════════════════════════════
    # 开机自启
    # ════════════════════════════════════════════
    def _startup_path(self):
        return os.path.join(os.environ["APPDATA"],
                            r"Microsoft\Windows\Start Menu\Programs\Startup",
                            "QuickBar.lnk")

    def _autostart_check(self):
        return os.path.exists(self._startup_path())

    def _autostart_toggle(self, enable):
        try:
            import tempfile
            sp = self._startup_path()
            if enable:
                # 创建开机自启快捷方式
                ps = f"""
$WshShell = New-Object -ComObject WScript.Shell
$sc = $WshShell.CreateShortcut("{sp}")
$sc.TargetPath = "{sys.executable}"
$sc.Arguments = "{os.path.join(BASE_DIR, 'game_bar.py')}"
$sc.WorkingDirectory = "{BASE_DIR}"
$sc.IconLocation = "shell32.dll,14"
$sc.Save()
"""
                with tempfile.NamedTemporaryFile(suffix=".ps1", delete=False, mode="w",
                                                 encoding="utf-8") as f:
                    f.write(ps)
                    tmp = f.name
                subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", tmp],
                               capture_output=True)
                os.unlink(tmp)
            else:
                if os.path.exists(sp):
                    os.remove(sp)
        except Exception as e:
            messagebox.showerror("开机自启", f"操作失败: {e}")

    # ════════════════════════════════════════════
    # 退出
    # ════════════════════════════════════════════
    def _on_destroy(self, event):
        """窗口销毁时自动保存（覆盖所有关闭方式：Alt+F4、系统关机等）"""
        if event.widget == self.root and not getattr(self, '_saved_on_exit', False):
            self._saved_on_exit = True
            self._save()

    def _quit(self):
        if not getattr(self, '_saved_on_exit', False):
            self._saved_on_exit = True
            self._save()
        self.root.destroy()
        sys.exit(0)

    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self._quit()


if __name__ == "__main__":
    GameBar().run()
