"""Декодирование загруженных картинок (backend/app/images.py)."""

import io

import pytest
from PIL import Image

from backend.app.images import InvalidImageError, decode_image

ORIENTATION_TAG = 0x0112


def jpeg_with_orientation(orientation: int) -> bytes:
    """JPEG 200×100: красный квадрат в левом верхнем углу, EXIF Orientation задан."""
    image = Image.new("RGB", (200, 100), (0, 0, 255))
    image.paste((255, 0, 0), (0, 0, 20, 20))
    exif = image.getexif()
    exif[ORIENTATION_TAG] = orientation
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", exif=exif.tobytes())
    return buffer.getvalue()


def is_red(pixel) -> bool:
    r, g, b = pixel
    return r > 200 and g < 80 and b < 80


def test_exif_rotation_applied():
    # Orientation=6: телефон снял "на боку", для показа повернуть на 90° по часовой.
    # Так фото покажет браузер — и такую же картинку должна получить модель.
    image = decode_image(jpeg_with_orientation(6))
    assert image.size == (100, 200)
    # левый верхний угол исходника после поворота по часовой — в правом верхнем
    assert is_red(image.getpixel((95, 5)))
    assert not is_red(image.getpixel((5, 5)))


def test_normal_orientation_unchanged():
    image = decode_image(jpeg_with_orientation(1))
    assert image.size == (200, 100)
    assert is_red(image.getpixel((5, 5)))


def test_image_without_exif():
    buffer = io.BytesIO()
    Image.new("RGBA", (64, 32), (10, 20, 30, 255)).save(buffer, "PNG")
    image = decode_image(buffer.getvalue())
    assert image.size == (64, 32)
    assert image.mode == "RGB"   # RGBA и прочее приводится к RGB для модели


def test_empty_file_rejected():
    with pytest.raises(InvalidImageError, match="Пустой файл"):
        decode_image(b"")


def test_not_an_image_rejected():
    with pytest.raises(InvalidImageError, match="не является изображением"):
        decode_image(b"%PDF-1.4 definitely not a picture")
