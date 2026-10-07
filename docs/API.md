# API — конечные точки

База: `http://<host>:8000/api`. Живая автодокументация (Swagger): `/docs`.

Все ответы — JSON. Координаты детекций — в пикселях **отправленного изображения**
(то, что вы прислали; фронтенд сам масштабирует под свой canvas).

---

## POST `/api/analyze` — полный анализ фотографии

Основной endpoint вкладки «Фото»: детекции + сводка + вердикт.

**Запрос:** `multipart/form-data`, поле `image` — файл JPEG/PNG.

```bash
curl -F "image=@board.jpg" http://localhost:8000/api/analyze
```

**Ответ `200`:**

```json
{
  "model": "hf-keremberke-yolov8m-seg",
  "time_ms": 87,
  "image_size": { "width": 1280, "height": 720 },
  "detections": [
    {
      "class_name": "dry_joint",
      "confidence": 0.81,
      "bbox": [412.5, 300.1, 495.2, 344.8],
      "polygon": [
        [412.5, 300.1], [495.2, 300.1],
        [495.2, 344.8], [412.5, 344.8]
      ]
    }
  ],
  "summary": { "total": 1, "by_class": { "dry_joint": 1 } },
  "verdict": {
    "status": "reject",
    "reason": "Брак: непропаянный элемент",
    "defects": [
      {
        "class_name": "dry_joint",
        "label": "непропаянный элемент",
        "category": "unsoldered",
        "count": 1,
        "area_pct": 0.4,
        "status": "reject",
        "note": null
      }
    ]
  },
  "tz_checklist": [
    { "id": "open_circuit", "title": "Разрыв на дорожках платы", "state": "not_checked",
      "found": [], "approximate": false,
      "note": "активная модель не распознаёт дефекты этого типа" },
    { "id": "unsoldered", "title": "Непропаянные элементы", "state": "reject",
      "found": ["непропаянный элемент"], "approximate": false, "note": null },
    { "id": "component_damage", "title": "Повреждение компонентов", "state": "clear",
      "found": [], "approximate": true,
      "note": "приближённо: модель распознаёт «неправильная установка компонента»" },
    { "id": "other", "title": "Иные дефекты", "state": "clear",
      "found": [], "approximate": false, "note": null }
  ]
}
```

- `tz_checklist` — **проверка по пунктам задания 4**, в порядке текста ТЗ.
  `state`: `reject` / `warning` — найдены дефекты (худший статус);
  `clear` — модель этот пункт проверяет, дефектов нет;
  `not_checked` — у активной модели нет ни одного класса этого пункта
  (честнее, чем «не найдено»). `approximate: true` — пункт закрыт
  классом-приближением. Пункты и привязка классов — `config.TZ_CATEGORIES`
  и поле `category` в `config.VERDICT_RULES`.

- `polygon` — полигон маски (только у сегментационных моделей; у детекционных `null`).
- `status`: `ok` (годен) / `warning` (проверка оператора) / `reject` (брак).
- `reason` — человекочитаемое объяснение, показывается крупно на UI.
- `defects` — разбор вердикта по классам, самые серьёзные первыми:
  `label` — русское название (для UI), `area_pct` — суммарная площадь
  дефектов класса в % от кадра (по маске, у детекции — по рамке),
  `note` — почему предупреждение повышено до брака (сработал порог).

**Правила вердикта** (`config.VERDICT_RULES`): у класса базовая критичность
`severity` и необязательные пороги `reject_count` / `reject_area_pct`,
повышающие `warning` до `reject`. Итог — худший статус среди классов.
Неизвестный класс — `warning`. Примеры `reason`:

| Детекции | `status` | `reason` |
|---|---|---|
| 2 × open_circuit | reject | Брак: разрыв дорожки ×2 |
| 1 × mouse_bite | warning | Требует проверки оператора: дефект края дорожки («мышиный укус») |
| 3 × mouse_bite | reject | Брак: дефект края дорожки («мышиный укус») — 3 шт. (порог брака — 3) |
| pcb_damage на 2% кадра | reject | Брак: повреждение платы — 2% площади (порог брака — 1%) |
| dry_joint + spur | reject | Брак: непропаянный элемент. Также проверить: заусенец дорожки |

**Ошибки:**

| Код | Когда | `detail` |
|---|---|---|
| 400 | пустой файл / не изображение | «Файл не является изображением (JPEG/PNG)» |
| 503 | модель не загрузилась | описание ошибки + подсказка про ml/README.md |

---

## POST `/api/frame` — кадр живого потока

