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
