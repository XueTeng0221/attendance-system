from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Class Attendance System"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./attendance.db"

    # 模型 Torch 权重路径
    face_detector_model: str = "weights/yolo11n-face.pt"
    emotion_model: str = "weights/emotion_cnn.pt"

    detection_confidence: float = 0.25

    # 合照分块检测参数
    group_photo_detection_conf: float = 0.30
    group_photo_tile_size: int = 640
    group_photo_tile_overlap: float = 0.25
    group_photo_nms_iou: float = 0.40
    recognition_threshold: float = 0.42
    liveness_threshold: float = 0.40
    request_timeout_sec: int = 60

    # 多帧活体参数
    liveness_min_frames: int = 3
    liveness_motion_threshold: float = 0.012
    liveness_brightness_threshold: float = 0.000

    # 无权重自动回退
    allow_heuristic_fallback: bool = True

    # JWT 鉴权
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    # 启动时自动注入的默认教师账号（首次启动 users 表为空时）
    default_teacher_username: str = "admin"
    default_teacher_password: str = "admin123"

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
