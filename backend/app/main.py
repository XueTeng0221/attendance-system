import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.session import Base, SessionLocal, engine
from app.models.entities import User
from app.services.auth import hash_password


logger = logging.getLogger("attendance")

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        any_user = db.scalar(select(User).limit(1))
        if any_user is None:
            db.add(
                User(
                    username=settings.default_teacher_username,
                    password_hash=hash_password(settings.default_teacher_password),
                    role="teacher",
                )
            )
            db.commit()
            logger.warning(
                "已创建默认教师账号 '%s'，请在生产环境修改 default_teacher_password",
                settings.default_teacher_username,
            )
    finally:
        db.close()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "message": "请求参数不合法"})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": "服务器内部异常",
            "message": str(exc),
        },
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_prefix)
