from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F

EMOTION_LABELS = ["happy", "neutral", "sad", "angry", "surprised"]


class EmotionAnalyzer:
    def __init__(self, model_path: str) -> None:
        self.model = None
        path = Path(model_path)
        if path.exists():
            self.model = torch.jit.load(str(path), map_location="cpu")
            self.model.eval()

    def predict(self, face_bgr: np.ndarray) -> tuple[str, float]:
        if self.model is not None:
            try:
                return self._predict_with_model(face_bgr)
            except Exception:
                # Fall back to heuristic pipeline when model inference fails.
                return self._predict_with_heuristic(face_bgr)

        return self._predict_with_heuristic(face_bgr)

    def _predict_with_model(self, face_bgr: np.ndarray) -> tuple[str, float]:
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        tensor = torch.from_numpy(gray).float() / 255.0
        tensor = F.interpolate(
            tensor.unsqueeze(0).unsqueeze(0),
            size=(48, 48),
            mode="bilinear",
            align_corners=False,
        )
        logits = self.model(tensor)
        probs = torch.softmax(logits, dim=1).squeeze(0)
        score, index = torch.max(probs, dim=0)
        return EMOTION_LABELS[int(index)], float(score.item())

    def _predict_with_heuristic(self, face_bgr: np.ndarray) -> tuple[str, float]:
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]

        upper = gray[: h // 2, :]
        lower = gray[h // 2 :, :]

        contrast = float(np.std(gray) / 128.0)
        lower_light = float(np.mean(lower) / 255.0)
        smile_signal = float((np.mean(lower[:, w // 4 : 3 * w // 4]) - np.mean(upper)) / 255.0)
        sharpness = float(min(1.0, cv2.Laplacian(gray, cv2.CV_64F).var() / 180.0))

        if smile_signal > 0.06 and contrast > 0.12:
            return "happy", min(0.95, 0.55 + smile_signal + contrast)
        if contrast < 0.07:
            return "neutral", 0.62
        if lower_light < 0.36:
            return "sad", min(0.9, 0.5 + (0.4 - lower_light))
        if sharpness > 0.65:
            return "surprised", min(0.93, 0.5 + sharpness / 2)
        return "angry", min(0.86, 0.52 + contrast)
