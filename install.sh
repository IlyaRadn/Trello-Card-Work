#!/usr/bin/env bash
# TrelloDeep — установщик для команды (macOS / Linux)
# Запуск:  bash install.sh
#
# Делает всё сам: создаёт venv, ставит зависимости, спрашивает токен,
# пишет .env и .mcp.json с правильными путями под этот компьютер.

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "=== Установка плагина TrelloDeep (macOS / Linux) ==="
echo "Папка проекта: $ROOT"
echo

# 1. Python 3
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 не найден."
  echo "Установи: https://www.python.org/downloads/  (или на macOS:  brew install python)"
  exit 1
fi
echo "Python: $(python3 --version)"

# 2. Виртуальное окружение
VENV_PY="$ROOT/.venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  echo "Создаю виртуальное окружение (.venv)..."
  python3 -m venv "$ROOT/.venv"
fi

# 3. Зависимости
echo "Ставлю зависимости..."
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet -r "$ROOT/mcp/requirements.txt"
echo "Зависимости установлены."
echo

# 4. Ключ и токен
DEFAULT_KEY="19182c221233719e958c9591183d3cee"
read -r -p "Trello API KEY (просто Enter = общий ключ команды): " KEY
KEY="${KEY:-$DEFAULT_KEY}"

echo
echo "Теперь выпусти СВОЙ токен: открой ссылку, нажми Allow, скопируй токен:"
echo "https://trello.com/1/authorize?expiration=30days&scope=read,write&response_type=token&name=TrelloDeep&key=$KEY"
echo
read -r -p "Вставь свой Trello TOKEN: " TOKEN
if [ -z "$TOKEN" ]; then
  echo "Токен пустой — установка прервана."
  exit 1
fi

# 5. .env
printf 'TRELLO_KEY=%s\nTRELLO_TOKEN=%s\n' "$KEY" "$TOKEN" > "$ROOT/.env"
echo ".env создан."

# 6. .mcp.json с абсолютными путями под этот компьютер
cat > "$ROOT/.mcp.json" <<EOF
{
  "mcpServers": {
    "trello-deep": {
      "command": "$VENV_PY",
      "args": ["$ROOT/mcp/server.py"]
    }
  }
}
EOF
echo ".mcp.json создан: $ROOT/.mcp.json"

echo
echo "=== ГОТОВО ==="
echo "Осталось:"
echo "  1. Открой папку $ROOT в Claude как проект"
echo "     (или скопируй .mcp.json в папку своего рабочего проекта Claude)."
echo "  2. Полностью перезапусти Claude."
echo "  3. Набери /mcp — должен появиться trello-deep с 6 инструментами."
