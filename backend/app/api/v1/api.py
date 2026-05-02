from fastapi import APIRouter

from app.api.v1.routes import attendance, auth, group_photo, reports, students

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(students.router)
api_router.include_router(attendance.router)
api_router.include_router(group_photo.router)
api_router.include_router(reports.router)
