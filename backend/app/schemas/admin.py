import uuid
from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator

BLOCKED_MODEL_HOSTS = {"169.254.169.254", "metadata.google.internal"}


def _validate_api_base(value: str | None) -> str | None:
    if value is None:
        return value
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("API 地址必须是 http(s) 且包含主机名")
    if parsed.hostname.lower() in BLOCKED_MODEL_HOSTS:
        raise ValueError("不允许使用云元数据地址")
    return value


class ModelConfigCreate(BaseModel):
    type: Literal["llm", "embedding"]
    provider_name: str = "openai_compatible"
    api_base: str
    api_key: str = ""
    model_name: str
    parameters: dict | None = None
    is_active: bool = True

    @field_validator("api_base")
    @classmethod
    def validate_api_base(cls, value: str) -> str:
        validated = _validate_api_base(value)
        assert validated is not None
        return validated



class ModelConfigResponse(BaseModel):
    id: uuid.UUID
    type: str
    provider_name: str
    api_base: str
    model_name: str
    parameters: dict | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ModelConfigUpdate(BaseModel):
    provider_name: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    parameters: dict | None = None
    is_active: bool | None = None

    @field_validator("api_base")
    @classmethod
    def validate_api_base(cls, value: str | None) -> str | None:
        return _validate_api_base(value)


class UserCreateAdmin(BaseModel):
    username: str
    password: str
    role: str = "user"


class UserUpdateAdmin(BaseModel):
    username: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserResetPassword(BaseModel):
    new_password: str | None = None


class UserAdminResponse(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    is_active: bool = True
    created_at: datetime
    last_login: datetime | None = None
    total_tokens: int = 0
    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    action: str
    target_type: str | None
    target_id: str | None
    details: dict | None
    ip_address: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class TokenStatsResponse(BaseModel):
    user_id: uuid.UUID
    username: str = ""
    total_tokens: int
    session_tokens: list[dict] = []


class AgentTemplateResponse(BaseModel):
    id: uuid.UUID
    role: str
    name: str
    system_prompt: str
    is_active: bool
    updated_at: datetime
    model_config = {"from_attributes": True}


class AgentTemplateUpdate(BaseModel):
    name: str | None = None
    system_prompt: str | None = None
    is_active: bool | None = None
