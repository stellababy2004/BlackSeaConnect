import io

from PIL import Image
import pillow_heif

import app as app_module


def test_heic_phone_photo_is_converted_to_jpeg():
    image = Image.new("RGB", (4032, 3024), (120, 160, 200))

    heif = pillow_heif.from_pillow(image)
    source = io.BytesIO()
    heif.save(source, quality=95)

    processed, mime_type = app_module._prepare_owner_property_image(
        source.getvalue(),
        "image/heic",
    )

    assert mime_type == "image/jpeg"

    with Image.open(io.BytesIO(processed)) as result:
        assert result.format == "JPEG"
        assert result.size == (2000, 1500)
        assert len(result.getexif()) == 0


def test_jpeg_metadata_is_removed():
    source = io.BytesIO()

    image = Image.new("RGB", (1200, 800), (90, 130, 170))
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "BlackSea Connect test metadata"

    image.save(
        source,
        format="JPEG",
        quality=95,
        exif=exif,
    )

    processed, mime_type = app_module._prepare_owner_property_image(
        source.getvalue(),
        "image/jpeg",
    )

    assert mime_type == "image/jpeg"

    with Image.open(io.BytesIO(processed)) as result:
        assert result.size == (800, 1200)
        assert len(result.getexif()) == 0
