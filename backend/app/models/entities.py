from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    class_name: Mapped[str] = mapped_column(String(64), index=True)
    face_embedding: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    attendances = relationship("AttendanceRecord", back_populates="student")
    participations = relationship("ActivityParticipation", back_populates="student")
    emotions = relationship("EmotionEvent", back_populates="student")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    liveness_score: Mapped[float] = mapped_column(Float, default=0.0)
    emotion: Mapped[str] = mapped_column(String(32), default="neutral")
    reason: Mapped[str] = mapped_column(String(255), default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    student = relationship("Student", back_populates="attendances")


class ActivityParticipation(Base):
    __tablename__ = "activity_participations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    event_name: Mapped[str] = mapped_column(String(128), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    activity_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    student = relationship("Student", back_populates="participations")


class EmotionEvent(Base):
    __tablename__ = "emotion_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(24), index=True)
    emotion: Mapped[str] = mapped_column(String(32), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    student = relationship("Student", back_populates="emotions")
