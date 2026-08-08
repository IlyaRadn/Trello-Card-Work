"""
Trello Deep — MCP-сервер.

Закрывает четыре пробела штатного Trello-коннектора: вложения (список +
скачивание), комментарии, история изменений. На этапе 1 реализован только
`trello_fetch_attachment` — единственный неочевидный риск во всей затее:
доезжает ли скачанный файл до файловой системы, которую видит агент.

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
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# .env ищем рядом с этим файлом и на уровень выше (корень репозитория).
_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE / ".env")
load_dotenv(_HERE.parent / ".env")

API = "https://api.trello.com/1"
KEY = os.environ.get("TRELLO_KEY")
TOKEN = os.environ.get("TRELLO_TOKEN")

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


if __name__ == "__main__":
    mcp.run()
