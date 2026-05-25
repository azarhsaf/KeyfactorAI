from datetime import datetime, timedelta, timezone
import logging
from typing import Any
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
        if "@" in username:
            left, right = username.split("@", 1)
            return f"{left[:2]}***@{right}"
        if "\\" in username:
            domain, user = username.split("\\", 1)
            return f"{domain}\\{user[:2]}***"
        return f"{username[:2]}***" if username else "(empty)"

    def _resolved_username(self) -> str:
        username = settings.keyfactor_username.strip().strip('"').strip("'")
        if "\\" in username or "@" in username:
            return username
        if settings.keyfactor_domain:
            return f"{settings.keyfactor_domain}\\{username}"
        return username

    def _auth(self):
        if settings.keyfactor_auth_type.lower() == "basic":
            return (self._resolved_username(), settings.keyfactor_password)
        return None

    def _get_headers(self):
        return {
            "x-keyfactor-requested-with": "APIClient",
            "Accept": "application/json",
        }

    def _client(self):
        logger.info("Keyfactor client init base=%s user=%s", self.base, self._masked_username())
        return httpx.Client(verify=settings.keyfactor_verify_tls, timeout=settings.keyfactor_timeout, auth=self._auth(), headers=self._get_headers())

    def health_check(self) -> dict[str, Any]:
        endpoint = f"{self.base}/Certificates"
        diag: dict[str, Any] = {
            "ok": False,
            "status": "disconnected",
            "api_reachable": False,
            "authenticated": False,
            "permission_denied": False,
            "endpoint_tested": endpoint,
            "http_status_code": None,
            "message": "",
            "error": "",
        }
        logger.info("Starting Keyfactor health check endpoint=%s", endpoint)
        try:
            with self._client() as c:
                r = c.get(endpoint)
                diag["http_status_code"] = r.status_code
                diag["api_reachable"] = True
                if r.status_code == 200:
                    diag.update({"ok": True, "status": "connected", "authenticated": True, "message": "Connected and authenticated"})
                elif r.status_code == 401:
                    diag.update({"status": "auth_failed", "authenticated": False, "message": "Authentication failed"})
                elif r.status_code == 403:
                    diag.update({"status": "permission_denied", "authenticated": True, "permission_denied": True, "message": "Permission denied"})
                elif r.status_code == 405:
                    diag.update({"status": "method_or_endpoint_error", "message": "Wrong method or endpoint"})
                else:
                    diag.update({"status": "api_error", "message": f"API responded with HTTP {r.status_code}", "error": r.text[:500]})
                return diag
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            diag.update({"status": "network_error", "api_reachable": False, "authenticated": False, "message": "Network or TLS connectivity issue", "error": str(exc)})
            return diag
        except Exception as exc:
            diag.update({"status": "unknown_error", "api_reachable": False, "authenticated": False, "message": "Network or TLS connectivity issue", "error": str(exc)})
            return diag

    def list_certificates(self):
        with self._client() as c:
            r = c.get(f"{self.base}/Certificates")
            r.raise_for_status()
            return r.json()

    def search_certificates(self, payload: dict):
        logger.info("Certificates/Search unsupported in this deployment; using list_certificates fallback")
        return self.list_certificates()

    def _rows(self, raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            for key in ["Certificates", "Items", "Data"]:
                if isinstance(raw.get(key), list):
                    return raw[key]
        return []

    def get_expiring_certificates(self, days: int):
        rows = self._rows(self.list_certificates())
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)
        out = []
        for cert in rows:
            not_after = cert.get("NotAfter") or cert.get("ExpirationDate")
            if not not_after:
                continue
            try:
                dt = datetime.fromisoformat(str(not_after).replace("Z", "+00:00"))
                if days == 0:
                    if dt <= now:
                        out.append(cert)
                elif now <= dt <= end:
                    out.append(cert)
            except Exception:
                continue
        return out

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
        rows = self._rows(self.list_certificates())
        return {"total_certificates": len(rows)}
