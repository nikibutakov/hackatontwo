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
    "reason": "Брак: обнаружено — непропаянный элемент"
  }
}
```

- `polygon` — полигон маски (только у сегментационных моделей; у детекционных `null`).
- `status`: `ok` (годен) / `warning` (проверка оператора) / `reject` (брак).
- `reason` — человекочитаемое объяснение, показывается крупно на UI.

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
    "active": true
  }
]
```

`type`: `segmentation` (маски) / `detection` (рамки) / `mock` (заглушка).
`loaded: false` — веса не найдены или ML-зависимости не установлены.

---

## POST `/api/models/{id}/activate` — переключить модель

Переключает активную модель. Возвращает обновлённый список (как GET `/api/models`).

```bash
curl -X POST http://localhost:8000/api/models/pcb-deeppcb-yolov8s/activate
```

**Ошибка `404`** — модель с таким id не зарегистрирована; в `detail` перечислены доступные.

Нюанс: первая активация ещё не груженной модели может занять 1–3 секунды
(загрузка весов) — на демо прогревайте модель заранее.

---

## GET `/api/metrics` — метрики валидации

Отдаёт содержимое `ml/metrics.json` (заполняет ML-участник, формат — в ml/README.md).

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
  }
}
```

`placeholder: true` — цифры временные (заглушка для разработки фронтенда).
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
