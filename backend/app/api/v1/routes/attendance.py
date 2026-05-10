import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.api.v1.deps import get_current_user
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import User
from app.schemas.attendance import AttendanceResponse, FaceBox, FaceDetectionResponse
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


@router.post("/detect-face", response_model=FaceDetectionResponse)
async def detect_face(
    image: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    try:
        image_bgr = decode_image_bytes(await image.read())

        def _run_detect():
            detection = recognition_service.detect_best_face(image_bgr)
            if detection is None:
                return FaceDetectionResponse(
                    found=False,
                    box=None,
                    image_width=int(image_bgr.shape[1]),
                    image_height=int(image_bgr.shape[0]),
                )
            return FaceDetectionResponse(
                found=True,
                box=FaceBox.model_validate(detection),
                image_width=int(image_bgr.shape[1]),
                image_height=int(image_bgr.shape[0]),
            )

        return await asyncio.wait_for(
            run_in_threadpool(_run_detect),
            timeout=settings.request_timeout_sec,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="人脸检测超时，请稍后重试") from exc
    except ImageDecodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
