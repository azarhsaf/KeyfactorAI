from collections import Counter
from datetime import datetime, timezone
from typing import Any


def classify_prompt(prompt: str):
    p = prompt.lower()
    if "top" in p and "expiring" in p:
        return "top_expiring_certificates", {"limit": 10}
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
    if "inventory" in p:
        return "inventory_summary", {}
    return "inventory_summary", {}


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
        "key_algorithm": str(r.get("KeyAlgorithm") or ""),
        "key_size": r.get("KeySize"),
        "signature_algorithm": str(r.get("SignatureAlgorithm") or ""),
    }


def to_table(rows: list[dict[str, Any]], limit: int = 100):
    return [parse_cert_row(x) for x in rows[:limit]]


def group_count(rows: list[dict[str, Any]], key: str):
    c = Counter(str(parse_cert_row(r).get(key) or "Unknown") for r in rows)
    return [{"name": k, "count": v} for k, v in c.most_common()]
