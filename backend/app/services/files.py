import hashlib
from io import BytesIO

from PIL import Image


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_thumbnail(data: bytes, max_size: int = 400) -> bytes:
    with Image.open(BytesIO(data)) as image:
        image = image.convert("RGB")
        image.thumbnail((max_size, max_size))
        output = BytesIO()
        image.save(output, format="JPEG", quality=80)
        return output.getvalue()
