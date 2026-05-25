from datetime import datetime, timedelta, timezone
import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class KeyfactorClient:
    def __init__(self):
        self.base_url = settings.keyfactor_base_url.rstrip("/")
        self.api_path = settings.keyfactor_api_path if settings.keyfactor_api_path.startswith("/") else f"/{settings.keyfactor_api_path}"
        self.base = f"{self.base_url}{self.api_path}"

    def _masked_username(self) -> str:
        username = settings.keyfactor_username.strip().strip('"').strip("'")
        if "\\" in username:
            domain, user = username.split("\\", 1)
            return f"{domain}\\{user[:2]}***"
        return f"{username[:2]}***" if username else "(empty)"

    def _resolved_username(self) -> str:
        username = settings.keyfactor_username.strip().strip('"').strip("'")
        if "\\" in username:
            return username
        if settings.keyfactor_domain:
            return f"{settings.keyfactor_domain}\\{username}"
        return username

    def _auth(self):
        if settings.keyfactor_auth_type.lower() == "basic":
            user = self._resolved_username()
            logger.info("Using basic auth with username=%s", self._masked_username())
            return (user, settings.keyfactor_password)
        return None

    def _get_headers(self):
        return {
            "x-keyfactor-requested-with": "APIClient",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _client(self):
        return httpx.Client(verify=settings.keyfactor_verify_tls, timeout=settings.keyfactor_timeout, auth=self._auth(), headers=self._get_headers())

    def health_check(self):
        swagger_url = f"{self.base}/swagger/index.html"
        cert_search_url = f"{self.base}/Certificates/Search"
        diag = {
            "ok": False,
            "base_url": self.base_url,
            "api_path": self.api_path,
            "swagger_url": swagger_url,
            "swagger_status": None,
            "cert_search_url": cert_search_url,
            "cert_search_status": None,
            "command_reachable": False,
            "auth_ok": False,
            "error": "",
            "diagnosis": "",
        }
        logger.info("Starting Keyfactor health check swagger=%s cert_search=%s", swagger_url, cert_search_url)
        try:
            with self._client() as c:
                swagger = c.get(swagger_url)
                diag["swagger_status"] = swagger.status_code
                if swagger.status_code == 200:
                    diag["command_reachable"] = True
                else:
                    diag["diagnosis"] = "Command API not reachable"
                    diag["error"] = f"Swagger status: {swagger.status_code}"
                    return diag

                payload = {"PageReturned": 1, "ReturnLimit": 1, "QueryString": "", "IncludeRevoked": False}
                cert = c.post(cert_search_url, json=payload)
                diag["cert_search_status"] = cert.status_code

                if cert.status_code == 200:
                    diag["ok"] = True
                    diag["auth_ok"] = True
                    diag["diagnosis"] = "Command reachable and authentication successful"
                elif cert.status_code in (401, 403):
                    diag["diagnosis"] = "Command reachable but authentication failed"
                    diag["error"] = cert.text[:500]
                else:
                    diag["diagnosis"] = "Command reachable but API call failed"
                    diag["error"] = cert.text[:500]

                logger.info("Keyfactor health result swagger_status=%s cert_status=%s diagnosis=%s", diag["swagger_status"], diag["cert_search_status"], diag["diagnosis"])
                return diag
        except Exception as exc:
            diag["diagnosis"] = "Command API not reachable"
            diag["error"] = str(exc)
            logger.exception("Keyfactor health check failed")
            return diag

    def list_certificates(self, page_size: int = 100):
        return self.search_certificates({"PageReturned": 1, "ReturnLimit": page_size, "QueryString": "", "IncludeRevoked": False})

    def search_certificates(self, payload: dict):
        with self._client() as c:
            r = c.post(f"{self.base}/Certificates/Search", json=payload)
            r.raise_for_status()
            return r.json()

    def get_expiring_certificates(self, days: int):
        end_dt = datetime.now(timezone.utc) + timedelta(days=days)
        primary = {
            "PageReturned": 1,
            "ReturnLimit": 250,
            "QueryString": "",
            "IncludeRevoked": False,
            "ExpirationDate": {"End": end_dt.isoformat()},
        }
        url = f"{self.base}/Certificates/Search"
        with self._client() as c:
            r = c.post(url, json=primary)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 400:
                fallback = {
                    "PageReturned": 1,
                    "ReturnLimit": 250,
                    "QueryString": f"Expires <= {end_dt.date().isoformat()}",
                    "IncludeRevoked": False,
                }
                r2 = c.post(url, json=fallback)
                if r2.status_code == 200:
                    return r2.json()
                raise RuntimeError({"url": url, "status_code": r2.status_code, "response": r2.text[:500]})
            raise RuntimeError({"url": url, "status_code": r.status_code, "response": r.text[:500]})

    def get_certificate_by_id(self, cert_id: int):
        with self._client() as c:
            r = c.get(f"{self.base}/Certificates/{cert_id}")
            r.raise_for_status()
            return r.json()

    def get_certificate_stores(self):
        with self._client() as c:
            r = c.get(f"{self.base}/CertificateStores")
            r.raise_for_status()
            return r.json()

    def get_orchestrator_jobs(self):
        with self._client() as c:
            r = c.get(f"{self.base}/OrchestratorJobs")
            r.raise_for_status()
            return r.json()

    def get_metadata_fields(self):
        with self._client() as c:
            r = c.get(f"{self.base}/MetadataFields")
            r.raise_for_status()
            return r.json()

    def get_inventory_summary(self):
        certs = self.list_certificates()
        rows = certs if isinstance(certs, list) else certs.get("Certificates", certs.get("Items", []))
        return {"total_certificates": len(rows)}
