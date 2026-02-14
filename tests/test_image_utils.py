from PIL import Image
from services.image_utils import embed_image_data, image_to_jpeg_bytes
import base64
from io import BytesIO


def make_test_image(size=(800, 600), color=(10, 120, 200)):
    return Image.new('RGB', size, color)


def test_image_to_jpeg_bytes_and_resize():
    img = make_test_image((1024, 600))
    b = image_to_jpeg_bytes(img, quality=80, max_size=512)
    # Should be JPEG bytes
    assert b[:2] == b'\xff\xd8'
    # Opening should succeed and size should be <= 512 on longest side
    im = Image.open(BytesIO(b))
    assert max(im.size) <= 512


def test_embed_image_data_returns_base64_jpeg():
    img = make_test_image((300, 200))
    s = embed_image_data(img)
    # Should decode to JPEG bytes
    decoded = base64.b64decode(s)
    assert decoded[:2] == b'\xff\xd8'
    im = Image.open(BytesIO(decoded))
    assert im.format == 'JPEG'