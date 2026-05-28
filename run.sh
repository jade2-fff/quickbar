#!/usr/bin/env bash
# QuickBar Linux/macOS 启动脚本
cd "$(dirname "$0")"
exec python3 game_bar.py "$@"
