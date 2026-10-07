# HANDOFF: подключение 4 моделей к серверу

Веса лежат в `ml/weights/` (в git не входят, передаются отдельно):
`hf_yolov8m_seg.pt`, `hf_yolov8s_deeppcb.pt`, `hf_yolov8m_dspcbsd.pt`, `pcb_yolov8s.pt`

## 1. backend/app/config.py — MODEL_REGISTRY заменить на:

```python
MODEL_REGISTRY: list[dict] = [
    {"id": "pku-yolov8s-ours", "type": "detection",
     "path": "ml/weights/pcb_yolov8s.pt",
     "description": "Наша: PKU-corrected, mAP50 0.943, честный board-disjoint сплит"},
    {"id": "hf-janani-deeppcb-yolov8s", "type": "detection",
     "path": "ml/weights/hf_yolov8s_deeppcb.pt",
     "description": "DeepPCB: 6 классов, mAP50 0.985 (в домене датасета)"},
    {"id": "hf-janani-dspcbsd-yolov8m", "type": "detection",
     "path": "ml/weights/hf_yolov8m_dspcbsd.pt",
     "description": "DsPCBSD+: 9 классов ('иные дефекты' из ТЗ)"},
    {"id": "hf-keremberke-yolov8m-seg", "type": "segmentation",
     "path": "ml/weights/hf_yolov8m_seg.pt",
     "description": "Сегментация, домен реальных фото (камера), mAP50 0.57"},
]
ACTIVE_MODEL = "pku-yolov8s-ours"
```

## 2. Там же — алиасы классов (новая константа) + дополнить VERDICT_RULES

Модели отдают разные имена одних и тех же дефектов; сервер нормализует их
в канонические (ключи VERDICT_RULES). В model_manager.py после инференса:
`det["class_name"] = CLASS_ALIASES.get(det["class_name"], det["class_name"])`.

```python
CLASS_ALIASES = {
    # keremberke (с заглавных букв)
    "Dry_joint": "dry_joint", "Incorrect_installation": "incorrect_installation",
    "PCB_damage": "pcb_damage", "Short_circuit": "short_circuit",
    # Janani-V DeepPCB
    "copper": "spurious_copper", "mousebite": "mouse_bite", "open": "open_circuit",
    "pin-hole": "missing_hole",
    # Janani-V DsPCBSD+ (классы в чекпойнте безымянные, порядок подтверждён
    # inspector.py автора модели)
    "0": "short", "1": "spur", "2": "spurious_copper", "3": "open_circuit",
    "4": "mouse_bite", "5": "hole_breakout", "6": "conductor_scratch",
    "7": "conductor_foreign_object", "8": "base_material_foreign_object",
}
```

В VERDICT_RULES добавить (серьёзность — по inspector.py DsPCBSD+):

```python
    "hole_breakout":               "warning",  # смещение отверстия
    "conductor_scratch":           "warning",  # царапина на дорожке
    "conductor_foreign_object":    "warning",  # загрязнение дорожки
    "base_material_foreign_object":"warning",  # включение в основании
```

## 3. В RU_LABELS (verdict.py) добавить:

```python
    "hole_breakout": "смещение отверстия",
    "conductor_scratch": "царапина на дорожке",
    "conductor_foreign_object": "загрязнение дорожки",
    "base_material_foreign_object": "постороннее включение в основании",
```

## 4. Запуск с реальными моделями

`USE_MOCK=false uvicorn backend.app.main:app --port 8000`
(или переменная окружения в docker-compose). Проверка: GET /api/health —
`active_model: pku-yolov8s-ours`, `mock_mode: false`; GET /api/models —
4 модели; POST /api/models/{id}/activate — переключение.