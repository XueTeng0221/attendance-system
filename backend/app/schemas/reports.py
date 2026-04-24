from datetime import datetime

from pydantic import BaseModel


class GroupPhotoMatchItem(BaseModel):
    student_id: int
    student_no: str
    name: str
    class_name: str
    confidence: float
    emotion: str
    emotion_score: float


class GroupPhotoResponse(BaseModel):
    event_name: str
    detected_faces: int
    matched_students: list[GroupPhotoMatchItem]
    unmatched_faces: int
    processing_time_ms: int


class ParticipationRow(BaseModel):
    student_id: int
    student_no: str
    name: str
    class_name: str
    events_count: int


class EmotionStatRow(BaseModel):
    emotion: str
    count: int


class EmotionTimelineRow(BaseModel):
    timestamp: datetime
    emotion: str
    source: str
