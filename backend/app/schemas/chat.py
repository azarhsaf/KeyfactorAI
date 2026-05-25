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
    ai_summary: str | None = None
    source: str
    tool: str
    result_count: int
    ai_summary_status: str
    timestamp: str
    table: list[dict[str, Any]]
    diagnostics: dict[str, Any] | None = None
