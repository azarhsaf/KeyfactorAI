# Keyfactor AI Assistant

Offline-first Docker Compose AI assistant for Keyfactor Command using read-only external integration.

## Architecture
- Frontend: React + Vite chat UI with suggested prompts, table rendering, and CSV export.
- Backend: FastAPI with prompt classification, safe tool routing, Keyfactor API client, audit logging.
- Model: Ollama container with configurable model and offline preload mode.
- DB: PostgreSQL for audit logs/history.
- Reverse proxy: NGINX at `http://<server-ip>:8090`.

## Files Created
- `docker-compose.yml`
- `.env.example`
- `nginx/default.conf`
- `backend/*`
- `frontend/*`

## Configure `.env`
```bash
cp .env.example .env
```
Set:
- `KEYFACTOR_BASE_URL`
- `KEYFACTOR_API_PATH` (default `/KeyfactorAPI`)
- `KEYFACTOR_AUTH_TYPE` / credentials
- `KEYFACTOR_VERIFY_TLS`
- `OLLAMA_MODEL`
- `OFFLINE_MODE`

## Online model pull mode (dev)
1. Set `AUTO_PULL_MODEL=true`.
2. Start stack.
3. Pull model in ollama container:
```bash
docker compose exec ollama ollama pull qwen2.5:3b-instruct
```

## Offline model preload mode (production)
1. On connected machine, pull model.
2. Copy Ollama model volume or `~/.ollama/models` to offline VM.
3. Mount/preload into `ollama_data` volume.
4. Set `OFFLINE_MODE=true` and do not run pull commands.

## Start
```bash
docker compose up -d --build
```
Open: `http://server-ip:8090`

## Test questions
1. How many certificates expire next week?
2. Show certificates expiring in 30 days.
3. Which certificates are already expired?
4. Show failed orchestrator jobs.
5. Show certificate inventory by template.

## Known limitations (MVP)
- Tool classifier is keyword-based and currently covers core prompts only.
- Keyfactor endpoint paths can vary by version; update paths in `backend/app/services/keyfactor_client.py`.
- SQL read-only fallback is scaffolded via env flags but not enabled by default.
- Local admin login only (LDAP/AD planned later).
