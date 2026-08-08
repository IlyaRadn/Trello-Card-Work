#!/usr/bin/env python3
"""
Смоук-тест этапа 1: скачивание вложений.

Проверяет главный (и единственный неочевидный) риск: доезжает ли файл до
файловой системы. Берёт карточку, перечисляет её вложения через Trello API,
скачивает каждое инструментом сервера trello_fetch_attachment, сверяет размеры
с тем, что заявляет API, и распаковывает zip.

Запуск (из корня репозитория, с активным .env или переменными окружения):
    .venv/Scripts/python.exe scripts/probe.py https://trello.com/c/KdZqQd8E

Токену достаточно scope=read.
"""

import asyncio
import os
import sys
import zipfile
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Даём импортировать mcp/server.py как модуль.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mcp"))
load_dotenv(_ROOT / ".env")

import server  # noqa: E402

API = "https://api.trello.com/1"
OUT = _ROOT / "trello_files"


async def list_attachments(card: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=60) as client:
        return await server._get_json(
            client, f"/cards/{card}/attachments", fields="all"
        )


async def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("Укажи URL или id карточки")
    if not os.environ.get("TRELLO_KEY") or not os.environ.get("TRELLO_TOKEN"):
        sys.exit("Нет TRELLO_KEY/TRELLO_TOKEN. Создай .env из .env.example.")

    card = server._normalize_card(sys.argv[1])
    print(f"Карточка: {card}\n")

    atts = await list_attachments(card)
    uploads = [a for a in atts if a.get("isUpload")]
    links = [a for a in atts if not a.get("isUpload")]
    print(f"Вложений: {len(uploads)} файлов, {len(links)} ссылок\n")

    ok, fail = 0, 0
    saved: list[Path] = []
    for a in uploads:
        expected = a.get("bytes") or 0
        try:
            res = await server.trello_fetch_attachment(card, a["id"], str(OUT))
            p = Path(res["path"])
            actual = p.stat().st_size
            match = "OK  " if actual == expected else "SIZE MISMATCH"
            if actual == expected:
                ok += 1
            else:
                fail += 1
            saved.append(p)
            print(f"  {match} {p.name:<48} {actual:>10} / {expected} B")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"  FAIL {a.get('fileName','?')}: {e}")

    for a in links:
        print(f"  [ссылка] {a.get('name')} -> {a.get('url')}")

    # Распаковка архивов — сразу видно, что внутри.
    for p in saved:
        if p.suffix.lower() == ".zip":
            target = OUT / (p.stem + "_unpacked")
            try:
                with zipfile.ZipFile(p) as z:
                    z.extractall(target)
                names = sorted(os.listdir(target))
                print(f"\n  {p.name} распакован -> {len(names)} объектов")
                for n in names[:20]:
                    print(f"     {n}")
            except Exception as e:  # noqa: BLE001
                print(f"  не смог распаковать {p.name}: {e}")

    print(f"\nИтог: {ok} OK, {fail} проблем. Файлы в {OUT}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
