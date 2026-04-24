from datetime import datetime
from time import perf_counter

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    ActivityParticipation,
    AttendanceRecord,
    EmotionEvent,
    Student,
)
from app.schemas.reports import GroupPhotoMatchItem, GroupPhotoResponse
from app.services.emotion import EmotionAnalyzer
from app.services.face_engine import FaceDetector
from app.services.liveness import LivenessDetector
from app.services.torch_embedder import TorchFaceEmbedder
from app.utils.image import crop_face


class RecognitionService:
    def __init__(self) -> None:
        self.detector = FaceDetector()
        self.embedder = TorchFaceEmbedder()
        self.liveness = LivenessDetector()
        self.emotion = EmotionAnalyzer(settings.emotion_model)

    def register_student(
        self,
        db: Session,
        student_no: str,
        name: str,
        class_name: str,
        image_bgr: np.ndarray,
    ) -> Student:
        existing = db.scalar(select(Student).where(Student.student_no == student_no))
        if existing:
            raise ValueError(f"student_no '{student_no}' already exists")

        detections = self.detector.detect(image_bgr)
        if not detections:
            raise ValueError("no face found in registration image")

        best_box, _ = max(detections, key=lambda item: self._box_area(item[0]))
        face = crop_face(image_bgr, best_box)

        embedding = self.embedder.extract(face)
        student = Student(
            student_no=student_no,
            name=name,
            class_name=class_name,
            face_embedding=self.embedder.to_json(embedding),
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        return student

    def process_attendance(self, db: Session, image_bgr: np.ndarray) -> dict:
        detections = self.detector.detect(image_bgr)
        now = datetime.utcnow()

        if not detections:
            return self._save_attendance(
                db,
                status="failed",
                confidence=0.0,
                liveness_score=0.0,
                emotion=("neutral", 0.0),
                student=None,
                reason="未检测到人脸",
                now=now,
            )

        best_box, _ = max(detections, key=lambda item: self._box_area(item[0]))
        face = crop_face(image_bgr, best_box)

        liveness_score = self.liveness.score(face)
        emotion = self.emotion.predict(face)

        if liveness_score < settings.liveness_threshold:
            return self._save_attendance(
                db,
                status="failed",
                confidence=0.0,
                liveness_score=liveness_score,
                emotion=emotion,
                student=None,
                reason="活体检测未通过",
                now=now,
            )

        embedding = self.embedder.extract(face)
        matched_student, best_score = self._match_student(db, embedding)

        if matched_student is None or best_score < settings.recognition_threshold:
            return self._save_attendance(
                db,
                status="failed",
                confidence=best_score,
                liveness_score=liveness_score,
                emotion=emotion,
                student=None,
                reason="人脸库匹配失败",
                now=now,
            )

        return self._save_attendance(
            db,
            status="success",
            confidence=best_score,
            liveness_score=liveness_score,
            emotion=emotion,
            student=matched_student,
            reason="",
            now=now,
        )

    def process_group_photo(self, db: Session, image_bgr: np.ndarray, event_name: str) -> GroupPhotoResponse:
        start = perf_counter()
        detections = self.detector.detect(image_bgr)

        matched_items: list[GroupPhotoMatchItem] = []
        seen_student_ids: set[int] = set()

        for box, _ in detections:
            face = crop_face(image_bgr, box)
            emotion, emotion_score = self.emotion.predict(face)
            embedding = self.embedder.extract(face)
            student, confidence = self._match_student(db, embedding)

            self._save_emotion(db, student.id if student else None, "group_photo", emotion, emotion_score)

            if student is None or confidence < settings.recognition_threshold:
                continue
            if student.id in seen_student_ids:
                continue

            seen_student_ids.add(student.id)

            db.add(
                ActivityParticipation(
                    student_id=student.id,
                    event_name=event_name,
                    confidence=confidence,
                )
            )

            matched_items.append(
                GroupPhotoMatchItem(
                    student_id=student.id,
                    student_no=student.student_no,
                    name=student.name,
                    class_name=student.class_name,
                    confidence=confidence,
                    emotion=emotion,
                    emotion_score=emotion_score,
                )
            )

        db.commit()
        elapsed = int((perf_counter() - start) * 1000)
        return GroupPhotoResponse(
            event_name=event_name,
            detected_faces=len(detections),
            matched_students=matched_items,
            unmatched_faces=max(0, len(detections) - len(matched_items)),
            processing_time_ms=elapsed,
        )

    def participation_stats(self, db: Session) -> list[dict]:
        query = (
            select(
                Student.id,
                Student.student_no,
                Student.name,
                Student.class_name,
                func.count(ActivityParticipation.id).label("events_count"),
            )
            .join(ActivityParticipation, ActivityParticipation.student_id == Student.id, isouter=True)
            .group_by(Student.id)
            .order_by(func.count(ActivityParticipation.id).desc())
        )
        rows = db.execute(query).all()
        return [
            {
                "student_id": row.id,
                "student_no": row.student_no,
                "name": row.name,
                "class_name": row.class_name,
                "events_count": row.events_count,
            }
            for row in rows
        ]

    def emotion_stats(self, db: Session) -> dict:
        summary_query = (
            select(EmotionEvent.emotion, func.count(EmotionEvent.id).label("count"))
            .group_by(EmotionEvent.emotion)
            .order_by(func.count(EmotionEvent.id).desc())
        )
        timeline_query = select(EmotionEvent).order_by(EmotionEvent.timestamp.desc()).limit(50)

        summary = db.execute(summary_query).all()
        timeline = db.scalars(timeline_query).all()

        return {
            "summary": [{"emotion": row.emotion, "count": row.count} for row in summary],
            "timeline": [
                {
                    "timestamp": item.timestamp,
                    "emotion": item.emotion,
                    "source": item.source,
                }
                for item in timeline
            ],
        }

    def _match_student(self, db: Session, query_embedding) -> tuple[Student | None, float]:
        students = db.scalars(select(Student)).all()
        if not students:
            return None, 0.0

        best_student: Student | None = None
        best_score = -1.0

        for student in students:
            known = self.embedder.from_json(student.face_embedding)
            score = self.embedder.cosine_similarity(query_embedding, known)
            if score > best_score:
                best_score = score
                best_student = student

        return best_student, max(0.0, best_score)

    @staticmethod
    def _box_area(box: tuple[int, int, int, int]) -> int:
        x1, y1, x2, y2 = box
        return max(1, (x2 - x1) * (y2 - y1))

    def _save_emotion(
        self,
        db: Session,
        student_id: int | None,
        source: str,
        emotion: str,
        score: float,
    ) -> None:
        db.add(
            EmotionEvent(
                student_id=student_id,
                source=source,
                emotion=emotion,
                score=score,
            )
        )

    def _save_attendance(
        self,
        db: Session,
        status: str,
        confidence: float,
        liveness_score: float,
        emotion: tuple[str, float],
        student: Student | None,
        reason: str,
        now: datetime,
    ) -> dict:
        emotion_label, emotion_score = emotion

        record = AttendanceRecord(
            student_id=student.id if student else None,
            status=status,
            confidence=confidence,
            liveness_score=liveness_score,
            emotion=emotion_label,
            reason=reason,
            timestamp=now,
        )
        db.add(record)

        self._save_emotion(
            db,
            student.id if student else None,
            "attendance",
            emotion_label,
            emotion_score,
        )

        db.commit()

        return {
            "status": status,
            "confidence": confidence,
            "liveness_score": liveness_score,
            "reason": reason,
            "attendance_time": now,
            "student": student,
            "emotion": {
                "emotion": emotion_label,
                "score": emotion_score,
            },
        }
