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
            return self._detect_by_yolo(image_bgr)

        return self._detect_by_haar(image_bgr)

    def _detect_by_yolo(self, image_bgr: np.ndarray) -> list[tuple[tuple[int, int, int, int], float]]:
        '''
        YOLO 识别核心逻辑。
        参数：
            image_bgr: 输入的 BGR 图像。
        返回：
            boxes: 识别到的人脸框，格式为 ((x1, y1, x2, y2), confidence)。
                其中 x1, y1, x2, y2 为人脸框的左上角和右下角坐标，confidence 为人脸框的置信度。
        '''
        results = self.model.predict(image_bgr, conf=settings.detection_confidence, verbose=False)
        boxes: list[tuple[tuple[int, int, int, int], float]] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                confidence = float(box.conf[0].item())
                boxes.append(((int(x1), int(y1), int(x2), int(y2)), confidence))
        return boxes

    def _detect_by_haar(self, image_bgr: np.ndarray) -> list[tuple[tuple[int, int, int, int], float]]:
        '''
        Haar cascade 识别核心逻辑。
        参数：
            image_bgr: 输入的 BGR 图像。
        返回：
            boxes: 识别到的人脸框，格式为 ((x1, y1, x2, y2), confidence)。
                其中 x1, y1, x2, y2 为人脸框的左上角和右下角坐标，confidence 为人脸框的置信度。
        '''
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = self._fallback_detector.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=5)
        return [((int(x), int(y), int(x + w), int(y + h)), 0.4) for x, y, w, h in faces]
