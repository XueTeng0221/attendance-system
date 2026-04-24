import cv2
import numpy as np


class ImageDecodeError(ValueError):
    pass


def decode_image_bytes(raw: bytes) -> np.ndarray:
    if not raw:
        raise ImageDecodeError("empty image payload")

    nparr = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ImageDecodeError("unable to decode image")
    return img


def crop_face(image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = box
    h, w = image.shape[:2]
    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(x1 + 1, min(x2, w))
    y2 = max(y1 + 1, min(y2, h))
    return image[y1:y2, x1:x2]
