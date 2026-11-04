import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import router as v1_router
from app.api.v1.ws import router as ws_router
from app.config import SEED_ADMIN, settings, validate_settings
from app.limiter import limiter

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema changes are applied with Alembic (``alembic upgrade head``),
    # never by create_all on application startup.
    validate_settings()
    logger.info("BidPivot API starting")

    await _seed_agent_templates()

    # Seed default users only when explicitly enabled
    if SEED_ADMIN:
        await _seed_default_users()

    yield


async def _seed_agent_templates():
    """Insert the default writing-agent prompts once."""
    from sqlalchemy import select

    from app.database import async_session
    from app.models.agent_template import AgentTemplate
    from app.services.agents.prompts import DEFAULT_AGENT_PROMPTS

    async with async_session() as db:
        existing = set((await db.execute(select(AgentTemplate.role))).scalars().all())
        added = 0
        for role, prompt in DEFAULT_AGENT_PROMPTS.items():
            if role in existing:
                continue
            db.add(AgentTemplate(role=role, name=f"{role}Agent", system_prompt=prompt))
            added += 1
        if added:
            await db.commit()
            logger.info("Seeded %s default agent templates", added)


async def _seed_default_users():
    """Create default admin and user accounts if they don't exist."""
    from app.database import async_session
    from app.models.user import User
    from app.services.auth import get_user_by_username, create_user
    from app.schemas.user import UserCreate
    from app.utils.security import hash_password
    from sqlalchemy import select

    async with async_session() as db:
        # Create admin if not exists
        admin = await get_user_by_username(db, "admin")
        if not admin:
            admin_user = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
            )
            db.add(admin_user)
            logger.info("Created default admin user (admin/admin123)")

        # Create regular user if not exists
        user = await get_user_by_username(db, "user1")
        if not user:
            regular_user = User(
                username="user1",
                password_hash=hash_password("user123"),
                role="user",
            )
            db.add(regular_user)
            logger.info("Created default user (user1/user123)")

        await db.commit()


app = FastAPI(title="BidPivot API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "http_request method=%s path=%s status=%s duration_ms=%.1f",
        request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


app.include_router(v1_router)
app.include_router(ws_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
