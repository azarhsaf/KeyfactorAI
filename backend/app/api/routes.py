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
from app.tools.tool_registry import classify_prompt, now_iso, normalize_rows, to_table, group_count, GENERAL_PKI, supported_questions_grouped

router = APIRouter()

@router.get('/question-library')
def question_library():
    return supported_questions_grouped()

@router.post('/auth/login')
def login(payload: LoginRequest):
    if payload.username == settings.local_admin_username and payload.password == settings.local_admin_password:
        return {'ok': True, 'token': 'local-admin-token', 'username': payload.username}
    raise HTTPException(status_code=401, detail='Invalid credentials')

@router.get('/health')
def health():
    return {'ok': True, 'version': settings.app_version}

@router.get('/ollama/diagnostics')
def get_ollama_diagnostics():
    return ollama_diagnostics()

@router.get('/keyfactor/diagnostics')
def keyfactor_diagnostics(db: Session = Depends(get_db)):
    db_ok = True
    try: db.execute(text('SELECT 1'))
    except Exception: db_ok = False
    kf = KeyfactorClient()
    return {'timestamp': now_iso(), 'keyfactor': kf.health_check(), 'ollama': ollama_diagnostics(), 'database': {'ok': db_ok}}

@router.post('/chat', response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    tool, params, suggestions = classify_prompt(req.prompt)
    if tool == 'general_pki_answer':
        return ChatResponse(answer=GENERAL_PKI[params['topic']], ai_summary=None, source='Controlled PKI Knowledge', tool=tool, result_count=1, ai_summary_status='not_used', timestamp=now_iso(), table=[])
    if tool == 'invalid_sha128':
        return ChatResponse(answer='SHA-128 is not a standard certificate signature algorithm check supported by this tool. Did you mean SHA1 certificates or weak hash certificates?', ai_summary=None, source='Keyfactor Command API', tool=tool, result_count=0, ai_summary_status='not_used', timestamp=now_iso(), table=[])
    if tool == 'unsupported':
        msg = 'This question is not supported yet. Try one of these supported questions.'
        return ChatResponse(answer=msg, ai_summary='Suggestions: ' + '; '.join(suggestions[:5]), source='Keyfactor Command API', tool=tool, result_count=0, ai_summary_status='not_used', timestamp=now_iso(), table=[])

    kf = KeyfactorClient()
    health = kf.health_check()
    if not health.get('api_reachable'):
        return ChatResponse(answer='Network or TLS connectivity issue.', ai_summary=None, source='unavailable', tool='none', result_count=0, ai_summary_status='not_used', timestamp=now_iso(), table=[], diagnostics=health)

    rows = normalize_rows(kf.list_certificates())
    now = datetime.now(timezone.utc)
    result_rows = []
    answer = ''

    if tool in ('count_certificates','inventory_summary','list_certificates'):
        result_rows = rows
        answer = f'Found {len(rows)} total certificates in inventory.'
    elif tool in ('expired_certificates','count_expired_certificates'):
        result_rows = [r for r in rows if (dt:=_parse_dt(r.get('NotAfter') or r.get('ExpirationDate'))) and dt < now]
        answer = f"Found {len(result_rows)} expired certificates."
    elif tool == 'expiring_certificates':
        d = params.get('days', 30)
        lo, hi = now, now + timedelta(days=d)
        result_rows = [r for r in rows if (dt:=_parse_dt(r.get('NotAfter') or r.get('ExpirationDate'))) and lo <= dt <= hi]
        answer = f'Found {len(result_rows)} certificates expiring within the next {d} days.'
    elif tool == 'group_by_issuer':
        result_rows = group_count(rows, 'issuer'); answer = f'Found {len(result_rows)} issuer groups.'
    elif tool == 'group_by_template':
        result_rows = group_count(rows, 'template'); answer = f'Found {len(result_rows)} template groups.'
    elif tool == 'group_by_owner':
        result_rows = group_count(rows, 'owner'); answer = f'Found {len(result_rows)} owner groups.'
    elif tool == 'group_by_expiry_year':
        counts={}
        for r in rows:
            if (dt:=_parse_dt(r.get('NotAfter') or r.get('ExpirationDate'))): counts[dt.year]=counts.get(dt.year,0)+1
        result_rows=[{'year':y,'count':c} for y,c in sorted(counts.items())]; answer=f'Found expiry distribution across {len(result_rows)} years.'
    elif tool == 'sha1_certificates':
        result_rows=[r for r in rows if 'sha1' in str(r.get('SignatureAlgorithm','')).lower()]; answer=f'Found {len(result_rows)} SHA1 certificates.'
    elif tool == 'md5_certificates':
        result_rows=[r for r in rows if 'md5' in str(r.get('SignatureAlgorithm','')).lower()]; answer=f'Found {len(result_rows)} MD5 certificates.'
    elif tool == 'weak_crypto_summary':
        result_rows=[r for r in rows if any(x in str(r.get('SignatureAlgorithm','')).lower() for x in ['sha1','md5'])]; answer=f'Found {len(result_rows)} weak-hash certificates.'
    elif tool == 'rsa_less_than_2048':
        result_rows=[r for r in rows if 'rsa' in str(r.get('KeyAlgorithm','')).lower() and _safe_int(r.get('KeySize')) < 2048]; answer=f'Found {len(result_rows)} RSA certificates less than 2048-bit.'
    elif tool == 'owner_missing':
        result_rows=[r for r in rows if not (r.get('OwnerRoleName') or r.get('Owner'))]; answer=f'Found {len(result_rows)} certificates without owner metadata.'
    elif tool == 'template_missing':
        result_rows=[r for r in rows if not (r.get('TemplateName') or r.get('TemplateId'))]; answer=f'Found {len(result_rows)} certificates without template metadata.'
    elif tool == 'metadata_missing':
        result_rows=[r for r in rows if not (r.get('OwnerRoleName') and (r.get('TemplateName') or r.get('TemplateId')) and (r.get('IssuedCN') or r.get('CommonName') or r.get('CN')))]; answer=f'Found {len(result_rows)} certificates with missing metadata.'
    elif tool == 'unknown_issuer':
        result_rows=[r for r in rows if not r.get('IssuerDN')]; answer=f'Found {len(result_rows)} certificates with unknown issuer.'
    elif tool == 'cn_missing':
        result_rows=[r for r in rows if not (r.get('IssuedCN') or r.get('CommonName') or r.get('CN'))]; answer=f'Found {len(result_rows)} certificates without CN.'
    elif tool == 'top_expiring_certificates':
        limit=params.get('limit',10); cand=[(dt,r) for r in rows if (dt:=_parse_dt(r.get('NotAfter') or r.get('ExpirationDate'))) and dt>=now]; cand.sort(key=lambda x:x[0]); result_rows=[r for _,r in cand[:limit]]; answer=f'Found top {len(result_rows)} certificates expiring soon.'
    elif tool == 'long_validity':
        days=params.get('days',398); result_rows=[]
        for r in rows:
            nb=_parse_dt(r.get('NotBefore')); na=_parse_dt(r.get('NotAfter') or r.get('ExpirationDate'))
            if nb and na and (na-nb).days>days: result_rows.append(r)
        answer=f'Found {len(result_rows)} certificates valid more than {days} days.'
    elif tool == 'weak_expiring_soon':
        hi=now+timedelta(days=30)
        result_rows=[r for r in rows if (dt:=_parse_dt(r.get('NotAfter') or r.get('ExpirationDate'))) and now<=dt<=hi and ('sha1' in str(r.get('SignatureAlgorithm','')).lower() or ('rsa' in str(r.get('KeyAlgorithm','')).lower() and _safe_int(r.get('KeySize'))<2048))]
        answer=f'Found {len(result_rows)} weak certificates expiring in the next 30 days.'
    else:
        return ChatResponse(answer='This question is not supported yet. Try one of these supported questions.', ai_summary=None, source='Keyfactor Command API', tool='unsupported', result_count=0, ai_summary_status='not_used', timestamp=now_iso(), table=[])

    ai_summary=None; ai_status='disabled'
    if settings.enable_ai_summary:
        ai_summary, ai_status = summarize_with_llm(req.prompt, answer)

    table = result_rows if (result_rows and isinstance(result_rows[0], dict) and ('count' in result_rows[0] or 'year' in result_rows[0] or 'name' in result_rows[0])) else to_table(result_rows, limit=50)
    db.add(AuditLog(username=req.username,prompt=req.prompt,selected_tool=tool,data_source='Keyfactor Command API',result_count=len(result_rows),response_summary=answer)); db.commit()
    return ChatResponse(answer=answer, ai_summary=ai_summary, source='Keyfactor Command API', tool=tool, result_count=len(result_rows), ai_summary_status=ai_status, timestamp=now_iso(), table=table, diagnostics={'records_scanned': len(rows)})

@router.get('/audit')
def audit_logs(db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()

def _parse_dt(v):
    if not v: return None
    try: return datetime.fromisoformat(str(v).replace('Z','+00:00'))
    except Exception: return None

def _safe_int(v):
    try: return int(v)
    except Exception: return 0
