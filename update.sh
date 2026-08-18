#!/usr/bin/env bash
# TrelloDeep — обновление (macOS / Linux). Запуск:  bash update.sh
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
echo "=== Обновление плагина TrelloDeep ==="
echo "Забираю свежую версию с GitHub..."
git pull
VENV_PY="$ROOT/.venv/bin/python"
if [ -x "$VENV_PY" ]; then
  echo "Обновляю зависимости..."
  "$VENV_PY" -m pip install --quiet --upgrade -r "$ROOT/mcp/requirements.txt"
else
  echo "Внимание: .venv не найден — запусти сначала: bash install.sh"
fi
echo
echo "=== ГОТОВО ==="
echo "Теперь полностью перезапусти Claude (Cmd+Q и открой заново),"
echo "и набери /mcp — обновления подхватятся."
