import httpx
from app.core.config import settings


def summarize_with_llm(prompt: str, facts: str) -> str:
    if settings.llm_provider != "ollama":
        return facts
    try:
        with httpx.Client(timeout=60) as c:
            r = c.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": f"Summarize this Keyfactor result without adding facts. User prompt: {prompt}\nFacts: {facts}",
                    "stream": False,
                },
            )
            r.raise_for_status()
            return r.json().get("response", facts)
    except Exception:
        return facts
