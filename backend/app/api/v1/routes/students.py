import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.v1.deps import require_teacher
from app.core.config import settings
from app.db.session import SessionLocal, get_db
from app.models.entities import User
from app.schemas.student import StudentBatchImportItem, StudentBatchImportResponse, StudentRead
from app.services.container import recognition_service
from app.utils.image import ImageDecodeError, decode_image_bytes

router = APIRouter(prefix="/students", tags=["students"])


@router.post("/register", response_model=StudentRead)
async def register_student(
    student_no: str = Form(...),
    name: str = Form(...),
    class_name: str = Form(...),
    image: UploadFile = File(...),
    password: str | None = Form(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    try:
        image_bgr = decode_image_bytes(await image.read())
        student = recognition_service.register_student(
            db,
            student_no=student_no,
            name=name,
            class_name=class_name,
            image_bgr=image_bgr,
            password=password,
        )
        return student
    except ImageDecodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[StudentRead])
def list_students(
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    from sqlalchemy import select

    from app.models.entities import Student

    return db.scalars(select(Student).order_by(Student.created_at.desc())).all()


def _parse_student_filename(filename: str) -> tuple[str, str, str, str]:
    stem = Path(filename).stem.strip()
    parts = [part.strip() for part in stem.split("-")]
    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError("文件名格式应为：学号-姓名-班级-性别.*")
    return parts[0], parts[1], parts[2], parts[3]


def _import_students_batch(db: Session, payloads: list[tuple[str, bytes]]) -> StudentBatchImportResponse:
    items: list[StudentBatchImportItem] = []
    success_count = 0
    seen_student_no: set[str] = set()

    for filename, content in payloads:
        student_no: str | None = None
        name: str | None = None
        class_name: str | None = None
        gender: str | None = None

        try:
            student_no, name, class_name, gender = _parse_student_filename(filename)
            if student_no in seen_student_no:
                raise ValueError(f"批次内学号重复：{student_no}")

            image_bgr = decode_image_bytes(content)
            student = recognition_service.register_student(
                db,
                student_no=student_no,
                name=name,
                class_name=class_name,
                image_bgr=image_bgr,
                password=None,
            )
            seen_student_no.add(student_no)
            success_count += 1
            items.append(
                StudentBatchImportItem(
                    filename=filename,
                    student_no=student_no,
                    name=name,
                    class_name=class_name,
                    gender=gender,
                    success=True,
                    message="导入成功",
                    student=StudentRead.model_validate(student),
                )
            )
        except (ImageDecodeError, ValueError) as exc:
            items.append(
                StudentBatchImportItem(
                    filename=filename,
                    student_no=student_no,
                    name=name,
                    class_name=class_name,
                    gender=gender,
                    success=False,
                    message=str(exc),
                    student=None,
                )
            )

    total = len(payloads)
    return StudentBatchImportResponse(
        total=total,
        success_count=success_count,
        failed_count=total - success_count,
        items=items,
    )


@router.post("/import-directory", response_model=StudentBatchImportResponse)
async def import_students_from_directory(
    images: list[UploadFile] = File(...),
    _: User = Depends(require_teacher),
):
    if not images:
        raise HTTPException(status_code=400, detail="未收到待导入图片")

    payloads: list[tuple[str, bytes]] = []
    for image in images:
        filename = image.filename or "未命名文件"
        payloads.append((filename, await image.read()))

    def _run_with_session() -> StudentBatchImportResponse:
        db = SessionLocal()
        try:
            return _import_students_batch(db, payloads)
        finally:
            db.close()

    try:
        return await asyncio.wait_for(
            run_in_threadpool(_run_with_session),
            timeout=settings.request_timeout_sec,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="批量导入超时，请减少单次图片数量后重试") from exc
