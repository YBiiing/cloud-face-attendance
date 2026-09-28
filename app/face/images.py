from io import BytesIO
import warnings

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.face.types import FaceError

MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 20_000_000


def decode_image(data: bytes, max_bytes: int = MAX_BYTES, max_pixels: int = MAX_PIXELS) -> np.ndarray:
    if not data:
        raise FaceError('INVALID_IMAGE')
    if len(data) > max_bytes:
        raise FaceError('IMAGE_TOO_LARGE')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in {'JPEG', 'PNG'}:
                    raise FaceError('UNSUPPORTED_IMAGE')
                if source.width * source.height > max_pixels:
                    raise FaceError('IMAGE_TOO_LARGE')
                source.verify()
            with Image.open(BytesIO(data)) as source:
                image = ImageOps.exif_transpose(source).convert('RGB')
                return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    except FaceError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise FaceError('INVALID_IMAGE') from None
