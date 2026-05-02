from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import require_teacher
from app.db.session import get_db
from app.models.entities import AttendanceRecord, Student, User
from app.schemas.reports import EmotionStatRow, EmotionTimelineRow, ParticipationRow
from app.services.container import recognition_service
from app.utils.export import rows_to_csv, tables_to_xlsx

router = APIRouter(prefix="/reports", tags=["reports"])


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


@router.get("/participation", response_model=list[ParticipationRow])
def get_participation_report(
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    return recognition_service.participation_stats(db)


@router.get("/emotions")
def get_emotion_report(
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    result = recognition_service.emotion_stats(db)
    return {
        "summary": [EmotionStatRow(**item) for item in result["summary"]],
        "timeline": [EmotionTimelineRow(**item) for item in result["timeline"]],
    }


_ATTENDANCE_HEADERS = ["学号", "姓名", "班级", "状态", "置信度", "活体分", "情绪", "原因", "考勤时间"]
_PARTICIPATION_HEADERS = ["学号", "姓名", "班级", "参与活动数"]


def _attendance_rows(db: Session) -> list[list]:
    query = (
        select(AttendanceRecord, Student)
        .join(Student, Student.id == AttendanceRecord.student_id, isouter=True)
        .order_by(AttendanceRecord.timestamp.desc())
    )
    rows: list[list] = []
    for record, student in db.execute(query).all():
        rows.append(
            [
                student.student_no if student else "",
                student.name if student else "",
                student.class_name if student else "",
                record.status,
                round(record.confidence, 4),
                round(record.liveness_score, 4),
                record.emotion,
                record.reason,
                _format_dt(record.timestamp),
            ]
        )
    return rows


def _participation_rows(db: Session) -> list[list]:
    stats = recognition_service.participation_stats(db)
    return [
        [item["student_no"], item["name"], item["class_name"], item["events_count"]]
        for item in stats
    ]


@router.get("/attendance/export")
def export_attendance(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    rows = _attendance_rows(db)
    if format == "csv":
        return rows_to_csv(_ATTENDANCE_HEADERS, rows, "attendance.csv")
    if format == "xlsx":
        return tables_to_xlsx({"考勤记录": (_ATTENDANCE_HEADERS, rows)}, "attendance.xlsx")
    raise HTTPException(status_code=400, detail="不支持的导出格式")


@router.get("/participation/export")
def export_participation(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    rows = _participation_rows(db)
    if format == "csv":
        return rows_to_csv(_PARTICIPATION_HEADERS, rows, "participation.csv")
    if format == "xlsx":
        return tables_to_xlsx({"活动参与": (_PARTICIPATION_HEADERS, rows)}, "participation.xlsx")
    raise HTTPException(status_code=400, detail="不支持的导出格式")
