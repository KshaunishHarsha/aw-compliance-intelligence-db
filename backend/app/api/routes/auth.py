import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel

from app.api.deps import get_current_user, get_redis
from app.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import RefreshRequest, TokenResponse, UserResponse

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_access_token(user_id: str, role: str) -> str:
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "role": role, "type": "access", "jti": jti, "exp": expire},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _create_refresh_token(user_id: str) -> str:
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    return jwt.encode(
        {"sub": user_id, "type": "refresh", "jti": jti, "exp": expire},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


class _LoginBody(BaseModel):
    email: str
    password: str


@router.post("/login", response_model=TokenResponse)
async def login(
    body: _LoginBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not _verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    user_id_str = str(user.id)
    user_role = user.role

    await db.execute(
        update(User).where(User.id == user.id).values(last_login_at=datetime.utcnow())
    )
    await db.commit()

    logger.info("User login", extra={"user_id": user_id_str})
    return TokenResponse(
        access_token=_create_access_token(user_id_str, user_role),
        refresh_token=_create_refresh_token(user_id_str),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    # For per-token invalidation, call POST /auth/logout/token with the token.
    logger.info("User logout", extra={"user_id": str(current_user.id)})


@router.post("/logout/token", status_code=status.HTTP_204_NO_CONTENT)
async def logout_token(
    body: RefreshRequest,
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
) -> None:
    """Blocklist a specific token by its jti. Accepts either access or refresh token."""
    try:
        payload = jwt.decode(
            body.refresh_token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        jti: str | None = payload.get("jti")
        exp: int | None = payload.get("exp")
        if jti and exp:
            ttl = max(0, exp - int(datetime.now(timezone.utc).timestamp()))
            await redis_client.setex(f"blocklist:{jti}", ttl, "1")
            logger.info("Token blocklisted", extra={"jti": jti})
    except JWTError:
        pass  # Expired or invalid token — nothing to blocklist


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
) -> TokenResponse:
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    try:
        payload = jwt.decode(
            body.refresh_token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")
        if user_id is None or payload.get("type") != "refresh":
            raise invalid
    except JWTError:
        raise invalid

    if jti and await redis_client.get(f"blocklist:{jti}"):
        raise invalid

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise invalid

    # Rotate: blocklist the used refresh token
    if jti:
        exp: int | None = payload.get("exp")
        if exp:
            ttl = max(0, exp - int(datetime.now(timezone.utc).timestamp()))
            await redis_client.setex(f"blocklist:{jti}", ttl, "1")

    return TokenResponse(
        access_token=_create_access_token(str(user.id), user.role),
        refresh_token=_create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user
