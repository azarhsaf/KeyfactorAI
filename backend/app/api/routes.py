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


@router.post("/command/test")
def test_command():
    return KeyfactorClient().health_check()


@router.get("/keyfactor/diagnostics")
def keyfactor_diagnostics(db: Session = Depends(get_db)):
    kf = KeyfactorClient()
    health = kf.health_check()
    model_status = summarize_with_llm("health", "model check") != "model check"
    db_ok = True
    db_error = ""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_ok = False
        db_error = str(exc)

    return {
        "timestamp": now_iso(),
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "env_loaded": True,
        "keyfactor": {
            **health,
            "username": kf._masked_username(),
            "password": "********",
        },
        "model": {"provider": settings.llm_provider, "model": settings.ollama_model, "reachable": model_status},
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
    logger.info("Selected tool=%s params=%s", tool, params)
    kf = KeyfactorClient()
    health = kf.health_check()

    source = "Keyfactor Command API"
    table = []
    answer = ""
    diagnostic = None

    if not health.get("command_reachable"):
        source = "unavailable"
        answer = f"Command API is not reachable. Tested {health.get('swagger_url')} and got status {health.get('swagger_status')}. Error: {health.get('error') or 'n/a'}"
        diagnostic = health
        tool = "none"
    elif not health.get("auth_ok"):
        source = "unavailable"
        answer = f"Command is reachable but authentication/API call failed. Status: {health.get('cert_search_status')}."
        diagnostic = health
        tool = "none"
    else:
        try:
            if tool == "count_expiring_certificates":
                raw = kf.get_expiring_certificates(params["days"])
                table = format_expiring_rows(raw)
                facts = f"There are {len(table)} certificates expiring in the next {params['days']} days."
            elif tool == "get_expiring_certificates":
                raw = kf.get_expiring_certificates(params["days"])
                table = format_expiring_rows(raw)
                facts = f"Found {len(table)} certificates for the requested expiry range."
            elif tool == "get_expired_certificates":
                raw = kf.get_expiring_certificates(0)
                table = format_expiring_rows(raw)
                facts = f"Found {len(table)} expired certificates."
            elif tool == "get_failed_orchestrator_jobs":
                rows = kf.get_orchestrator_jobs()
                table = [r for r in rows if str(r.get("Status", "")).lower() == "failed"]
                facts = f"Found {len(table)} failed orchestrator jobs."
            else:
                summary = kf.get_inventory_summary()
                table = [summary]
                facts = f"Inventory summary total certificates: {summary.get('total_certificates', 0)}."

            answer = summarize_with_llm(req.prompt, facts)
        except Exception as exc:
            logger.exception("Tool execution failed")
            source = "unavailable"
            answer = f"Command request failed while executing tool {tool}: {str(exc)}"
            diagnostic = health

    logger.info("Chat result tool=%s result_count=%s source=%s", tool, len(table), source)
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
