from collections import Counter
from datetime import datetime, timezone
from typing import Any

SUPPORTED_QUESTIONS = [
    "total certificates",
    "expired certificates",
    "certificates expiring next week / 7 days / 30 days",
    "SHA1 certificates",
    "weak hash certificates",
    "RSA less than 2048",
    "certificates without owner",
    "certificates by issuer",
    "certificates by template",
    "top expiring certificates",
    "inventory summary",
    "what is PKI / CA / certificate / CRL / OCSP",
]

GENERAL_PKI = {
    "pki": "PKI means Public Key Infrastructure. It is the system used to issue, manage, validate, and revoke digital certificates.",
    "ca": "A CA is a Certificate Authority that issues and signs digital certificates.",
    "certificate": "A digital certificate binds an identity to a public key and is used for authentication and encryption.",
    "crl": "A CRL is a Certificate Revocation List used to publish revoked certificates.",
    "ocsp": "OCSP is the Online Certificate Status Protocol used to check certificate revocation status in real time.",
}


def classify_prompt(prompt: str):
    p = prompt.lower().strip()
    if "sha128" in p:
        return "invalid_sha128", {}
    for k in GENERAL_PKI:
        if f"what is {k}" in p or p == k:
            return "general_pki_question", {"topic": k}
    if "top" in p and "expiring" in p:
        return "top_expiring_certificates", {"limit": 10}
    if "total weak" in p or "weak algorithm" in p or "weak hash" in p:
        return "weak_algorithm_summary", {}
    if ("how many" in p or "count" in p) and "expired" in p:
        return "count_expired_certificates", {}
    if "show" in p and "expired" in p:
        return "get_expired_certificates", {}
    if "next week" in p or "7 days" in p:
        return "count_expiring_certificates", {"days": 7}
    if "30 days" in p:
        return "get_expiring_certificates", {"days": 30}
    if "sha1" in p:
        return "sha1_certificates", {}
    if "weak rsa" in p or "rsa less than 2048" in p or "below 2048" in p:
        return "rsa_less_than_2048_certificates", {}
    if "without owner" in p or "orphan" in p:
        return "certificates_without_owner", {}
    if "issuer" in p and "count" in p:
        return "certificates_by_issuer", {}
    if "template" in p and "count" in p:
        return "certificates_by_template", {}
    if "expiry year" in p:
        return "certificates_by_expiry_year", {}
    if "failed" in p and "job" in p:
        return "get_failed_orchestrator_jobs", {}
    if "inventory" in p or "total certificates" in p:
        return "inventory_summary", {}
    return "unsupported", {}


def planner_fallback_json(intent: str, filters: dict[str, Any] | None = None):
    return {
        "intent": intent,
        "method": "GET",
        "endpoint": "/Certificates",
        "filters": filters or {
            "expiry_days": None,
            "expired": False,
            "sha1": False,
            "weak_rsa": False,
            "owner_missing": False,
            "template": None,
            "issuer": None,
        },
        "limit": 20,
        "explanation": "Rule-based fallback intent",
    }


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def normalize_rows(raw: Any):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for k in ["Certificates", "Items", "Data"]:
            if isinstance(raw.get(k), list):
                return raw[k]
    return []


def parse_cert_row(r: dict[str, Any]):
    return {
        "cn": r.get("IssuedCN") or r.get("CommonName") or r.get("CN"),
        "not_after": r.get("NotAfter") or r.get("ExpirationDate"),
        "issuer": r.get("IssuerDN"),
        "template": r.get("TemplateName") or r.get("TemplateId"),
        "thumbprint": r.get("Thumbprint"),
        "owner": r.get("OwnerRoleName") or r.get("Owner"),
    }


def to_table(rows: list[dict[str, Any]], limit: int = 100):
    return [parse_cert_row(x) for x in rows[:limit]]


def group_count(rows: list[dict[str, Any]], key: str):
    c = Counter(str(parse_cert_row(r).get(key) or "Unknown") for r in rows)
    return [{"name": k, "count": v} for k, v in c.most_common()]
