# Keyfactor AI Assistant

Offline-first Docker Compose AI assistant for Keyfactor Command using read-only external integration.

## Architecture
- Frontend: React + Vite build output served by frontend NGINX container.
- Backend: FastAPI with deterministic prompt classification, safe tool routing, diagnostics, and audit logging.
- Model: Ollama container (optional for summarization, deterministic mode still works without it).
- DB: PostgreSQL for audit logs/history.
- Reverse proxy: outer NGINX at `http://<server-ip>:8090`.

## Version in GUI
- The sidebar shows `Version <app_version> (release)` from backend diagnostics.

## Configure `.env`
```bash
cp .env.example .env
```
Set Keyfactor settings and credentials.

## Start / Rebuild
```bash
docker compose down
docker compose up -d --build
```
Open: `http://172.16.21.186:8090`

## Key API endpoints
- `GET /api/keyfactor/diagnostics`
- `GET /api/keyfactor/test-expiring?days=7`
- `POST /api/chat`
- `POST /api/command/test`

## Troubleshooting commands
```bash
docker compose exec backend python - << 'PY'
import httpx
auth=("irfan.lab\\svc_kf_service","Admin@123")
base="https://172.16.21.184/KeyfactorAPI"
for p in ["/swagger/index.html", "/Certificates/Search"]:
    if p == "/Certificates/Search":
        r=httpx.post(base+p,json={"PageReturned":1,"ReturnLimit":1,"QueryString":"","IncludeRevoked":False},auth=auth,verify=False,timeout=30,headers={"x-keyfactor-requested-with":"APIClient"})
    else:
        r=httpx.get(base+p,auth=auth,verify=False,timeout=30)
    print(p, r.status_code, r.text[:300])
PY

curl http://172.16.21.186:8090/api/keyfactor/diagnostics
curl "http://172.16.21.186:8090/api/keyfactor/test-expiring?days=7"
```

## Health behavior
- Uses swagger reachability (`/swagger/index.html`) and authenticated `/Certificates/Search`.
- If swagger=200 + auth fails (401/403), diagnosis is: `Command reachable but authentication failed`.
- If swagger unreachable, diagnosis is: `Command API not reachable`.

## Known limitations
- Intent parsing is deterministic/rule-based and currently focused on MVP questions.
- Keyfactor endpoint response shapes may vary by Command version.
- SQL read-only fallback remains future scope.
