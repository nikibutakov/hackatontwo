# ML-часть: датасеты, модели, метрики

Папка закреплена за **ML-участником**. Здесь всё про модели: скачивание бейзлайна,
подготовку датасета, обучение своей модели и метрики.

## Структура папки

```
ml/
├── download_hf_model.py     # скачать бейзлайн с Hugging Face (+ --check)
├── train_yolo.py            # обучение своей модели на DeepPCB
├── pcb.yaml                 # конфиг датасета (проверить пути и классы!)
├── metrics.json             # метрики для вкладки «Метрики» (ОБНОВЛЯТЬ после обучения)
├── requirements-ml.txt      # ultralytics, huggingface_hub
├── data/                    # датасеты (в git НЕ попадают, .gitignore)
│   └── deeppcb/             # DeepPCB — раскладка ниже
├── weights/                 # веса моделей (в git НЕ попадают)
│   ├── hf_yolov8m_seg.pt    # бейзлайн (появится после download_hf_model.py)
│   └── pcb_yolov8s.pt       # своя модель (появится после train_yolo.py)
└── runs/                    # логи обучения YOLO (в git НЕ попадают)
```

## Шаг 1 — бейзлайн с Hugging Face (30 минут, сделать ПЕРВЫМ)

```bash
pip install -r ml/requirements-ml.txt
python ml/download_hf_model.py          # скачает веса в ml/weights/
python ml/download_hf_model.py --check  # проверка совместимости и классов
```

Модель: `keremberke/yolov8m-pcb-defect-segmentation` — сегментация, 4 класса
(dry_joint, incorrect_installation, pcb_damage, short_circuit), обучена на 189 фото.
mAP@0.5 ≈ 0.57 — бейзлайн для сравнения и домен «реальных фото» (важно для камеры).

Если `--check` упал: карточка модели просит старый пин
`ultralytics==8.0.23 + ultralyticsplus` — ставьте его в **отдельный venv**,
чтобы не сломать обучение (обучение идёт на новом ultralytics).

После проверки: запускайте сервер с `USE_MOCK=false` — фронтенд получает настоящие
детекции.

## Шаг 2 — датасет DeepPCB (своя модель)

Источник: Kaggle, ищите **«DeepPCB»** или «PCB defect detection» — берите версию,
где разметка **уже в YOLO-формате** (txt-файлы с нормализованными bbox).
6 классов: missing_hole, mouse_bite, **open_circuit** (разрыв дорожки — главное из ТЗ),
short, spur, spurious_copper.

Раскладка (пути проверяются в `pcb.yaml`):

```
ml/data/deeppcb/
├── images/
│   ├── train/   # ~80%
│   ├── val/     # ~15%
│   └── test/    # ~5% (не трогать до финальной проверки!)
└── labels/      # те же подпапки, txt-файлы с теми же именами, что картинки
```

Если скачалась версия «вырезка + шаблон» (пары картинок) — для обучения берите
дефектные вырезки; сверьте порядок классов с файлом классов датасета и поправьте
`pcb.yaml` при расхождении.

## Шаг 3 — обучение

```bash
python ml/train_yolo.py --model-size s --epochs 80
```

- GPU (Colab T4 или локальная карта): 30–60 минут.
- `--device cpu` работает, но дольше.
- Веса автоматически копируются в `ml/weights/pcb_yolov8s.pt`.

После обучения обязательно:
1. Переписать метрики из `ml/runs/pcb_train/results.csv` (и `results.png`) в
   `ml/metrics.json` — структура ниже.
2. Добавить модель в `MODEL_REGISTRY` в `backend/app/config.py`.

## Формат metrics.json (для вкладки «Метрики»)

```json
{
  "models": {
    "pcb-deeppcb-yolov8s": {
      "name": "YOLOv8s, наша дообученная",
      "baseline": false,
      "map50_box": 0.789,
      "dataset": "DeepPCB (1500 изображений)",
      "per_class": { "open_circuit": 0.82, "short": 0.75 },
      "placeholder": false
    }
  }
}
```

`baseline: true/false` — чем модель помечается на вкладке (бейзлайн HF / наша).
Поля `map50_mask` и `per_class` — опциональны.

## Опционально (если останется время)

- **Объединённая модель**: датасет HF (COCO) сконвертировать в YOLO и смёрджить с
  DeepPCB → одна модель на 10 классов. Делать только после того, как обе базовые
  модели работают.
- **ONNX-экспорт** для ускорения CPU-инференса на живом потоке.
