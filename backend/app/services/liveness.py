import cv2
import numpy as np


class LivenessDetector:
    def score(self, face_bgr: np.ndarray) -> float:
        '''
        活体检测分数评估。
        参数：
        face_bgr: 人脸图像，BGR格式。
        返回：
        分数，范围在[0, 1]之间。
        '''
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)

        # 模糊
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        blur_norm = min(1.0, blur_score / 140.0)

        # FFT 频谱和纹理归一化
        fft = np.fft.fftshift(np.fft.fft2(gray))
        magnitude = np.log(np.abs(fft) + 1)
        h, w = magnitude.shape
        center = magnitude[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
        high_freq = magnitude.mean() - center.mean()
        texture_norm = np.clip((high_freq + 2.0) / 6.0, 0.0, 1.0)
        
        # 颜色方差和归一化
        color_var = np.std(face_bgr.astype(np.float32), axis=(0, 1)).mean()
        color_norm = np.clip(color_var / 52.0, 0.0, 1.0)

        score = 0.45 * blur_norm + 0.35 * texture_norm + 0.2 * color_norm
        return float(np.clip(score, 0.0, 1.0))
