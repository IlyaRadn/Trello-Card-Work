"""
Trello Deep — MCP-сервер.

Закрывает четыре пробела штатного Trello-коннектора: вложения (список +
скачивание), комментарии, история изменений. Плюс два пишущих инструмента
(комментарий, загрузка файла) с обязательным подтверждением.

Инструменты:
  - trello_fetch_attachment   скачать вложение на диск (read)
  - trello_list_attachments   список вложений          (read)
  - trello_get_comments       комментарии карточки      (read)
  - trello_get_card_history   история изменений         (read)
  - trello_add_comment        добавить комментарий      (write, confirm)
  - trello_upload_attachment  прикрепить файл           (write, confirm)

Ключ и токен читаются ИСКЛЮЧИТЕЛЬНО из переменных окружения
TRELLO_KEY и TRELLO_TOKEN (или из .env рядом). Хардкод недопустим.
"""

import asyncio
import mimetypes
import os
import re
from pathlib import Path
from urllib.parse import quote

import httpx
from dotenv import dotenv_values, load_dotenv
from mcp.server.fastmcp import FastMCP

# .env ищем рядом с этим файлом и на уровень выше (корень репозитория).
_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE / ".env")
load_dotenv(_HERE.parent / ".env")

# Значения из .env как явный фолбэк. Нужно на случай запуска плагином:
# .mcp.json может подставить пустой TRELLO_KEY="", а load_dotenv (без override)
# пустую переменную окружения из .env не перезапишет. Системная переменная
# приоритетна; при её отсутствии или пустоте берём значение из .env.
_DOTENV = {**dotenv_values(_HERE.parent / ".env"), **dotenv_values(_HERE / ".env")}

API = "https://api.trello.com/1"
KEY = os.environ.get("TRELLO_KEY") or _DOTENV.get("TRELLO_KEY")
TOKEN = os.environ.get("TRELLO_TOKEN") or _DOTENV.get("TRELLO_TOKEN")

mcp = FastMCP("trello-deep")


# --------------------------------------------------------------------------
# Вспомогательное
# --------------------------------------------------------------------------

class TrelloError(Exception):
    """Ошибка, текст которой безопасно показать агенту/пользователю."""


def _require_creds() -> None:
    if not KEY or not TOKEN:
        raise TrelloError(
            "Не заданы TRELLO_KEY и/или TRELLO_TOKEN. "
            "Скопируй .env.example в .env и подставь ключ и токен."
        )


def _auth_header() -> dict[str, str]:
    # Trello отключил авторизацию через query-параметры для скачивания
    # вложений в январе 2021. Работает только этот заголовок — используем
    # его единообразно на всех эндпоинтах.
    return {
        "Authorization": f'OAuth oauth_consumer_key="{KEY}", oauth_token="{TOKEN}"'
    }


def _normalize_card(card: str) -> str:
    """URL карточки -> shortLink. shortLink и полный id пропускает как есть."""
    m = re.search(r"/c/([A-Za-z0-9]+)", card)
    if m:
        return m.group(1)
    return card.strip()


async def _api_get(path: str, **params):
    """Разовый GET JSON: создаёт клиент, вызывает _get_json. Для читающих тулов."""
    _require_creds()
    async with httpx.AsyncClient(timeout=60) as client:
        return await _get_json(client, path, **params)


async def _api_post(path: str, *, data: dict | None = None, files: dict | None = None):
    """Разовый POST к Trello (пишущие тулы). Авторизация через key/token
    query-параметрами — для JSON-эндпоинтов это допустимо и надёжно для POST."""
    _require_creds()
    params = {"key": KEY, "token": TOKEN}
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
        r = await client.post(f"{API}{path}", params=params, data=data, files=files)
        _raise_for_trello(r, path)
        return r.json()


async def _get_json(client: httpx.AsyncClient, path: str, **params):
    """GET JSON с ретраями на 429 (экспоненциальная задержка, до 3 попыток)."""
    delay = 1.0
    for attempt in range(3):
        r = await client.get(f"{API}{path}", params=params, headers=_auth_header())
        if r.status_code == 429 and attempt < 2:
            await asyncio.sleep(delay)
            delay *= 2
            continue
        _raise_for_trello(r, path)
        return r.json()
    _raise_for_trello(r, path)  # последний ответ, если все попытки — 429


