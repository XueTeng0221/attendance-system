from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.reports import EmotionStatRow, EmotionTimelineRow, ParticipationRow
from app.services.container import recognition_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/participation", response_model=list[ParticipationRow])
def get_participation_report(db: Session = Depends(get_db)):
    return recognition_service.participation_stats(db)


@router.get("/emotions")
def get_emotion_report(db: Session = Depends(get_db)):
    result = recognition_service.emotion_stats(db)
    return {
        "summary": [EmotionStatRow(**item) for item in result["summary"]],
        "timeline": [EmotionTimelineRow(**item) for item in result["timeline"]],
    }
