from datetime import datetime

from pydantic import BaseModel

from app.schemas.student import StudentRead


class EmotionResult(BaseModel):
    emotion: str
    score: float


class FaceBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float


class FaceDetectionResponse(BaseModel):
    found: bool
    box: FaceBox | None = None
    image_width: int
    image_height: int


class AttendanceResponse(BaseModel):
    status: str
    confidence: float
    liveness_score: float
    liveness_breakdown: dict | None = None
    reason: str
    attendance_time: datetime
    student: StudentRead | None = None
    emotion: EmotionResult
