import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.api.v1.deps import get_current_user
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import User
from app.schemas.attendance import AttendanceResponse
from app.services.container import recognition_service
from app.utils.image import ImageDecodeError, decode_image_bytes

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/check", response_model=AttendanceResponse)
async def check_attendance(
    images: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    if not images:
        raise HTTPException(status_code=400, detail="未收到图像帧")

    try:
        frames = [decode_image_bytes(await image.read()) for image in images]

        # 把当前用户在请求线程内拷贝一份只读字段，避免在线程池里再访问 ORM 对象。
        user_snapshot = User(
            id=current_user.id,
            username=current_user.username,
            role=current_user.role,
            student_id=current_user.student_id,
            password_hash=current_user.password_hash,
        )

        def _run_with_session():
            db = SessionLocal()
            try:
                return recognition_service.process_attendance_multi(db, frames, user_snapshot)
            finally:
                db.close()

        result = await asyncio.wait_for(
            run_in_threadpool(_run_with_session),
            timeout=settings.request_timeout_sec,
        )
        return result
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="识别超时，请稍后重试") from exc
    except ImageDecodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
