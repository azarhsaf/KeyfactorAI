from datetime import datetime, timedelta, timezone
import httpx
from app.core.config import settings


class KeyfactorClient:
    def __init__(self):
        self.base = f"{settings.keyfactor_base_url.rstrip('/')}{settings.keyfactor_api_path}"

    def _auth(self):
        if settings.keyfactor_auth_type.lower() == "basic":
            return (settings.keyfactor_username, settings.keyfactor_password)
        return None

    def health_check(self):
        try:
            with httpx.Client(verify=settings.keyfactor_verify_tls, timeout=settings.keyfactor_timeout, auth=self._auth()) as c:
                r = c.get(f"{self.base}/Status")
                return {"ok": r.status_code < 400, "status_code": r.status_code}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def list_certificates(self, page_size: int = 100):
        return self.search_certificates({"Limit": page_size})

    def search_certificates(self, payload: dict):
        with httpx.Client(verify=settings.keyfactor_verify_tls, timeout=settings.keyfactor_timeout, auth=self._auth()) as c:
            r = c.post(f"{self.base}/Certificates/Search", json=payload)
            r.raise_for_status()
            return r.json()

    def get_expiring_certificates(self, days: int):
        end = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        payload = {"PageReturned": 1, "ReturnLimit": 250, "QueryString": "", "IncludeRevoked": False, "ExpirationDate": {"End": end}}
        return self.search_certificates(payload)

    def get_certificate_by_id(self, cert_id: int):
        with httpx.Client(verify=settings.keyfactor_verify_tls, timeout=settings.keyfactor_timeout, auth=self._auth()) as c:
            r = c.get(f"{self.base}/Certificates/{cert_id}")
            r.raise_for_status()
            return r.json()

    def get_certificate_stores(self):
        with httpx.Client(verify=settings.keyfactor_verify_tls, timeout=settings.keyfactor_timeout, auth=self._auth()) as c:
            r = c.get(f"{self.base}/CertificateStores")
            r.raise_for_status()
            return r.json()

    def get_orchestrator_jobs(self):
        with httpx.Client(verify=settings.keyfactor_verify_tls, timeout=settings.keyfactor_timeout, auth=self._auth()) as c:
            r = c.get(f"{self.base}/OrchestratorJobs")
            r.raise_for_status()
            return r.json()

    def get_metadata_fields(self):
        with httpx.Client(verify=settings.keyfactor_verify_tls, timeout=settings.keyfactor_timeout, auth=self._auth()) as c:
            r = c.get(f"{self.base}/MetadataFields")
            r.raise_for_status()
            return r.json()

    def get_inventory_summary(self):
        certs = self.list_certificates()
        rows = certs if isinstance(certs, list) else certs.get("Certificates", [])
        return {"total_certificates": len(rows)}