Облегчённый вариант для камеры: ответ минимальный, детекции **сглажены**
(анти-мерцание: дефект подтверждается в `CONFIRM_FRAMES` кадрах подряд
и держится `HOLD_MS` после пропадания — параметры в `backend/app/config.py`).

Протокол клиента: следующий кадр отправлять **только после ответа**
на предыдущий — темп потока подстраивается под скорость модели сам.

**Запрос:** идентичен `/api/analyze` (multipart, поле `image`).

**Ответ `200`:**

```json
{
  "model": "hf-keremberke-yolov8m-seg",
  "time_ms": 41,
  "detections": [
    {
      "class_name": "short_circuit",
      "confidence": 0.66,
      "bbox": [610.0, 420.3, 700.1, 455.9],
      "polygon": null
    }
  ]
}
```

Коды ошибок — как у `/api/analyze`.

---

## GET `/api/models` — список моделей

**Ответ `200`:**

```json
[
  {
    "id": "hf-keremberke-yolov8m-seg",
    "type": "segmentation",
    "description": "Бейзлайн с Hugging Face: dry_joint, ...",
    "loaded": true,
    "active": true,
    "error": null
  }
]
```

`type`: `segmentation` (маски) / `detection` (рамки) / `mock` (заглушка).
`loaded: false` — веса ещё не загружены в память (запрос их **не** грузит, отвечает мгновенно).
Активная модель грузится при старте сервера, остальные — при активации.
`error` — текст ошибки последней попытки загрузки (веса не найдены, нет ML-зависимостей), иначе `null`.

---

## POST `/api/models/{id}/activate` — переключить модель

Переключает активную модель. Возвращает обновлённый список (как GET `/api/models`).

```bash
curl -X POST http://localhost:8000/api/models/pcb-deeppcb-yolov8s/activate
```

**Ошибка `404`** — модель с таким id не зарегистрирована; в `detail` перечислены доступные.
**Ошибка `503`** — веса не загрузились; активной **остаётся прежняя** модель, в `detail` — причина.

Нюанс: первая активация ещё не груженной модели может занять 1–3 секунды
(запрос ждёт загрузки весов, зато первый кадр после переключения не тормозит).
Сглаживание потока камеры при переключении сбрасывается.

---

## GET `/api/metrics` — метрики валидации

Отдаёт содержимое `ml/metrics.json` (заполняет ML-участник, формат — в ml/README.md)
плюс справочники для вкладки «Метрики».

**Ответ `200`:**

```json
{
  "models": {
    "hf-keremberke-yolov8m-seg": {
      "name": "YOLOv8m-seg (бейзлайн Hugging Face)",
      "baseline": true,
      "map50_box": 0.568,
      "map50_mask": 0.557,
      "dataset": "keremberke/pcb-defect-segmentation (189 фото)",
      "per_class": { "dry_joint": 0.60 },
      "placeholder": true
    }
  },
  "class_info": {
    "dry_joint": { "label": "непропаянный элемент", "category": "unsoldered", "approximate": false }
  },
  "tz_categories": [
    { "id": "open_circuit", "title": "Разрыв на дорожках платы" },
    { "id": "unsoldered", "title": "Непропаянные элементы" },
    { "id": "component_damage", "title": "Повреждение компонентов" },
    { "id": "other", "title": "Иные дефекты" }
  ]
}
```

`placeholder: true` — цифры временные (заглушка для разработки фронтенда).
`class_info` — для каждого класса из `per_class` всех моделей: русское название,
пункт ТЗ и признак приближения (из `config.VERDICT_RULES`).
`tz_categories` — пункты ТЗ в порядке текста задания (`config.TZ_CATEGORIES`).
Ключи моделей в `models` должны совпадать с `id` в `/api/models` — по ним
вкладка помечает активную модель.
**Ошибка `404`** — `ml/metrics.json` не найден.

---

## GET `/api/health` — живость

```json
{
  "status": "ok",
  "active_model": "mock",
  "mock_mode": true,
  "ml_dependencies": false
}
```

Фронтенд опрашивает каждые 10 секунд (индикатор в шапке). `mock_mode: true` —
сервер работает без ML и возвращает фейковые детекции.

---

## Схемы данных (сводка)

| Сущность | Поля | Где определена |
|---|---|---|
| `Detection` | class_name, confidence, bbox[x1,y1,x2,y2], polygon? | `backend/app/schemas.py` |
| `Verdict` | status (ok/warning/reject), reason | там же |
| `Summary` | total, by_class | там же |
| `AnalyzeResponse` | model, time_ms, image_size, detections, summary, verdict | там же |
| `FrameResponse` | model, time_ms, detections | там же |

При изменении схем обновляйте этот файл И `backend/app/schemas.py` одновременно.
