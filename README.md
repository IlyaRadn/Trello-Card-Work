# Trello Deep

MCP-плагин, закрывающий четыре пробела штатного Trello-коннектора:
**вложения** (список + скачивание содержимого), **комментарии** и **историю
изменений**. Всё, что приложено к карточке файлом (бренд-гайды, PDF, docx, zip
с макетами, картинки), становится видимым агенту — скачанные на диск файлы
читаются нативно, в т.ч. картинки.

Формат плагина одинаков для Cowork и Claude Code — один MCP-сервер работает
в обеих средах.

## Инструменты

| Инструмент | Назначение | Права |
|---|---|---|
| `trello_fetch_attachment` | Скачать вложение на диск, вернуть путь | read |
| `trello_list_attachments` | Список вложений (файлы/ссылки по `is_upload`) | read |
| `trello_get_comments` | Комментарии карточки | read |
| `trello_get_card_history` | История изменений | read |
| `trello_add_comment` | Добавить комментарий (с подтверждением) | write |
| `trello_upload_attachment` | Прикрепить файл (с подтверждением) | write |

`card` принимается в любом виде: полный URL, shortLink (`KdZqQd8E`) или id.
`trello_fetch_attachment` возвращает **путь**, а не содержимое (вложения бывают
по 20+ МБ — base64 забил бы контекст). Удаления в плагине нет намеренно.

## Установка (локально / для разработки)

```bash
git clone https://github.com/IlyaRadn/Trello-Card-Work.git
cd Trello-Card-Work
python -m venv .venv
.venv/Scripts/pip install -r mcp/requirements.txt      # Windows
# source .venv/bin/activate && pip install -r mcp/requirements.txt   # macOS/Linux
```

## Доступы (ключ и токен)

1. **API key** — https://trello.com/power-ups/admin (создать Power-Up, взять ключ).
2. **Токен** — открыть в браузере, подставив свой ключ:

   ```
   https://trello.com/1/authorize?expiration=30days&scope=read,write&response_type=token&name=TrelloDeep&key=ВАШ_КЛЮЧ
   ```

Затем создать `.env` из шаблона и вписать значения:

```bash
cp .env.example .env      # вписать TRELLO_KEY и TRELLO_TOKEN
```

## Установка для команды (Windows) — быстрый способ

Для коллег, кто хочет пользоваться плагином у себя. Нужен **Python 3.10+**,
**Git** и **Claude** (Claude Code / десктоп) на своём компьютере.

1. Скачать репозиторий:
   ```bash
   git clone https://github.com/IlyaRadn/Trello-Card-Work.git
   ```
2. Запустить установщик (создаст venv, поставит зависимости, спросит токен,
   пропишет `.env` и `.mcp.json` с путями под этот компьютер):
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```
   Скрипт даст ссылку для выпуска **своего** токена — открой её, нажми Allow,
   вставь токен обратно в консоль. Ключ можно оставить общий (Enter).
3. **Открыть эту папку в Claude как проект** (или скопировать созданный
   `.mcp.json` в папку своего рабочего проекта Claude).
4. Полностью перезапустить Claude → `/mcp` → появится `trello-deep`.

> У каждого коллеги — **свой токен** (действия идут от его имени, доступ по его
> правам). Общий — только API key. `.env` и `.mcp.json` в `.gitignore`, в
> репозиторий не попадают.

## Подключение как плагина Claude Code (вручную)

Манифест `.claude-plugin/plugin.json` уже описывает MCP-сервер. Сервер берёт
`TRELLO_KEY`/`TRELLO_TOKEN` из системных переменных окружения, а при их
отсутствии — из `.env` в корне репозитория. Для локального использования
достаточно заполнить `.env`.

> Сервер запускается командой `python`. Убедись, что зависимости из
> `mcp/requirements.txt` установлены в то окружение Python, которое найдётся
> в `PATH` (либо активируй venv перед запуском Claude Code).

## Смоук-тест

```bash
.venv/Scripts/python.exe scripts/probe.py https://trello.com/c/KdZqQd8E
```

Скачивает все вложения карточки, сверяет размеры с API, распаковывает zip.

## Безопасность

- Ключ и токен читаются только из окружения / `.env`. Хардкод недопустим.
- `.env` в `.gitignore` — в репозиторий не попадёт.
- `expiration=never` не использовать. Ставить `30days` и перевыпускать.
- Скоуп `account` не запрашивать.
- Пишущие инструменты (`add_comment`, `upload_attachment`) необратимы и не
  срабатывают без `confirm=true` — агент обязан получить явное согласие.
- **Отзыв токена при компрометации:** https://trello.com/my/account →
  Applications → Revoke.

## Лицензия

MIT — см. [LICENSE](LICENSE).
