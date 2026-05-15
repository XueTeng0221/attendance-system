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
    User,
)
from app.schemas.reports import GroupPhotoFaceBox, GroupPhotoMatchItem, GroupPhotoResponse
from app.services.auth import hash_password
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
        password: str | None = None,
    ) -> Student:
        existing = db.scalar(select(Student).where(Student.student_no == student_no))
        if existing:
            raise ValueError(f"student_no '{student_no}' already exists")

        # 学生登录账号沿用学号，避免与现有教师账号冲突。
        existing_user = db.scalar(select(User).where(User.username == student_no))
        if existing_user is not None:
            raise ValueError(f"username '{student_no}' already exists")

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
        db.flush()  # 拿到 student.id 给 User 引用

        login_password = password or student_no
        db.add(
            User(
                username=student_no,
                password_hash=hash_password(login_password),
                role="student",
                student_id=student.id,
            )
        )
        db.commit()
        db.refresh(student)
        return student

    def process_attendance(self, db: Session, image_bgr: np.ndarray) -> dict:
        return self.process_attendance_multi(db, [image_bgr], current_user=None)

    def detect_best_face(self, image_bgr: np.ndarray) -> dict | None:
        detections = self.detector.detect(image_bgr)
        if not detections:
            return None
        best_box, confidence = max(detections, key=lambda item: self._box_area(item[0]))
        x1, y1, x2, y2 = best_box
        return {
            "x1": int(x1),
            "y1": int(y1),
            "x2": int(x2),
            "y2": int(y2),
            "confidence": float(confidence),
        }

    def process_attendance_multi(
        self,
        db: Session,
        frames_bgr: list[np.ndarray],
        current_user: User | None,
    ) -> dict:
        '''多帧考勤主链路。frames_bgr 接受任意 ≥1 张图，多帧时启用运动校验。'''
        now = datetime.utcnow()

        if not frames_bgr:
            return self._save_attendance(
                db,
                status="failed",
                confidence=0.0,
                liveness_score=0.0,
                liveness_breakdown=None,
                emotion=("neutral", 0.0),
                student=None,
                reason="未收到任何图像",
                now=now,
            )

        # 每帧检测最大人脸；缺脸帧直接累计为采集失败原因。
        faces: list[np.ndarray] = []
        for frame in frames_bgr:
            detections = self.detector.detect(frame)
            if not detections:
                continue
            best_box, _ = max(detections, key=lambda item: self._box_area(item[0]))
            faces.append(crop_face(frame, best_box))

        if not faces:
            return self._save_attendance(
                db,
                status="failed",
                confidence=0.0,
                liveness_score=0.0,
                liveness_breakdown=None,
                emotion=("neutral", 0.0),
                student=None,
                reason="未检测到人脸",
                now=now,
            )

        last_face = faces[-1]
        emotion = self.emotion.predict(last_face)

        # 多帧走 score_sequence；若仅有 1 帧则退化为单帧打分。
        is_multi = len(faces) >= settings.liveness_min_frames
        if is_multi:
            liveness = self.liveness.score_sequence(faces)
            liveness_score = liveness["score"]
            liveness_passed = liveness["passed"]
            liveness_reason = liveness["reason"]
        else:
            single = self.liveness.score_single(last_face)
            liveness_score = single["score"]
            moire_rejected = single.get("moire", 0.0) > 0
            liveness_passed = (liveness_score >= settings.liveness_threshold) and (not moire_rejected)
            if moire_rejected:
                liveness_reason = "摩尔纹分数>0，按策略直接拒绝"
            else:
                liveness_reason = "" if liveness_passed else "活体检测未通过"
            liveness = {**single, "passed": liveness_passed, "reason": liveness_reason}

        if not liveness_passed:
            return self._save_attendance(
                db,
                status="failed",
                confidence=0.0,
                liveness_score=liveness_score,
                liveness_breakdown=liveness,
                emotion=emotion,
                student=None,
                reason=liveness_reason or "活体检测未通过",
                now=now,
            )

        embedding = self.embedder.extract(last_face)
        matched_student, best_score = self._match_student(db, embedding)

        if matched_student is None or best_score < settings.recognition_threshold:
            return self._save_attendance(
                db,
                status="failed",
                confidence=best_score,
                liveness_score=liveness_score,
                liveness_breakdown=liveness,
                emotion=emotion,
                student=None,
                reason="人脸库匹配失败",
                now=now,
            )

        # 学生角色仅允许匹配自己，避免代签。
        if current_user is not None and current_user.role == "student":
            if matched_student.id != current_user.student_id:
                return self._save_attendance(
                    db,
                    status="failed",
                    confidence=best_score,
                    liveness_score=liveness_score,
                    liveness_breakdown=liveness,
                    emotion=emotion,
                    student=None,
                    reason="人脸与登录账号不一致",
                    now=now,
                )

        return self._save_attendance(
            db,
            status="success",
            confidence=best_score,
            liveness_score=liveness_score,
            liveness_breakdown=liveness,
            emotion=emotion,
            student=matched_student,
            reason="",
            now=now,
        )

    def process_group_photo(self, db: Session, image_bgr: np.ndarray, event_name: str) -> GroupPhotoResponse:
        start = perf_counter()
        detections = self.detector.detect_tiled(
            image_bgr,
            conf=settings.group_photo_detection_conf,
            tile_size=settings.group_photo_tile_size,
            overlap=settings.group_photo_tile_overlap,
            nms_iou=settings.group_photo_nms_iou,
        )

        matched_items: list[GroupPhotoMatchItem] = []
        face_boxes: list[GroupPhotoFaceBox] = []
        seen_student_ids: set[int] = set()

        for box, _ in detections:
            x1, y1, x2, y2 = box
            face = crop_face(image_bgr, box)
            emotion, emotion_score = self.emotion.predict(face)
            embedding = self.embedder.extract(face)
            student, confidence = self._match_student(db, embedding)

            self._save_emotion(db, student.id if student else None, "group_photo", emotion, emotion_score)

            matched = student is not None and confidence >= settings.recognition_threshold
            face_boxes.append(
                GroupPhotoFaceBox(
                    x1=int(x1),
                    y1=int(y1),
                    x2=int(x2),
                    y2=int(y2),
                    confidence=confidence,
                    matched=matched,
                    student_no=student.student_no if matched and student else None,
                    name=student.name if matched and student else None,
                    class_name=student.class_name if matched and student else None,
                )
            )

            if not matched:
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
        matched_face_count = sum(1 for item in face_boxes if item.matched)
        return GroupPhotoResponse(
            event_name=event_name,
            detected_faces=len(detections),
            matched_students=matched_items,
            face_boxes=face_boxes,
            image_width=int(image_bgr.shape[1]),
            image_height=int(image_bgr.shape[0]),
            unmatched_faces=max(0, len(detections) - matched_face_count),
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
        liveness_breakdown: dict | None,
        emotion: tuple[str, float],
        student: Student | None,
        reason: str,
        now: datetime,
    ) -> dict:
        emotion_label, emotion_score = emotion
        student_payload = None
        if student is not None:
            student_payload = {
                "id": student.id,
                "student_no": student.student_no,
                "name": student.name,
                "class_name": student.class_name,
                "created_at": student.created_at,
            }

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
            "liveness_breakdown": liveness_breakdown,
            "reason": reason,
            "attendance_time": now,
            "student": student_payload,
            "emotion": {
                "emotion": emotion_label,
                "score": emotion_score,
            },
        }
