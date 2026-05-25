import json
import httpx
from app.core.config import settings

STRICT_SUMMARY_PREFIX = (
    "You are summarizing a deterministic Keyfactor Command API result. "
    "Do not add any new facts. Do not estimate. Do not use approximate language. "
    "Do not mention anything not present in the provided result. Keep the answer short and factual."
)


def ollama_diagnostics() -> dict:
    out = {"reachable": False, "model": settings.ollama_model, "model_available": False, "status": "unavailable", "error": "", "available_models": []}
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
            models = [m.get("name", "") for m in r.json().get("models", [])]
            out["available_models"] = models
            out["model_available"] = settings.ollama_model in models
            out["status"] = "available" if out["model_available"] else "model_missing"
            return out
    except Exception as exc:
        out["error"] = str(exc)
        return out


def summarize_with_llm(prompt: str, deterministic_text: str) -> tuple[str, str]:
    diag = ollama_diagnostics()
    if diag["status"] != "available":
        if diag["status"] == "model_missing":
            return "AI summary unavailable: model not found", diag["status"]
        return "AI summary unavailable, but deterministic Keyfactor result is available.", diag["status"]
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": f"{STRICT_SUMMARY_PREFIX}\nUser question: {prompt}\nDeterministic result: {deterministic_text}",
                    "stream": False,
                    "options": {"temperature": 0, "top_p": 0.1, "repeat_penalty": 1.1},
                },
            )
            if r.status_code == 404:
                return "AI summary unavailable: model not found", "model_missing"
            r.raise_for_status()
            txt = r.json().get("response", "").strip()
            banned = ["approximately", "around", "maybe", "probably", "discovered", "ai assistant"]
            if any(b in txt.lower() for b in banned):
                return "AI summary suppressed due to non-deterministic wording.", "suppressed"
            return txt or "AI summary unavailable, but deterministic Keyfactor result is available.", "available"
    except Exception:
        return "AI summary unavailable, but deterministic Keyfactor result is available.", "unavailable"
