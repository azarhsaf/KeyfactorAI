from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.chat import LoginRequest, ChatRequest, ChatResponse
from app.core.config import settings
from app.core.db import get_db
from app.models.audit import AuditLog
from app.services.keyfactor_client import KeyfactorClient
from app.services.llm_service import summarize_with_llm
from app.tools.tool_registry import classify_prompt, now_iso, format_expiring_rows

router = APIRouter()


@router.post("/auth/login")
def login(payload: LoginRequest):
    if payload.username == settings.local_admin_username and payload.password == settings.local_admin_password:
        return {"ok": True, "token": "local-admin-token", "username": payload.username}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/health")
def health():
    return {"ok": True}


@router.post("/command/test")
def test_command():
    return KeyfactorClient().health_check()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    tool, params = classify_prompt(req.prompt)
    kf = KeyfactorClient()
    source = "command_api"
    table = []

    try:
        if tool == "count_expiring_certificates":
            raw = kf.get_expiring_certificates(params["days"])
            table = format_expiring_rows(raw)
            facts = f"There are {len(table)} certificates expiring in the next {params['days']} days."
        elif tool == "get_expiring_certificates":
            raw = kf.get_expiring_certificates(params["days"])
            table = format_expiring_rows(raw)
            facts = f"Found {len(table)} certificate records."
        elif tool == "get_failed_orchestrator_jobs":
            rows = kf.get_orchestrator_jobs()
            table = [r for r in rows if str(r.get('Status', '')).lower() == 'failed']
            facts = f"Found {len(table)} failed orchestrator jobs."
        else:
            summary = kf.get_inventory_summary()
            table = [summary]
            facts = f"Total certificates discovered: {summary.get('total_certificates', 0)}."
        answer = summarize_with_llm(req.prompt, facts)
    except Exception:
        source = "unavailable"
        answer = "I cannot answer because Keyfactor Command connection is unavailable."
        tool = "none"

    row = AuditLog(
        username=req.username,
        prompt=req.prompt,
        selected_tool=tool,
        data_source=source,
        result_count=len(table),
        response_summary=answer,
    )
    db.add(row)
    db.commit()

    return ChatResponse(answer=answer, source=source, timestamp=now_iso(), tool=tool, table=table)


@router.get("/audit")
def audit_logs(db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    return logs
