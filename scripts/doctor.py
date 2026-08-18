#!/usr/bin/env python3
"""Диагностика установки плагина TrelloDeep. Запусти и пришли вывод команде.

Windows:  .venv\\Scripts\\python.exe scripts\\doctor.py
macOS:    .venv/bin/python scripts/doctor.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OK, FAIL, WARN = "[ OK ]", "[FAIL]", "[WARN]"
problems = []

def line(status, msg, hint=""):
    print(f"{status} {msg}")
    if status == FAIL and hint:
        print(f"        -> {hint}")
        problems.append(hint)

print("=" * 60)
print(" TrelloDeep — диагностика установки")
print(f" Папка проекта: {ROOT}")
print("=" * 60)

# 1. Python
v = sys.version_info
if v >= (3, 10):
    line(OK, f"Python {v.major}.{v.minor}.{v.micro}")
else:
    line(FAIL, f"Python {v.major}.{v.minor}", "Нужен Python 3.10+. Переустанови и запусти install заново.")

# 2. venv (запущены ли мы из .venv)
in_venv = "venv" in sys.executable.lower() or (ROOT / ".venv") in Path(sys.executable).parents
line(OK if in_venv else WARN, f"Интерпретатор: {sys.executable}",
     )
if not in_venv:
    print("        (лучше запускать из .venv — см. шапку файла)")

# 3. Зависимости
for mod, pip in [("mcp","mcp"),("httpx","httpx"),("dotenv","python-dotenv"),("pymupdf","pymupdf"),("docx","python-docx")]:
    try:
        __import__(mod)
        line(OK, f"Зависимость: {pip}")
    except Exception:
        line(FAIL, f"Зависимость не найдена: {pip}",
             "Запусти установщик заново (install.ps1 / install.sh) — он ставит зависимости.")

# 4. .env
env = ROOT / ".env"
key = tok = None
if env.exists():
    try:
        from dotenv import dotenv_values
        vals = dotenv_values(env)
        key, tok = vals.get("TRELLO_KEY"), vals.get("TRELLO_TOKEN")
    except Exception:
        pass
    if key and tok:
        line(OK, f".env найден, ключ и токен заданы (токен …{tok[-6:]})")
    else:
        line(FAIL, ".env есть, но TRELLO_KEY/TRELLO_TOKEN пустые",
             "Открой .env и впиши ключ и свой токен, или запусти установщик заново.")
else:
    line(FAIL, ".env не найден", "Скопируй .env.example в .env и впиши ключ/токен (или запусти установщик).")

# 5. Токен рабочий?
if key and tok:
    try:
        import httpx
        r = httpx.get("https://api.trello.com/1/members/me", params={"key": key, "token": tok}, timeout=20)
        if r.status_code == 200:
            line(OK, f"Токен рабочий (Trello: {r.json().get('fullName','?')})")
        elif r.status_code == 401:
            line(FAIL, "Токен отклонён (401)", "Перевыпусти токен и впиши заново, затем запусти установщик.")
        else:
            line(WARN, f"Trello ответил {r.status_code}")
    except Exception as e:
        line(WARN, f"Не удалось проверить токен (сеть?): {e}")

# 6. server.py + инструменты
try:
    sys.path.insert(0, str(ROOT / "mcp"))
    import server, asyncio
    tools = [t.name for t in asyncio.run(server.mcp.list_tools())]
    if len(tools) >= 6:
        line(OK, f"Сервер стартует, инструментов: {len(tools)}")
    else:
        line(WARN, f"Сервер стартует, но инструментов только {len(tools)}")
except Exception as e:
    line(FAIL, f"server.py не запускается: {e}", "Проверь зависимости выше.")

# 7. .mcp.json
mcp = ROOT / ".mcp.json"
if mcp.exists():
    try:
        cfg = json.loads(mcp.read_text(encoding="utf-8"))
        srv = cfg.get("mcpServers", {}).get("trello-deep", {})
        cmd = Path(srv.get("command","")); arg = Path((srv.get("args") or [""])[0])
        okc = cmd.exists(); oka = arg.exists()
        if okc and oka:
            line(OK, ".mcp.json корректен (пути к python и server.py существуют)")
        else:
            line(FAIL, ".mcp.json есть, но пути неверны",
                 f"python найден: {okc}, server.py найден: {oka}. Запусти установщик заново.")
    except Exception as e:
        line(FAIL, f".mcp.json повреждён: {e}", "Запусти установщик заново.")
else:
    line(FAIL, ".mcp.json не найден в корне проекта", "Запусти установщик (install.ps1 / install.sh).")

print("=" * 60)
if problems:
    print(f" ИТОГ: есть проблемы ({len(problems)}). Сверху отмечены [FAIL] и что делать.")
else:
    print(" ИТОГ: всё в порядке на стороне файлов и токена.")
    print(" Если /mcp всё равно не показывает trello-deep:")
    print("  1) Открой в Claude ИМЕННО папку Trello-Card-Work как проект.")
    print("  2) Полностью закрой Claude (из трея / Cmd+Q) и открой заново.")
    print("  3) /mcp — не путать с 'Directory/Коннекторы' (там штатный Trello, не наш плагин).")
print("=" * 60)
