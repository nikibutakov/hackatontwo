# ============================================================
# РОЛЬ: Backend-разработчик
#
# ЧТО ЗДЕСЬ: декодирование загруженной картинки — один код для
# /api/analyze и /api/frame.
#
# ПОЧЕМУ НЕ ПРОСТО Image.open: телефон часто сохраняет снимок "на боку"
# и записывает поворот в EXIF (тег Orientation). Браузер этот тег
# учитывает и показывает фото ровно, а PIL — нет. Без поворота модель
# получила бы повёрнутую картинку, а рамки легли бы не туда на экране.
# exif_transpose применяет поворот к пикселям, и координаты детекций
# совпадают с тем, что видит пользователь.
# ============================================================

import io

from PIL import Image, ImageOps


class InvalidImageError(ValueError):
    """Файл пустой или не является изображением."""


def decode_image(raw: bytes) -> Image.Image:
    """Байты файла -> RGB-картинка с применённым EXIF-поворотом."""
    if not raw:
        raise InvalidImageError("Пустой файл")
    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)  # без EXIF возвращает картинку как есть
        return image.convert("RGB")
    except Exception as exc:
        raise InvalidImageError("Файл не является изображением (JPEG/PNG)") from exc
