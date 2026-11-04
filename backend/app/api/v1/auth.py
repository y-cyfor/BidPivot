import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import ApiResponse
from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models.login_history import LoginHistory
from app.models.user import User
from app.schemas.user import LogoutRequest, RefreshRequest, UserCreate, UserLogin
from app.services.auth import authenticate_user, create_user, get_user_by_id, get_user_by_username
from app.services.progress import get_redis
from app.utils.captcha import create_captcha, verify_captcha
from app.utils.security import create_access_token, create_refresh_token, decode_access_token
from app.utils.token_store import is_token_revoked, revoke_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_SECONDS = 15 * 60


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _record_login(db: AsyncSession, user_id: uuid.UUID, request: Request, login_status: str) -> None:
    db.add(LoginHistory(
        user_id=user_id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:500],
        status=login_status,
    ))
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.warning("Failed to record login history for user %s", user_id, exc_info=True)


def _tokens(user: User) -> dict:
    return {
        "token": create_access_token(str(user.id)),
        "refresh_token": create_refresh_token(str(user.id)),
    }


@router.get("/captcha", response_model=ApiResponse[object])
async def get_captcha(request: Request):
    ip = request.client.host if request.client else None
    result = await create_captcha(ip)
    if result is None:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="验证码请求过于频繁，请稍后再试")
    captcha_id, image_base64 = result
    return {
        "code": 200,
        "data": {"captcha_id": captcha_id, "image_base64": image_base64},
        "message": "ok",
    }


@router.post("/login", response_model=ApiResponse[object])
@limiter.limit("10/minute")
async def login(request: Request, body: UserLogin, db: AsyncSession = Depends(get_db)):
    username = body.username.strip()
    fail_key = f"login_fail:{username.lower()}"

    try:
        redis = await get_redis()
        failures = int(await redis.get(fail_key) or 0)
        if failures >= LOGIN_MAX_FAILURES:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="登录失败次数过多，请 15 分钟后再试",
            )
    except HTTPException:
        raise
    except Exception:
        redis = None

    if not body.captcha_id or not body.captcha_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入验证码")
    if not await verify_captcha(body.captcha_id, body.captcha_code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误")

    user = await authenticate_user(db, username, body.password)
    if user is None:
        if redis is not None:
            try:
                await redis.incr(fail_key)
                await redis.expire(fail_key, LOGIN_LOCK_SECONDS)
            except Exception:
                logger.warning("Failed to update login failure counter", exc_info=True)
        known_user = await get_user_by_username(db, username)
        if known_user is not None:
            await _record_login(db, known_user.id, request, "failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    if redis is not None:
        try:
            await redis.delete(fail_key)
        except Exception:
            pass

    await _record_login(db, user.id, request, "success")
    tokens = _tokens(user)
    return {
        "code": 200,
        "data": {
            **tokens,
            "user": {"id": str(user.id), "username": user.username, "role": user.role},
        },
        "message": "登录成功",
    }


@router.post("/refresh", response_model=ApiResponse[object])
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_access_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("wrong token type")
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌无效或已过期")

    if await is_token_revoked(payload.get("jti")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌已失效")

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    # Rotate: the old refresh token can only be used once.
    await revoke_token(payload.get("jti"), payload.get("exp"))
    tokens = _tokens(user)
    return {
        "code": 200,
        "data": {
            **tokens,
            "user": {"id": str(user.id), "username": user.username, "role": user.role},
        },
        "message": "刷新成功",
    }


@router.post("/logout", response_model=ApiResponse[object])
async def logout(request: Request, body: LogoutRequest | None = None):
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        try:
            payload = decode_access_token(auth_header[7:].strip())
            await revoke_token(payload.get("jti"), payload.get("exp"))
        except JWTError:
            pass

    if body and body.refresh_token:
        try:
            payload = decode_access_token(body.refresh_token)
            if payload.get("type") == "refresh":
                await revoke_token(payload.get("jti"), payload.get("exp"))
        except JWTError:
            pass

    return {"code": 200, "data": None, "message": "已退出登录"}


@router.post("/register", response_model=ApiResponse[object])
@limiter.limit("5/minute")
async def register(request: Request, body: UserCreate, db: AsyncSession = Depends(get_db)):
    if not settings.ALLOW_PUBLIC_REGISTER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="注册已关闭，请联系管理员创建账号")
    existing = await get_user_by_username(db, body.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    user = await create_user(db, body)
    return {
        "code": 200,
        "data": {"id": str(user.id), "username": user.username, "role": user.role},
        "message": "注册成功",
    }


@router.get("/me", response_model=ApiResponse[object])
async def get_me(user: User = Depends(get_current_user)):
    return {
        "code": 200,
        "data": {"id": str(user.id), "username": user.username, "role": user.role},
        "message": "ok",
    }
