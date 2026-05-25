from pydantic import BaseModel
from typing import Any


class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    prompt: str
    username: str = "admin"


class ChatResponse(BaseModel):
    answer: str
    source: str
    timestamp: str
    tool: str
    table: list[dict[str, Any]]
    diagnostics: dict[str, Any] | None = None
