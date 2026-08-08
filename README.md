# Trello Deep

MCP-плагин, закрывающий четыре пробела штатного Trello-коннектора:
**вложения** (список + скачивание содержимого), **комментарии** и **историю
изменений**. Всё, что приложено к карточке файлом (бренд-гайды, PDF, docx, zip
с макетами), становится видимым агенту.

> Статус: этап 1 — реализован `trello_fetch_attachment` (скачивание вложений).
> Остальные инструменты — по плану этапов (см. ТЗ).

## Установка

```bash
python -m venv .venv
.venv/Scripts/pip install -r mcp/requirements.txt   # Windows
# source .venv/bin/activate && pip install -r mcp/requirements.txt  # macOS/Linux
```

## Доступы (ключ и токен)

1. **API key** — https://trello.com/power-ups/admin (создать Power-Up, взять ключ).
2. **Токен** — открыть в браузере, подставив свой ключ:

   ```
   https://trello.com/1/authorize?expiration=30days&scope=read,write&response_type=token&name=TrelloDeep&key=ВАШ_КЛЮЧ
   ```

Затем:

```bash
cp .env.example .env      # и вписать TRELLO_KEY / TRELLO_TOKEN
```

**Безопасность:**
- `.env` уже в `.gitignore` — в репозиторий не попадёт.
- `expiration=never` не использовать. Ставить `30days` и перевыпускать.
- Скоуп `account` не запрашивать.
- Отзыв токена при компрометации: https://trello.com/my/account → Applications → Revoke.

## Смоук-тест (этап 1)

```bash
.venv/Scripts/python.exe scripts/probe.py https://trello.com/c/KdZqQd8E
```

Скачивает все вложения карточки, сверяет размеры с API, распаковывает zip.

## Инструменты

| Инструмент | Назначение | Права | Статус |
|---|---|---|---|
| `trello_fetch_attachment` | Скачать вложение на диск, вернуть путь | read | ✅ этап 1 |
| `trello_list_attachments` | Список вложений карточки | read | план |
| `trello_get_comments` | Комментарии карточки | read | план |
| `trello_get_card_history` | История изменений | read | план |
| `trello_add_comment` | Добавить комментарий (с подтверждением) | write | план |
| `trello_upload_attachment` | Прикрепить файл (с подтверждением) | write | план |
