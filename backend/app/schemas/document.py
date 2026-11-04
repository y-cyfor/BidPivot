from pydantic import BaseModel


class DocumentUpdate(BaseModel):
    content_html: str | None = None
    content_json: dict | None = None
