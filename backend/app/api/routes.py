from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.schemas.chat import LoginRequest, ChatRequest, ChatResponse
from app.core.config import settings
from app.core.db import get_db
from app.models.audit import AuditLog
from app.services.keyfactor_client import KeyfactorClient
from app.services.llm_service import summarize_with_llm, ollama_diagnostics
from app.tools.tool_registry import classify_prompt, now_iso, normalize_rows, to_table, group_count

router = APIRouter()


@router.post("/auth/login")
def login(payload: LoginRequest):
    if payload.username == settings.local_admin_username and payload.password == settings.local_admin_password:
        return {"ok": True, "token": "local-admin-token", "username": payload.username}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/health")
def health():
    return {"ok": True, "version": settings.app_version}


@router.get("/ollama/diagnostics")
def get_ollama_diagnostics():
    return ollama_diagnostics()


@router.get("/keyfactor/diagnostics")
def keyfactor_diagnostics(db: Session = Depends(get_db)):
    kf = KeyfactorClient()
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "timestamp": now_iso(),
        "frontend_status": "served_by_nginx",
        "backend_status": "running",
        "app_version": settings.app_version,
        "keyfactor": {**kf.health_check(), "username": kf._masked_username(), "password": "********"},
        "ollama": ollama_diagnostics(),
        "database": {"ok": db_ok},
    }


@router.get("/keyfactor/test-expiring")
def keyfactor_test_expiring(days: int = Query(default=7, ge=0, le=365)):
    rows = KeyfactorClient().get_expiring_certificates(days)
    return {"days": days, "count": len(rows), "first_10": to_table(rows, limit=10)}


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    tool, params = classify_prompt(req.prompt)
    kf = KeyfactorClient()
    health = kf.health_check()
    source = "Keyfactor Command API"

    if not health.get("api_reachable"):
        return ChatResponse(answer="Network or TLS connectivity issue.", source="unavailable", tool="none", result_count=0, ai_summary_status="not_used", timestamp=now_iso(), table=[], diagnostics=health)

    all_rows = normalize_rows(kf.list_certificates())
    now = datetime.now(timezone.utc)
    result_rows = []
    answer = ""

    if tool == "count_expiring_certificates":
        d = params["days"]
        result_rows = [r for r in all_rows if (lambda dt: dt and now <= dt <= now + timedelta(days=d))( _parse_dt(r.get("NotAfter") or r.get("ExpirationDate")) )]
        answer = f"Found {len(result_rows)} certificates expiring in the next {d} days."
    elif tool == "get_expiring_certificates":
        d = params["days"]
        result_rows = [r for r in all_rows if (lambda dt: dt and now <= dt <= now + timedelta(days=d))( _parse_dt(r.get("NotAfter") or r.get("ExpirationDate")) )]
        answer = f"Found {len(result_rows)} certificates expiring in the next {d} days."
    elif tool == "get_expired_certificates":
        result_rows = [r for r in all_rows if (lambda dt: dt and dt < now)(_parse_dt(r.get("NotAfter") or r.get("ExpirationDate")))]
        answer = f"Found {len(result_rows)} expired certificates."
    elif tool == "count_expired_certificates":
        result_rows = [r for r in all_rows if (lambda dt: dt and dt < now)(_parse_dt(r.get("NotAfter") or r.get("ExpirationDate")))]
        answer = f"There are {len(result_rows)} expired certificates."
    elif tool == "sha1_certificates":
        result_rows = [r for r in all_rows if "sha1" in str(r.get("SignatureAlgorithm", "")).lower()]
        answer = f"Found {len(result_rows)} SHA1 certificates."
    elif tool == "rsa_less_than_2048_certificates":
        result_rows = [r for r in all_rows if "rsa" in str(r.get("KeyAlgorithm", "")).lower() and _safe_int(r.get("KeySize")) < 2048]
        answer = f"Found {len(result_rows)} RSA certificates with key size less than 2048."
    elif tool == "certificates_without_owner":
        result_rows = [r for r in all_rows if not (r.get("OwnerRoleName") or r.get("Owner"))]
        answer = f"Found {len(result_rows)} certificates without owner metadata."
    elif tool == "certificates_by_issuer":
        grouped = group_count(all_rows, "issuer")
        answer = f"Found {len(grouped)} issuer groups."
        result_rows = grouped
    elif tool == "certificates_by_template":
        grouped = group_count(all_rows, "template")
        answer = f"Found {len(grouped)} template groups."
        result_rows = grouped
    elif tool == "certificates_by_expiry_year":
        years = {}
        for r in all_rows:
            dt = _parse_dt(r.get("NotAfter") or r.get("ExpirationDate"))
            if dt:
                years[dt.year] = years.get(dt.year, 0) + 1
        result_rows = [{"year": y, "count": c} for y, c in sorted(years.items())]
        answer = f"Found expiry distribution across {len(result_rows)} years."
    elif tool == "top_expiring_certificates":
        limit = params.get("limit", 10)
        candidates = []
        for r in all_rows:
            dt = _parse_dt(r.get("NotAfter") or r.get("ExpirationDate"))
            if dt and dt >= now:
                candidates.append((dt, r))
        candidates.sort(key=lambda x: x[0])
        result_rows = [r for _, r in candidates[:limit]]
        answer = f"Top {len(result_rows)} certificates expiring soon."
    elif tool == "get_failed_orchestrator_jobs":
        jobs = kf.get_orchestrator_jobs()
        result_rows = [r for r in jobs if str(r.get("Status", "")).lower() == "failed"]
        answer = f"Found {len(result_rows)} failed jobs."
    else:
        result_rows = [{"total_certificates": len(all_rows)}]
        answer = f"Inventory summary: total certificates = {len(all_rows)}."

    final_answer, ai_status = summarize_with_llm(req.prompt, answer)
    table = result_rows if (result_rows and isinstance(result_rows[0], dict) and ("count" in result_rows[0] or "year" in result_rows[0])) else to_table(result_rows, limit=50)

    db.add(AuditLog(username=req.username, prompt=req.prompt, selected_tool=tool, data_source=source, result_count=len(result_rows), response_summary=final_answer))
    db.commit()

    return ChatResponse(answer=final_answer, source=source, tool=tool, result_count=len(result_rows), ai_summary_status=ai_status, timestamp=now_iso(), table=table, diagnostics=health)


@router.get("/audit")
def audit_logs(db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()


def _parse_dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def _safe_int(v):
    try:
        return int(v)
    except Exception:
        return 0
