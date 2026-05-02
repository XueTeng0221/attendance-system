from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


class FaceDetector:
    def __init__(self) -> None:
        self.model = None
        self._fallback_detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        model_path = Path(settings.face_detector_model)
        if YOLO is not None and model_path.exists():
            self.model = YOLO(str(model_path))

    def detect(self, image_bgr: np.ndarray) -> list[tuple[tuple[int, int, int, int], float]]:
        if self.model is not None:
            return self._yolo(image_bgr, settings.detection_confidence)
        return self._haar(image_bgr)

    def detect_tiled(
        self,
        image_bgr: np.ndarray,
        conf: float,
        tile_size: int = 640,
        overlap: float = 0.25,
        nms_iou: float = 0.40,
    ) -> list[tuple[tuple[int, int, int, int], float]]:
        """分块检测大图，解决小脸在缩放后消失的问题。"""
        if self.model is None:
            return self._haar(image_bgr)

        h, w = image_bgr.shape[:2]
        # 图像足够小时直接单次推理
        if h <= tile_size * 1.5 and w <= tile_size * 1.5:
            return self._yolo(image_bgr, conf)

        step = max(1, int(tile_size * (1 - overlap)))
        raw: list[tuple[tuple[int, int, int, int], float]] = []

        for y0 in range(0, h, step):
            for x0 in range(0, w, step):
                x2 = min(x0 + tile_size, w)
                y2 = min(y0 + tile_size, h)
                x1 = max(0, x2 - tile_size)
                y1 = max(0, y2 - tile_size)

                tile = image_bgr[y1:y2, x1:x2]
                for (bx1, by1, bx2, by2), score in self._yolo(tile, conf):
                    raw.append(((x1 + bx1, y1 + by1, x1 + bx2, y1 + by2), score))

        return self._nms(raw, iou_threshold=nms_iou)

    # ------------------------------------------------------------------ #

    def _yolo(self, image_bgr: np.ndarray, conf: float) -> list[tuple[tuple[int, int, int, int], float]]:
        results = self.model.predict(image_bgr, conf=conf, verbose=False)
        boxes: list[tuple[tuple[int, int, int, int], float]] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                boxes.append(((int(x1), int(y1), int(x2), int(y2)), float(box.conf[0].item())))
        return boxes

    def _haar(self, image_bgr: np.ndarray) -> list[tuple[tuple[int, int, int, int], float]]:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = self._fallback_detector.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=5)
        return [((int(x), int(y), int(x + w), int(y + h)), 0.4) for x, y, w, h in faces]

    @staticmethod
    def _nms(
        boxes: list[tuple[tuple[int, int, int, int], float]],
        iou_threshold: float = 0.40,
    ) -> list[tuple[tuple[int, int, int, int], float]]:
        if not boxes:
            return []
        rects = [[x1, y1, x2 - x1, y2 - y1] for (x1, y1, x2, y2), _ in boxes]
        scores = [float(s) for _, s in boxes]
        indices = cv2.dnn.NMSBoxes(rects, scores, score_threshold=0.0, nms_threshold=iou_threshold)
        if len(indices) == 0:
            return []
        flat = indices.flatten() if hasattr(indices, "flatten") else list(indices)
        return [boxes[i] for i in flat]
