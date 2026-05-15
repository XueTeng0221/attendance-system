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


class GroupPhotoFaceBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    matched: bool
    student_no: str | None = None
    name: str | None = None
    class_name: str | None = None


class GroupPhotoResponse(BaseModel):
    event_name: str
    detected_faces: int
    matched_students: list[GroupPhotoMatchItem]
    face_boxes: list[GroupPhotoFaceBox]
    image_width: int
    image_height: int
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
