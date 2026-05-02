from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.deps import require_teacher
from app.db.session import get_db
from app.models.entities import User
from app.schemas.student import StudentRead
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
