import json
import logging
import os
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def _load_config_json() -> dict:
    """Load config from backend/config.json if it exists."""
    config_path = Path(__file__).parent.parent / "config.json"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded config from {config_path}")
        return data
    except Exception as e:
        logger.warning(f"Failed to load {config_path}: {e}")
        return {}


def _config_to_env_overrides(cfg: dict) -> dict:
    """Convert config.json structure to environment variable overrides."""
    overrides = {}
    if "database" in cfg and "url" in cfg["database"]:
        overrides["DATABASE_URL"] = cfg["database"]["url"]
    if "redis" in cfg and "url" in cfg["redis"]:
        overrides["REDIS_URL"] = cfg["redis"]["url"]
    if "qdrant" in cfg and "url" in cfg["qdrant"]:
        overrides["QDRANT_URL"] = cfg["qdrant"]["url"]
    if "minio" in cfg:
        m = cfg["minio"]
        if "endpoint" in m:
            overrides["MINIO_ENDPOINT"] = m["endpoint"]
        if "access_key" in m:
            overrides["MINIO_ACCESS_KEY"] = m["access_key"]
        if "secret_key" in m:
            overrides["MINIO_SECRET_KEY"] = m["secret_key"]
        if "bucket" in m:
            overrides["MINIO_BUCKET"] = m["bucket"]
    if "jwt" in cfg:
        jwt = cfg["jwt"]
        if "secret" in jwt:
            overrides["JWT_SECRET"] = jwt["secret"]
        if "expire_minutes" in jwt:
            overrides["JWT_EXPIRE_MINUTES"] = str(jwt["expire_minutes"])
    if "server" in cfg:
        s = cfg["server"]
        if "cors_origins" in s:
            overrides["CORS_ORIGINS"] = json.dumps(s["cors_origins"])
    return overrides


# Load config.json and set as env defaults (env vars still take priority)
_cfg = _load_config_json()
_env_overrides = _config_to_env_overrides(_cfg)
for key, value in _env_overrides.items():
    if key not in os.environ:
        os.environ[key] = value


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://bidpivot:bidpivot_dev@localhost:5432/bidpivot"
    REDIS_URL: str = "redis://localhost:6379/0"
    QDRANT_URL: str = "http://localhost:6333"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: SecretStr = SecretStr("minioadmin")
    MINIO_SECRET_KEY: SecretStr = SecretStr("minioadmin")
    MINIO_BUCKET: str = "bidpivot"
    JWT_SECRET: SecretStr = SecretStr("change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    # Separate key for encrypting provider API keys. Falls back to JWT_SECRET
    # for backwards compatibility when unset.
    ENCRYPTION_KEY: SecretStr | None = None
    ALLOW_PUBLIC_REGISTER: bool = False
    # Optional ClamAV endpoint, e.g. "clamav:3310". Scanning is skipped when unset.
    CLAMAV_HOST: str | None = None
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def validate_settings() -> None:
    """Fail fast on unsafe production defaults."""
    if settings.APP_ENV.lower() != "production":
        return
    problems: list[str] = []
    jwt_secret = settings.JWT_SECRET.get_secret_value()
    if jwt_secret == "change-me-in-production" or "CHANGE_ME" in jwt_secret:
        problems.append("JWT_SECRET 仍为默认/占位值")
    encryption_key = settings.ENCRYPTION_KEY.get_secret_value() if settings.ENCRYPTION_KEY else ""
    if not encryption_key or "CHANGE_ME" in encryption_key:
        problems.append("ENCRYPTION_KEY 未设置或仍为占位值")
    if "bidpivot_dev" in settings.DATABASE_URL or "CHANGE_ME" in settings.DATABASE_URL:
        problems.append("DATABASE_URL 仍使用开发/占位密码")
    if problems:
        raise RuntimeError("生产配置不安全: " + "; ".join(problems))


if settings.JWT_SECRET.get_secret_value() == "change-me-in-production":
    logger.warning("JWT_SECRET is using default value! Set JWT_SECRET environment variable in production.")

SEED_ADMIN = os.getenv("BIDPIVOT_SEED_ADMIN", "").lower() == "true"
if SEED_ADMIN:
    logger.warning("BIDPIVOT_SEED_ADMIN is enabled - default accounts will be created on startup.")
