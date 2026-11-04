import uuid

from pydantic import BaseModel, field_validator


class UserLogin(BaseModel):
    username: str
    password: str
    captcha_id: str
    captcha_code: str


class UserCreate(BaseModel):
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码长度不能少于6位")
        return v

    @field_validator("username")
    @classmethod
    def username_min_length(cls, v: str) -> str:
        if len(v) < 2:
            raise ValueError("用户名长度不能少于2位")
        return v


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    role: str

    model_config = {"from_attributes": True}


class CaptchaResponse(BaseModel):
    captcha_id: str
    image_base64: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None
