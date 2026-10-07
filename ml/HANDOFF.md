# HANDOFF v2: подключение 4 моделей к серверу

> **Статус: применено в ветке `feature/handoff-v2`** (тем же кодом, что ниже,
> плюс поле `imgsz` в реестре — размер входа при инференсе теперь берётся
> из реестра: наша PKU-модель обучена на 960, остальные на 640).
> Бэкендеру: посмотреть ветку (тесты 43/43 зелёные, приёмка из п.6 пройдена)
> и вмержить в dev. Этот документ остаётся описанием изменений.

> Обновлён под новый формат `VERDICT_RULES` (словари с `severity`/`category`)
> и тесты бэкенда. v1 больше не применять — форматы не совпадут.

Веса лежат в `ml/weights/` (в git не входят, передаются флешкой/облаком):

| Файл | Модель | Классы в чекпойнте |
|---|---|---|
| `pcb_yolov8s.pt` | наша, PKU-corrected | `missing_hole, mouse_bite, open_circuit, short, spur, spurious_copper` |
| `hf_yolov8s_deeppcb.pt` | Janani-V, DeepPCB | `copper, mousebite, open, pin-hole, short, spur` |
| `hf_yolov8m_dspcbsd.pt` | Janani-V, DsPCBSD+ | `0..8` (безымянные — маппинг ниже) |
| `hf_yolov8m_seg.pt` | keremberke, сегментация | `Dry_joint, Incorrect_installation, PCB_damage, Short_circuit` |

## 1. `backend/app/config.py` — MODEL_REGISTRY и ACTIVE_MODEL

Заменить единственную запись реестра на четыре и переключить активную модель:

```python
MODEL_REGISTRY: list[dict] = [
    {"id": "pku-yolov8s-ours", "type": "detection",
     "path": "ml/weights/pcb_yolov8s.pt",
     "description": "Наша: PKU-corrected, mAP50 0.943 (board-disjoint), 11 мс/кадр"},
    {"id": "hf-janani-deeppcb-yolov8s", "type": "detection",
     "path": "ml/weights/hf_yolov8s_deeppcb.pt",
     "description": "DeepPCB: 6 классов дорожек, mAP50 0.985 в домене датасета"},
    {"id": "hf-janani-dspcbsd-yolov8m", "type": "detection",
     "path": "ml/weights/hf_yolov8m_dspcbsd.pt",
     "description": "DsPCBSD+: 9 классов, закрывает «иные дефекты» из ТЗ"},
    {"id": "hf-keremberke-yolov8m-seg", "type": "segmentation",
     "path": "ml/weights/hf_yolov8m_seg.pt",
     "description": "Сегментация, домен реальных фото (камера), mAP50 0.57"},
]

ACTIVE_MODEL = "pku-yolov8s-ours"
```

## 2. `config.py` — новая константа `CLASS_ALIASES` (положить после VERDICT_RULES)

Модели отдают разные имена одних и тех же дефектов. Нормализация — в канонические
имена (ключи VERDICT_RULES и RU_LABELS). Порядок безымянных классов DsPCBSD+
подтверждён `inspector.py` автора модели.

```python
# ---------- Алиасы имён классов ----------
# Каноническое имя <- как класс называется в чекпойнте конкретной модели.
CLASS_ALIASES: dict[str, str] = {
    # keremberke (с заглавных букв)
    "Dry_joint": "dry_joint",
    "Incorrect_installation": "incorrect_installation",
    "PCB_damage": "pcb_damage",
    "Short_circuit": "short_circuit",
    # Janani-V DeepPCB
    "copper": "spurious_copper",
    "mousebite": "mouse_bite",
    "open": "open_circuit",
    "pin-hole": "missing_hole",
    # Janani-V DsPCBSD+ (имена-цифры; порядок подтверждён inspector.py автора)
    "0": "short",
    "1": "spur",
    "2": "spurious_copper",
    "3": "open_circuit",
    "4": "mouse_bite",
    "5": "hole_breakout",
    "6": "conductor_scratch",
    "7": "conductor_foreign_object",
    "8": "base_material_foreign_object",
}
```

## 3. `backend/app/model_manager.py` — применить алиасы в `YoloModel.predict`

В цикле сборки детекций строку

```python
"class_name": str(names[int(result.boxes.cls[i])]),
```

заменить на

```python
"class_name": config.CLASS_ALIASES.get(
    str(names[int(result.boxes.cls[i])]),
    str(names[int(result.boxes.cls[i])]),
),
```

(или через промежуточную переменную `raw` — как удобнее; важно одно: каждое
имя класса проходит через алиасы до того, как уйдёт в вердикт и фронтенд).
MockModel не трогать — он уже отдаёт канонические имена.

## 4. `config.py` — дополнить VERDICT_RULES четырьмя классами DsPCBSD+

Ваш формат (severity + пороги + category). Все четыре — честный пример пункта
ТЗ «иные дефекты на усмотрение разработчика», поэтому категория "other":

```python
    # --- Janani-V DsPCBSD+ («иные дефекты» из ТЗ) ---
    "hole_breakout":                {"severity": "warning", "reject_count": 3, "category": "other"},  # отверстие смещено с площадки
    "conductor_scratch":            {"severity": "warning", "reject_area_pct": 1.0, "category": "other"},  # царапина на дорожке
    "conductor_foreign_object":     {"severity": "warning", "category": "other"},  # загрязнение проводника
    "base_material_foreign_object": {"severity": "warning", "category": "other"},  # включение в основании платы
```

## 5. `backend/app/verdict.py` — дополнить RU_LABELS

```python
    "hole_breakout": "смещение отверстия",
    "conductor_scratch": "царапина на дорожке",
    "conductor_foreign_object": "загрязнение проводника",
    "base_material_foreign_object": "постороннее включение в основании",
```

## 6. Запуск и приёмка

```bash
set USE_MOCK=false
uvicorn backend.app.main:app --port 8000
```

- `GET /api/health` → `active_model: "pku-yolov8s-ours"`, `mock_mode: false`
- `GET /api/models` → 4 модели, у активной `"loaded": true`
- `POST /api/analyze` с `examples/10_open_circuit_01.jpg` → детекции
  `open_circuit` (наша модель отдаёт канонические имена), вердикт «Брак»,
  пункт ТЗ «Разрыв на дорожках платы» закрыт
- Переключиться на `hf-janani-dspcbsd-yolov8m` и прогнать ту же картинку:
  классы должны приходить ЧИТАЕМЫМИ (`short`, `mouse_bite`...), не `0..8` —
  это и есть проверка, что алиасы работают
- `pytest` — все 43 теста должны остаться зелёными
