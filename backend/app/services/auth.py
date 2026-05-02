from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


def hash_password(plain: str) -> str:
    # bcrypt 输入上限 72 字节，超出部分会被忽略；此处显式截断以避免警告。
    raw = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        raw = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(raw, hashed.encode("utf-8"))
    except Exception:
        return False


def encode_token(*, sub: str, role: str, user_id: int, student_id: int | None = None) -> str:
    expire = datetime.now(tz=timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": sub,
        "role": role,
        "uid": user_id,
        "sid": student_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