def _raise_for_trello(r: httpx.Response, what: str) -> None:
    if r.status_code == 401:
        raise TrelloError(
            "401 Unauthorized. Проверь TRELLO_KEY/TRELLO_TOKEN и что токен "
            "выпущен со scope, включающим read. Скачивание работает только "
            "с OAuth-заголовком (не с query-параметрами)."
        )
    if r.status_code == 404:
        raise TrelloError(f"404 Not Found: {what}. Проверь id карточки/вложения.")
    if r.status_code == 429:
        raise TrelloError("429 Rate limit: превышена частота запросов к Trello.")
    r.raise_for_status()


# --------------------------------------------------------------------------
# Этап 1: скачивание вложения
# --------------------------------------------------------------------------

@mcp.tool()
async def trello_fetch_attachment(
    card: str,
    attachment_id: str,
    dest_dir: str = "./trello_files",
) -> dict:
    """Скачивает вложение карточки Trello в файловую систему и возвращает ПУТЬ к файлу.

    Возвращает путь, а не содержимое: вложения бывают по 20+ МБ и забили бы
    контекст. Прочитай файл по возвращённому пути своими штатными средствами
    (в т.ч. картинки — их видно нативно).

    Аргументы:
        card: URL карточки, shortLink (напр. "KdZqQd8E") или полный id.
        attachment_id: id вложения (см. trello_list_attachments).
        dest_dir: куда сохранить. По умолчанию "./trello_files".

    Возвращает при файле:  {"path", "bytes", "mime", "is_link": false}
    Возвращает при ссылке: {"is_link": true, "url", "name", "path": null}
        (isUpload=false — это внешняя ссылка на Google Drive/YouTube и т.п.,
         скачивать нечего).
    """
    _require_creds()
    card = _normalize_card(card)

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
        meta = await _get_json(
            client, f"/cards/{card}/attachments/{attachment_id}", fields="all"
        )

        # Внешняя ссылка — качать нечего.
        if not meta.get("isUpload", False):
            return {
                "is_link": True,
                "url": meta.get("url"),
                "name": meta.get("name"),
                "path": None,
            }

        file_name = meta.get("fileName") or meta.get("name") or attachment_id
        # Имена содержат пробелы и скобки ("TLC_banners (4).zip") — обязательно quote().
        url = f"{API}/cards/{card}/attachments/{attachment_id}/download/{quote(file_name)}"

        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / file_name

        size = await _stream_download(client, url, path)

    mime = meta.get("mimeType") or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return {
        "path": str(path),
        "bytes": size,
        "mime": mime,
        "is_link": False,
    }


async def _stream_download(client: httpx.AsyncClient, url: str, path: Path) -> int:
    """Потоковое скачивание с ретраями на 429. Возвращает размер в байтах."""
    delay = 1.0
    for attempt in range(3):
        try:
            written = 0
            async with client.stream("GET", url, headers=_auth_header()) as r:
                if r.status_code == 429 and attempt < 2:
                    await r.aclose()
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                _raise_for_trello(r, str(path))
                with open(path, "wb") as f:
                    async for chunk in r.aiter_bytes(1 << 16):
                        f.write(chunk)
                        written += len(chunk)
            return written
        except httpx.TransportError as e:
            if attempt < 2:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            raise TrelloError(f"Сеть: не удалось скачать {path.name}: {e}") from e
    raise TrelloError(f"Не удалось скачать {path.name} после 3 попыток (429).")


# --------------------------------------------------------------------------
# Этап 2: читающие инструменты (list / comments / history)
# --------------------------------------------------------------------------

