import httpx
from app.core.config import settings


FALLBACK_MODEL_MISSING = "AI summary unavailable: model not found"
FALLBACK_UNAVAILABLE = "AI summary unavailable, but deterministic Keyfactor result is available."


def ollama_diagnostics() -> dict:
    out = {
        "reachable": False,
        "model": settings.ollama_model,
        "model_available": False,
        "status": "unavailable",
        "error": "",
        "available_models": [],
    }
    if settings.llm_provider != "ollama":
        out["status"] = "disabled"
        return out
    try:
        with httpx.Client(timeout=15) as c:
            r = c.get(f"{settings.ollama_base_url}/api/tags")
            if r.status_code != 200:
                out["error"] = f"HTTP {r.status_code}"
                return out
            out["reachable"] = True
            data = r.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            out["available_models"] = models
            if settings.ollama_model in models:
                out["model_available"] = True
                out["status"] = "available"
            else:
                out["status"] = "model_missing"
            return out
    except Exception as exc:
        out["error"] = str(exc)
        return out


def summarize_with_llm(prompt: str, facts: str) -> tuple[str, str]:
    diag = ollama_diagnostics()
    if diag["status"] != "available":
        msg = FALLBACK_MODEL_MISSING if diag["status"] == "model_missing" else FALLBACK_UNAVAILABLE
        return f"{facts} {msg}", diag["status"]
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(
                f"{settings.ollama_base_url}/api/generate",
                json={"model": settings.ollama_model, "prompt": f"Summarize this Keyfactor result without adding facts. User prompt: {prompt}\nFacts: {facts}", "stream": False},
            )
            if r.status_code == 404:
                return f"{facts} {FALLBACK_MODEL_MISSING}", "model_missing"
            r.raise_for_status()
            return r.json().get("response", facts), "available"
    except Exception:
        return f"{facts} {FALLBACK_UNAVAILABLE}", "unavailable"
