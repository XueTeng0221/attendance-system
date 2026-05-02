from datetime import datetime

from pydantic import BaseModel

from app.schemas.student import StudentRead


class EmotionResult(BaseModel):
    emotion: str
    score: float


class AttendanceResponse(BaseModel):
    status: str
    confidence: float
    liveness_score: float
    liveness_breakdown: dict | None = None
    reason: str
    attendance_time: datetime
    student: StudentRead | None = None
    emotion: EmotionResult
