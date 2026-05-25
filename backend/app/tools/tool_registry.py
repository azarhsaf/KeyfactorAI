from datetime import datetime, timezone


def classify_prompt(prompt: str):
    p = prompt.lower()
    if "expire" in p and "next week" in p:
        return "count_expiring_certificates", {"days": 7}
    if "expire" in p and "30" in p:
        return "get_expiring_certificates", {"days": 30}
    if "expired" in p:
        return "get_expired_certificates", {}
    if "failed" in p and "job" in p:
        return "get_failed_orchestrator_jobs", {}
    if "inventory" in p or "summary" in p:
        return "get_certificate_inventory_summary", {}
    return "get_certificate_inventory_summary", {}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def format_expiring_rows(raw):
    rows = raw if isinstance(raw, list) else raw.get("Certificates", raw.get("Items", []))
    out = []
    for r in rows[:250]:
        out.append(
            {
                "id": r.get("Id") or r.get("CertificateId"),
                "cn": r.get("CommonName") or r.get("CN"),
                "expiry_date": r.get("NotAfter") or r.get("ExpirationDate"),
                "ca": r.get("IssuerDN") or r.get("CertificateAuthority"),
                "template": r.get("CertificateTemplate"),
                "owner": r.get("Owner"),
                "serial_number": r.get("SerialNumber"),
            }
        )
    return out
