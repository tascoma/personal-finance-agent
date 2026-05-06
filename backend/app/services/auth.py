import logging
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _make_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID) -> str:
    return _make_token(
        {"sub": str(user_id)},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _make_token(
        {"sub": str(user_id)},
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> uuid.UUID:
    """Decode and validate a JWT, returning the user_id. Raises ValueError on failure."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        sub: str | None = payload.get("sub")
        if sub is None:
            raise ValueError("Token missing 'sub' claim")
        return uuid.UUID(sub)
    except JWTError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.scalars(select(User).where(User.email == email))
    return result.first()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


class AuthError(Exception):
    """Raised for authentication failures."""


async def register_user(db: AsyncSession, email: str, password: str) -> User:
    existing = await get_user_by_email(db, email)
    if existing is not None:
        raise AuthError("Email already registered")
    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("Registered new user %s", user.user_id)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthError("Invalid credentials")
    if not user.is_active:
        raise AuthError("Account is disabled")
    return user
