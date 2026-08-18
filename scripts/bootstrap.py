#!/usr/bin/env python3
"""SessionStart-хук для маркетплейс-установки: ставит python-зависимости плагина
в постоянную папку CLAUDE_PLUGIN_DATA/pylibs (переживает обновления). Идемпотентен:
переустанавливает только если requirements.txt новее отметки.

Устанавливает через `pip install --target` (плоская папка, не зависит от версии
Python) — сервер видит их через PYTHONPATH из plugin.json."""
import os
import subprocess
import sys
from pathlib import Path

data = Path(os.environ.get("CLAUDE_PLUGIN_DATA", "."))
root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent))
target = data / "pylibs"
req = root / "mcp" / "requirements.txt"
marker = data / ".deps_ok"

if not req.exists():
    print("bootstrap: requirements.txt не найден, пропускаю")
    sys.exit(0)

up_to_date = marker.exists() and marker.stat().st_mtime >= req.stat().st_mtime
if up_to_date and target.exists():
    print("trello-deep: зависимости уже установлены")
    sys.exit(0)

target.mkdir(parents=True, exist_ok=True)
print("trello-deep: устанавливаю зависимости (однократно)...")
subprocess.run(
    [sys.executable, "-m", "pip", "install", "--quiet", "--upgrade",
     "--target", str(target), "-r", str(req)],
    check=False,
)
marker.write_text("ok", encoding="utf-8")
print("trello-deep: зависимости готовы ->", target)
