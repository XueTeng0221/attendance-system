from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Class Attendance System"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./attendance.db"

    # YOLOv11 and torch model paths
    face_detector_model: str = "weights/yolo11n-face.pt"
    emotion_model: str = "weights/emotion_cnn.pt"

    detection_confidence: float = 0.35
    recognition_threshold: float = 0.55
    liveness_threshold: float = 0.52
    request_timeout_sec: int = 20

    # Allow pipeline fallback when no model file is present
    allow_heuristic_fallback: bool = True

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
