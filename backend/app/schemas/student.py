from datetime import datetime

from pydantic import BaseModel, Field


class StudentBase(BaseModel):
    student_no: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    class_name: str = Field(min_length=1, max_length=64)


class StudentCreate(StudentBase):
    pass


class StudentRead(StudentBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class StudentBatchImportItem(BaseModel):
    filename: str
    student_no: str | None = None
    name: str | None = None
    class_name: str | None = None
    gender: str | None = None
    success: bool
    message: str
    student: StudentRead | None = None


class StudentBatchImportResponse(BaseModel):
    total: int
    success_count: int
    failed_count: int
    items: list[StudentBatchImportItem]
