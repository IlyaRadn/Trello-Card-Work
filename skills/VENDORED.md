# Сторонние скиллы (vendored)

Часть скиллов в `skills/` скопирована из внешних репозиториев для работы «из
коробки». Лицензии сохранены — файлы `LICENSE` / `LICENSE.txt` лежат внутри
соответствующих папок. При обновлении сверяйтесь с источником.

| Скилл | Источник | Коммит | Лицензия |
|---|---|---|---|
| `canvas-design` | [anthropics/skills](https://github.com/anthropics/skills) · `skills/canvas-design` | `f6656c1` | Apache-2.0 — см. `canvas-design/LICENSE.txt` |
| `brandkit` | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) · `skills/brandkit` | `e988add` | MIT — см. `brandkit/LICENSE` |
| `taste-skill` | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) · `skills/taste-skill` | `e988add` | MIT — см. `taste-skill/LICENSE` |

`canvas-design/canvas-fonts/` — шрифты под OFL (лицензии `*-OFL.txt` рядом).

## Собственные скиллы (наши)

- `trello-attachments` — работа с вложениями/комментариями/историей карточки.
- `trello-design` — двухэтапный процесс: изучение карточки → ТЗ → (после апрува) дизайн.

## Как это используется

- **brandkit** — генерация бренд-борда картинкой (лого/символ/мокапы/цвет/типографика).
- **canvas-design** — постер-арт / эффектная обложка (PNG/PDF) с набором шрифтов.
- **taste-skill** (`design-taste-frontend`) — дизайн-качество для web/HTML (дайлы, анти-slop правила).

Навык `trello-design` (Этап 2) ссылается на них для отрисовки.
