import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.schemas.chat import LoginRequest, ChatRequest, ChatResponse
from app.core.config import settings
from app.core.db import get_db
from app.models.audit import AuditLog
from app.services.keyfactor_client import KeyfactorClient
from app.services.llm_service import summarize_with_llm
from app.tools.tool_registry import classify_prompt, now_iso, format_expiring_rows

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/auth/login")
def login(payload: LoginRequest):
    if payload.username == settings.local_admin_username and payload.password == settings.local_admin_password:
        return {"ok": True, "token": "local-admin-token", "username": payload.username}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/health")
def health():
    return {"ok": True, "version": settings.app_version}


@router.get("/keyfactor/diagnostics")
def keyfactor_diagnostics(db: Session = Depends(get_db)):
    kf = KeyfactorClient()
    health = kf.health_check()
    _, model_ok = summarize_with_llm("health", "model check")
    db_ok = True
    db_error = ""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_ok = False
        db_error = str(exc)

    return {
        "timestamp": now_iso(),
        "frontend_status": "served_by_nginx",
        "backend_status": "running",
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "keyfactor": {**health, "username": kf._masked_username(), "password": "********"},
        "ollama": {"provider": settings.llm_provider, "model": settings.ollama_model, "status": "connected" if model_ok else "unavailable"},
        "database": {"ok": db_ok, "error": db_error},
    }


@router.get("/keyfactor/test-expiring")
def keyfactor_test_expiring(days: int = Query(default=7, ge=0, le=365)):
    raw = KeyfactorClient().get_expiring_certificates(days)
    rows = format_expiring_rows(raw)
    return {"days": days, "count": len(rows), "first_10": rows[:10]}


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    tool, params = classify_prompt(req.prompt)
    kf = KeyfactorClient()
    health = kf.health_check()

    source = "Keyfactor Command API"
    table = []
    answer = ""
    diagnostic = None

    if not health.get("api_reachable"):
        source = "unavailable"
        answer = f"Network or TLS connectivity issue. Endpoint tested: {health.get('endpoint_tested')}."
        diagnostic = health
        tool = "none"
    elif not health.get("authenticated") and health.get("http_status_code") == 401:
        source = "unavailable"
        answer = "Authentication failed while accessing Keyfactor API."
        diagnostic = health
        tool = "none"
    elif health.get("http_status_code") == 403:
        source = "unavailable"
        answer = "Keyfactor API reachable but permission denied for this account."
        diagnostic = health
        tool = "none"
    else:
        try:
            if tool == "count_expiring_certificates":
                table = format_expiring_rows(kf.get_expiring_certificates(params["days"]))
                facts = f"There are {len(table)} certificates expiring in the next {params['days']} days."
            elif tool == "get_expiring_certificates":
                table = format_expiring_rows(kf.get_expiring_certificates(params["days"]))
                facts = f"Found {len(table)} certificates expiring in {params['days']} days."
            elif tool == "get_expired_certificates":
                table = format_expiring_rows(kf.get_expiring_certificates(0))
                facts = f"Found {len(table)} expired certificates."
            elif tool == "get_failed_orchestrator_jobs":
                rows = kf.get_orchestrator_jobs()
                table = [r for r in rows if str(r.get("Status", "")).lower() == "failed"]
                facts = f"Found {len(table)} failed orchestrator jobs."
            else:
                summary = kf.get_inventory_summary()
                table = [summary]
                facts = f"Inventory summary total certificates: {summary.get('total_certificates', 0)}."
            answer, _ = summarize_with_llm(req.prompt, facts)
        except Exception as exc:
            source = "unavailable"
            answer = f"Tool execution failed: {exc}"
            diagnostic = health

    row = AuditLog(
        username=req.username,
        prompt=req.prompt,
        selected_tool=tool,
        data_source=source,
        result_count=len(table),
        response_summary=answer,
        error=None if source != "unavailable" else str(diagnostic),
    )
    db.add(row)
    db.commit()

    return ChatResponse(answer=answer, source=source, timestamp=now_iso(), tool=tool, table=table, diagnostics=diagnostic)


@router.get("/audit")
def audit_logs(db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    return logs