@mcp.tool()
async def trello_list_attachments(card: str) -> list[dict]:
    """Возвращает список вложений карточки Trello.

    Файлы и внешние ссылки разделяются по признаку `is_upload`:
    is_upload=true — загруженный файл (можно скачать trello_fetch_attachment),
    is_upload=false — внешняя ссылка (Google Drive/YouTube и т.п.).

    Аргументы:
        card: URL карточки, shortLink (напр. "KdZqQd8E") или полный id.

    Возвращает массив объектов: {id, name, mime, bytes, is_upload, url, date}.
    """
    card = _normalize_card(card)
    atts = await _api_get(f"/cards/{card}/attachments", fields="all")
    out = []
    for a in atts:
        is_upload = bool(a.get("isUpload"))
        out.append(
            {
                "id": a.get("id"),
                "name": a.get("fileName") if is_upload else a.get("name"),
                "mime": a.get("mimeType"),
                "bytes": a.get("bytes"),
                "is_upload": is_upload,
                "url": a.get("url"),
                "date": a.get("date"),
            }
        )
    return out


@mcp.tool()
async def trello_get_comments(card: str, limit: int = 1000) -> list[dict]:
    """Возвращает комментарии карточки Trello (то, чего не отдаёт штатный коннектор).

    Аргументы:
        card: URL карточки, shortLink или полный id.
        limit: сколько комментариев вернуть. По умолчанию 1000.
            (Дефолт Trello — 50, поэтому для полной выборки указываем явно.)

    Возвращает массив объектов: {author, date, text}, от новых к старым.
    """
    card = _normalize_card(card)
    actions = await _api_get(
        f"/cards/{card}/actions", filter="commentCard", limit=limit
    )
    return [
        {
            "author": a.get("memberCreator", {}).get("fullName", "—"),
            "date": a.get("date"),
            "text": a.get("data", {}).get("text", ""),
        }
        for a in actions
    ]


@mcp.tool()
async def trello_get_card_history(
    card: str,
    limit: int = 1000,
    types: str | None = None,
) -> list[dict]:
    """Возвращает историю изменений карточки Trello.

    Видно, когда карточку двигали между списками, кто менял срок и требования.

    Аргументы:
        card: URL карточки, shortLink или полный id.
        limit: сколько событий вернуть. По умолчанию 1000.
        types: необязательный фильтр по типам действий через запятую
            (напр. "updateCard,commentCard"). По умолчанию — все типы.

    Возвращает массив объектов: {type, date, who, data}, от новых к старым.
    Полезное в data для перемещений: listBefore / listAfter.
    """
    card = _normalize_card(card)
    params = {"filter": types or "all", "limit": limit}
    actions = await _api_get(f"/cards/{card}/actions", **params)
    return [
        {
            "type": a.get("type"),
            "date": a.get("date"),
            "who": a.get("memberCreator", {}).get("fullName", "—"),
            "data": a.get("data", {}),
        }
        for a in actions
    ]


# --------------------------------------------------------------------------
# Этап 3: пишущие инструменты (необратимы силами плагина — требуют confirm)
# --------------------------------------------------------------------------
#
# Удаления в плагине нет намеренно: инструментов, стирающих карточки,
# комментарии или вложения, здесь быть не должно. Поэтому всё, что публикуется,
# плагин откатить не может. Оба инструмента защищены параметром confirm:
# без confirm=True они НЕ пишут, а возвращают предпросмотр действия. Агент
# обязан сначала показать этот предпросмотр пользователю и получить явное «да».

COMMENT_MAX = 16384          # лимит Trello на длину комментария
MAX_UPLOAD = 250 * 1024 * 1024  # жёсткий максимум вложения Trello (платный тариф)


