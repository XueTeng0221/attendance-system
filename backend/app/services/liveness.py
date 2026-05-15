import cv2
import numpy as np

from app.core.config import settings


class LivenessDetector:
    """单帧 + 多帧组合的启发式活体检测。

    单帧分项：模糊度、外环高频纹理、颜色方差、摩尔纹（屏幕翻拍特征）。
    多帧分项：相邻帧像素差作为运动证据、亮度方差体现自然光照变化。
    """

    def score_single(self, face_bgr: np.ndarray) -> dict:
        '''
        单帧活体打分。返回总分与各分项，便于前端展示与排查。
        '''
        if face_bgr is None or face_bgr.size == 0:
            return {"score": 0.0, "blur": 0.0, "texture": 0.0, "color": 0.0, "moire": 0.0}

        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)

        # 锐度：Laplacian 方差与 Sobel 梯度均值的几何平均，覆盖低对比度场景。
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        sobel_mag = float(np.mean(np.abs(cv2.Sobel(gray, cv2.CV_64F, 1, 1, ksize=3))))
        blur_norm = float(np.clip(min(laplacian_var / 140.0, sobel_mag / 18.0), 0.0, 1.0))

        # 频域：fftshift 后中心是低频，外环是高频。真实自然脸高频比例更高。
        fft = np.fft.fftshift(np.fft.fft2(gray))
        magnitude = np.log(np.abs(fft) + 1.0)
        h, w = magnitude.shape
        cy, cx = h // 2, w // 2

        yy, xx = np.ogrid[:h, :w]
        radius = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
        max_radius = float(min(cy, cx))
        center_mask = radius <= max_radius * 0.18
        outer_mask = radius >= max_radius * 0.55
        center_mean = float(magnitude[center_mask].mean()) if center_mask.any() else 0.0
        outer_mean = float(magnitude[outer_mask].mean()) if outer_mask.any() else 0.0
        high_freq = outer_mean - center_mean
        texture_norm = float(np.clip((high_freq + 4.5) / 6.0, 0.0, 1.0))

        # 颜色方差：屏幕翻拍后通道方差通常变窄。
        color_var = float(np.std(face_bgr.astype(np.float32), axis=(0, 1)).mean())
        color_norm = float(np.clip(color_var / 52.0, 0.0, 1.0))

        # 摩尔纹：在中频环带寻找规则峰，越显著说明越像屏幕。
        mid_band_mask = (radius >= max_radius * 0.30) & (radius <= max_radius * 0.55)
        if mid_band_mask.any():
            mid_band = magnitude[mid_band_mask]
            mid_mean = float(mid_band.mean())
            mid_std = float(mid_band.std()) + 1e-6
            mid_max = float(mid_band.max())
            moire_strength = (mid_max - mid_mean) / mid_std
            # 经验阈值：自然脸通常 < 4，屏幕翻拍 > 5；做一次平滑归一。
            moire_norm = float(np.clip((moire_strength - 3.5) / 4.0, 0.0, 1.0))
        else:
            moire_norm = 0.0

        score = 0.30 * blur_norm + 0.30 * texture_norm + 0.15 * color_norm + 0.25 * (1.0 - moire_norm)
        return {
            "score": float(np.clip(score, 0.0, 1.0)),
            "blur": blur_norm,
            "texture": texture_norm,
            "color": color_norm,
            "moire": moire_norm,
        }

    def score_sequence(self, faces_bgr: list[np.ndarray]) -> dict:
        '''
        多帧活体打分。需要至少 settings.liveness_min_frames 帧脸图，
        利用相邻帧的像素差证明确有自然运动，并组合单帧分项。
        '''
        valid = [face for face in faces_bgr if face is not None and face.size > 0]
        if len(valid) < settings.liveness_min_frames:
            return {
                "score": 0.0,
                "passed": False,
                "reason": "多帧采集不足",
                "single_avg": 0.0,
                "motion": 0.0,
                "brightness": 0.0,
            }

        # 单帧均分
        per_frame = [self.score_single(face) for face in valid]
        single_avg = float(np.mean([item["score"] for item in per_frame]))

        # 把所有人脸 resize 到统一尺寸再做差，避免因检测框抖动放大“运动”。
        target_size = (96, 96)
        normalized = [cv2.resize(face, target_size).astype(np.float32) / 255.0 for face in valid]
        diffs = []
        for prev, curr in zip(normalized, normalized[1:]):
            diffs.append(float(np.mean(np.abs(curr - prev))))
        motion_raw = float(np.mean(diffs)) if diffs else 0.0
        motion_norm = float(np.clip(motion_raw / 0.05, 0.0, 1.0))

        # 亮度方差变化：贴住静态照片时几乎为 0。
        brightness_series = [float(np.mean(item)) for item in normalized]
        brightness_var = float(np.var(brightness_series))
        brightness_norm = float(np.clip(brightness_var / 0.002, 0.0, 1.0))

        final = 0.55 * single_avg + 0.30 * motion_norm + 0.15 * brightness_norm
        moire_avg = float(np.mean([item["moire"] for item in per_frame]))

        # 按策略：亮度方差分数 > 0 或摩尔纹分数 > 0.02，直接拒绝。
        passed = False
        reason = ""
        if brightness_norm > 0 and moire_avg > 0.02:
            reason = "疑似屏幕翻拍"
        else:
            passed = (
                motion_raw >= settings.liveness_motion_threshold
                and final >= settings.liveness_threshold
            )
            if motion_raw < settings.liveness_motion_threshold:
                reason = "未检测到自然运动，疑似照片/静态画面"
            elif final < settings.liveness_threshold:
                reason = "活体综合评分不足"

        return {
            "score": float(np.clip(final, 0.0, 1.0)),
            "passed": passed,
            "reason": reason,
            "single_avg": single_avg,
            "motion": motion_norm,
            "motion_raw": motion_raw,
            "brightness": brightness_norm,
            "brightness_var": brightness_var,
            "frames": len(valid),
            "moire": moire_avg,
        }

    # 兼容旧调用（process_attendance 单帧链路）。
    def score(self, face_bgr: np.ndarray) -> float:
        return self.score_single(face_bgr)["score"]
