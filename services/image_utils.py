from io import BytesIO
from PIL import Image
import base64
from typing import Optional


def image_to_jpeg_bytes(img: Image.Image, quality: int = 85, max_size: Optional[int] = None) -> bytes:
    """Return JPEG bytes for the given PIL Image, optionally resizing to max_size on the longest side."""
    if max_size is not None:
        ratio = max_size / max(img.size)
        if ratio < 1:
            new_size = tuple(int(dim * ratio) for dim in img.size)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
    buffer = BytesIO()
    img.convert("RGB").save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def embed_image_data(img: Image.Image, src: Optional[str] = None, *, max_size: int = 512, quality: int = 85) -> str:
    """Return a base64-encoded JPEG representation of `img` (string, no header).

    This always returns inline base64 (no presigned URL). The caller is
    responsible for adding the `data:image/jpeg;base64,` header if needed.
    """
    img_bytes = image_to_jpeg_bytes(img, quality=quality, max_size=max_size)
    return base64.b64encode(img_bytes).decode('ascii')
