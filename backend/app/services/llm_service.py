import httpx
from app.core.config import settings


FALLBACK_MESSAGE = "AI summary unavailable, but deterministic Keyfactor result is available."


def summarize_with_llm(prompt: str, facts: str) -> tuple[str, bool]:
    if settings.llm_provider != "ollama":
        return facts, False
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": f"Summarize this Keyfactor result without adding facts. User prompt: {prompt}\nFacts: {facts}",
                    "stream": False,
                },
            )
            if r.status_code == 404:
                return f"{facts} {FALLBACK_MESSAGE}", False
            r.raise_for_status()
            return r.json().get("response", facts), True
    except Exception:
        return f"{facts} {FALLBACK_MESSAGE}", False
