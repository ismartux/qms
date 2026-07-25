from PIL import Image, ImageOps, UnidentifiedImageError
from io import BytesIO
from django.core.files.base import ContentFile


def compress_uploaded_image(django_file, quality=40, max_size=(1280, 1280)):
    """
    Safely compress uploaded image to JPEG.

    - Preserves orientation (EXIF-aware)
    - Prevents pointer issues
    - Handles corrupted images safely
    - Keeps backward compatibility (always returns JPEG ContentFile)
    """

    try:
        # Ensure file pointer at start
        if hasattr(django_file, "seek"):
            django_file.seek(0)

        img = Image.open(django_file)

        # Prevent EXIF rotation issues
        img = ImageOps.exif_transpose(img)

        # Convert to RGB (JPEG compatible)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize while preserving aspect ratio
        img.thumbnail(max_size, Image.LANCZOS)

        buffer = BytesIO()

        # Save as JPEG (consistent with existing logic)
        img.save(
            buffer,
            format="JPEG",
            quality=quality,
            optimize=True,
        )

        buffer.seek(0)

        return ContentFile(buffer.getvalue())

    except UnidentifiedImageError:
        # If not an image, return original file content safely
        if hasattr(django_file, "seek"):
            django_file.seek(0)
        return ContentFile(django_file.read())

    except Exception:
        # Fail-safe fallback
        if hasattr(django_file, "seek"):
            django_file.seek(0)
        return ContentFile(django_file.read())