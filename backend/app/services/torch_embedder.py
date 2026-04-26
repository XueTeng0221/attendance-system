import json

import cv2
import numpy as np
import torch
import torch.nn.functional as F


class TorchFaceEmbedder:
    def __init__(self, embedding_dim: int = 128, projection_seed: int = 2026) -> None:
        self.embedding_dim = embedding_dim
        generator = torch.Generator().manual_seed(projection_seed)
        projection = torch.randn((32 * 32, embedding_dim), generator=generator)
        self.projection = F.normalize(projection, dim=0)

    def extract(self, face_bgr: np.ndarray) -> torch.Tensor:
        '''
        从人脸提取特征向量。
        shape 为 (1, embedding_dim)，对待提取的人脸灰度图像进行下采样后进行正则化。
        '''
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        tensor = torch.from_numpy(gray).float() / 255.0
        tensor = F.interpolate(
            tensor.unsqueeze(0).unsqueeze(0),
            size=(32, 32),
            mode="bilinear",
            align_corners=False,
        ).squeeze(0).squeeze(0)

        embedding = torch.matmul(tensor.flatten(), self.projection)
        embedding = F.normalize(embedding, dim=0)
        return embedding

    @staticmethod
    def to_json(embedding: torch.Tensor) -> str:
        return json.dumps([float(v) for v in embedding.cpu().tolist()])

    @staticmethod
    def from_json(payload: str) -> torch.Tensor:
        values = json.loads(payload)
        vector = torch.tensor(values, dtype=torch.float32)
        return F.normalize(vector, dim=0)

    @staticmethod
    def cosine_similarity(a: torch.Tensor, b: torch.Tensor) -> float:
        a = F.normalize(a, dim=0)
        b = F.normalize(b, dim=0)
        return float(torch.dot(a, b).item())
