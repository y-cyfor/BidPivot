from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Uniform API envelope documented in OpenAPI."""

    code: int = 200
    data: T | None = None
    message: str = "ok"
