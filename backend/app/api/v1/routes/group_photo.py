import asyncio

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.reports import GroupPhotoResponse
from app.services.container import recognition_service
from app.utils.image import ImageDecodeError, decode_image_bytes

router = APIRouter(prefix="/group-photo", tags=["group-photo"])


@router.post("/recognize", response_model=GroupPhotoResponse)
async def recognize_group_photo(
    event_name: str = Form(...),
    image: UploadFile = File(...),
):
    try:
        image_bgr = decode_image_bytes(await image.read())

        def _run_with_session():
            db = SessionLocal()
            try:
                return recognition_service.process_group_photo(db, image_bgr, event_name)
            finally:
                db.close()

        result = await asyncio.wait_for(
            run_in_threadpool(_run_with_session),
            timeout=settings.request_timeout_sec,
        )
        return result
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="合照识别超时，请稍后重试") from exc
    except ImageDecodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