@mcp.tool()
async def trello_add_comment(card: str, text: str, confirm: bool = False) -> dict:
    """Публикует комментарий на карточке Trello от имени владельца токена.

    ВНИМАНИЕ: действие необратимо силами плагина (удаления в плагине нет).
    Упоминания через @username порождают реальные уведомления живым людям —
    не рассылай их без явной просьбы пользователя.

    Механизм подтверждения: при confirm=False (по умолчанию) инструмент НИЧЕГО
    не публикует, а возвращает предпросмотр. Покажи предпросмотр пользователю,
    получи явное согласие и только тогда вызови повторно с confirm=True.

    Аргументы:
        card: URL карточки, shortLink или полный id.
        text: текст комментария (поддерживается Markdown). Длиннее 16384
            символов — режется на несколько комментариев, а не теряется.
        confirm: True — публиковать. False — только предпросмотр.

    Возвращает при confirm=False: {"pending_confirmation": true, ...предпросмотр}.
    Возвращает при confirm=True:  {"posted": N, "comments": [{id, date, author}]}.
    """
    _require_creds()
    if not text or not text.strip():
        raise TrelloError("Пустой текст комментария.")
    card_n = _normalize_card(card)
    chunks = [text[i : i + COMMENT_MAX] for i in range(0, len(text), COMMENT_MAX)]

    if not confirm:
        return {
            "pending_confirmation": True,
            "action": "add_comment",
            "card": card_n,
            "parts": len(chunks),
            "chars": len(text),
            "mentions": bool(re.search(r"(?:^|\s)@[\w-]+", text)),
            "preview": text[:500],
            "note": (
                "Комментарий НЕ опубликован. Необратимо силами плагина. "
                "@упоминания шлют реальные уведомления людям. "
                "После явного согласия пользователя вызови снова с confirm=True."
            ),
        }

    created = []
    for chunk in chunks:
        res = await _api_post(
            f"/cards/{card_n}/actions/comments", data={"text": chunk}
        )
        created.append(
            {
                "id": res.get("id"),
                "date": res.get("date"),
                "author": res.get("memberCreator", {}).get("fullName"),
            }
        )
    return {"posted": len(created), "comments": created}


@mcp.tool()
async def trello_upload_attachment(
    card: str,
    file_path: str,
    name: str | None = None,
    confirm: bool = False,
) -> dict:
    """Прикрепляет локальный файл к карточке Trello.

    ВНИМАНИЕ: действие необратимо силами плагина (удаления в плагине нет).

    Механизм подтверждения: при confirm=False (по умолчанию) инструмент НИЧЕГО
    не прикрепляет, а возвращает предпросмотр. Покажи его пользователю, получи
    явное согласие и только тогда вызови повторно с confirm=True.

    Аргументы:
        card: URL карточки, shortLink или полный id.
        file_path: путь к локальному файлу (проверяется до отправки).
        name: имя вложения. По умолчанию — имя файла.
        confirm: True — прикреплять. False — только предпросмотр.

    Лимит размера зависит от тарифа рабочего пространства: 10 МБ на бесплатном,
    до 250 МБ на платных. Файл больше 250 МБ отклоняется до отправки.

    Возвращает при confirm=False: {"pending_confirmation": true, ...предпросмотр}.
    Возвращает при confirm=True:  {id, name, bytes, mime, url}.
    """
    _require_creds()
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        raise TrelloError(f"Файл не найден: {file_path}")
    size = p.stat().st_size
    if size > MAX_UPLOAD:
        raise TrelloError(
            f"Файл {size / 1e6:.1f} МБ превышает максимум Trello 250 МБ."
        )
    card_n = _normalize_card(card)
    att_name = name or p.name

    if not confirm:
        return {
            "pending_confirmation": True,
            "action": "upload_attachment",
            "card": card_n,
            "file": str(p),
            "name": att_name,
            "bytes": size,
            "note": (
                f"Файл НЕ прикреплён. Необратимо силами плагина. "
                f"Размер {size / 1e6:.1f} МБ (на бесплатном тарифе лимит 10 МБ, "
                f"на платных до 250 МБ). После согласия пользователя вызови "
                f"снова с confirm=True."
            ),
        }

    mime = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    with open(p, "rb") as fh:
        res = await _api_post(
            f"/cards/{card_n}/attachments",
            data={"name": att_name},
            files={"file": (att_name, fh, mime)},
        )
    return {
        "id": res.get("id"),
        "name": res.get("name"),
        "bytes": res.get("bytes"),
        "mime": res.get("mimeType"),
        "url": res.get("url"),
    }


if __name__ == "__main__":
    mcp.run()
