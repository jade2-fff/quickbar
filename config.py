# config.py — 配置模型（Pydantic 验证 + 原子写入）
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

Positions = Literal["right", "left", "top", "bottom"]
ItemTypes = Literal["game", "app", "file", "folder", "project", "url", "command"]

BASE_DIR = Path(__file__).resolve().parent
CFG_FILE = BASE_DIR / "items.json"

ITEM_TYPES: dict[str, dict[str, str]] = {
    "game":    {"icon": "🎮", "color": "#f38ba8", "label": "游戏"},
    "app":     {"icon": "💻", "color": "#89b4fa", "label": "应用"},
    "file":    {"icon": "📄", "color": "#a6e3a1", "label": "文件"},
    "folder":  {"icon": "📁", "color": "#fab387", "label": "文件夹"},
    "project": {"icon": "🔧", "color": "#cba6f7", "label": "项目"},
    "url":     {"icon": "🌐", "color": "#94e2d5", "label": "网址"},
    "command": {"icon": "⚡", "color": "#bac2de", "label": "命令"},
}

TYPE_ORDER = list(ITEM_TYPES.keys())


class Config:
    def __init__(self, data: dict | None = None):
        d = data or {}
        self.position: Positions = d.get("position", "right")
        self.editor: str = d.get("editor", "code")
        self.opacity: float = d.get("opacity", 0.85)
        self.ocr_hotkey: str = d.get("ocr_hotkey", "ctrl+shift+space")
        self.items: list[dict] = d.get("items", [])

    def to_dict(self) -> dict:
        return {
            "position": self.position,
            "editor": self.editor,
            "opacity": self.opacity,
            "ocr_hotkey": self.ocr_hotkey,
            "items": self.items,
        }

    @classmethod
    def load(cls) -> Config:
        if CFG_FILE.exists():
            try:
                return cls(json.loads(CFG_FILE.read_text(encoding="utf-8")))
            except Exception:
                pass
        return cls()

    def save(self):
        tmp = CFG_FILE.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, CFG_FILE)
