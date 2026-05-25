from collections import Counter
from datetime import datetime, timezone
from difflib import get_close_matches
from typing import Any

QUESTION_LIBRARY = {
    "Inventory": [
        ("how many certificates do we have", "count_certificates", {}),
        ("show certificate inventory summary", "inventory_summary", {}),
        ("total certificates", "count_certificates", {}),
        ("certificates by issuer", "group_by_issuer", {}),
        ("certificates by template", "group_by_template", {}),
        ("certificates by expiry year", "group_by_expiry_year", {}),
        ("certificates by owner", "group_by_owner", {}),
        ("certificates by ca", "group_by_issuer", {}),
        ("certificates imported this month", "issued_this_month", {}),
        ("certificates issued this month", "issued_this_month", {}),
    ],
    "Expiry": [
        ("how many certificates are expired", "count_expired_certificates", {}),
        ("show expired certificates", "expired_certificates", {}),
        ("certificates expiring today", "expiring_certificates", {"days": 0}),
        ("certificates expiring tomorrow", "expiring_certificates", {"days": 1}),
        ("certificates expiring this week", "expiring_certificates", {"days": 7}),
        ("certificates expiring next 7 days", "expiring_certificates", {"days": 7}),
        ("certificates expiring next 30 days", "expiring_certificates", {"days": 30}),
        ("certificates expiring next 60 days", "expiring_certificates", {"days": 60}),
        ("certificates expiring next 90 days", "expiring_certificates", {"days": 90}),
        ("top 10 certificates expiring soon", "top_expiring_certificates", {"limit": 10}),
    ],
    "Weak Crypto": [
        ("show sha1 certificates", "sha1_certificates", {}),
        ("show weak hash certificates", "weak_crypto_summary", {}),
        ("show rsa certificates less than 2048", "rsa_less_than_2048", {}),
        ("show certificates using md5", "md5_certificates", {}),
        ("show weak algorithm certificates", "weak_crypto_summary", {}),
        ("show certificates not using sha256 or better", "weak_crypto_summary", {}),
    ],
    "Ownership / Governance": [
        ("certificates without owner", "owner_missing", {}),
        ("orphaned certificates", "owner_missing", {}),
        ("certificates without template", "template_missing", {}),
        ("certificates without owner role", "owner_missing", {}),
        ("certificates missing metadata", "metadata_missing", {}),
        ("certificates with unknown issuer", "unknown_issuer", {}),
        ("certificates without cn", "cn_missing", {}),
    ],
    "Risk": [
        ("high risk certificates", "high_risk_certificates", {}),
        ("internet facing certificates", "unsupported", {}),
        ("expired production certificates", "unsupported", {}),
        ("weak certificates expiring soon", "weak_expiring_soon", {}),
        ("certificates with long validity", "long_validity", {"days": 398}),
        ("certificates valid more than 398 days", "long_validity", {"days": 398}),
        ("certificates valid more than 825 days", "long_validity", {"days": 825}),
    ],
}

GENERAL_PKI = {
    "what is pki": "PKI means Public Key Infrastructure. It is the system used to issue, manage, validate, and revoke digital certificates.",
    "what is ca": "A CA is a Certificate Authority that issues and signs digital certificates.",
    "what is root ca": "A Root CA is the top-level trusted certificate authority that signs subordinate CA certificates.",
    "what is issuing ca": "An Issuing CA is a subordinate certificate authority that issues end-entity certificates.",
    "what is crl": "A CRL is a Certificate Revocation List used to publish revoked certificates.",
    "what is ocsp": "OCSP is the Online Certificate Status Protocol used to check certificate revocation status in real time.",
    "what is certificate revocation": "Certificate revocation is the process of invalidating a certificate before its expiration date.",
    "what is certificate lifecycle management": "Certificate lifecycle management is the process to discover, issue, renew, deploy, monitor, and revoke certificates.",
    "what is sha1 risk": "SHA1 risk is that SHA1 is cryptographically weak and collision-prone, so certificates using SHA1 should be replaced.",
    "what is rsa key size": "RSA key size is the modulus length in bits; modern policy commonly requires at least 2048 bits.",
}


def classify_prompt(prompt: str):
    p = " ".join(prompt.lower().strip().split())
    if "sha128" in p:
        return "invalid_sha128", {}, []
    if p in GENERAL_PKI:
        return "general_pki_answer", {"topic": p}, []

    all_q = []
    for _, items in QUESTION_LIBRARY.items():
        for q, tool, params in items:
            all_q.append((q, tool, params))
            if q in p or p in q:
                return tool, params, []

    candidate_texts = [q for q, _, _ in all_q]
    close = get_close_matches(p, candidate_texts, n=5, cutoff=0.45)
    return "unsupported", {}, close


def supported_questions_grouped():
    return QUESTION_LIBRARY


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def normalize_rows(raw: Any):
    if isinstance(raw, list): return raw
    if isinstance(raw, dict):
        for k in ["Certificates", "Items", "Data"]:
            if isinstance(raw.get(k), list): return raw[k]
    return []


def parse_cert_row(r: dict[str, Any]):
    return {"cn": r.get("IssuedCN") or r.get("CommonName") or r.get("CN"), "not_after": r.get("NotAfter") or r.get("ExpirationDate"), "issuer": r.get("IssuerDN"), "template": r.get("TemplateName") or r.get("TemplateId"), "thumbprint": r.get("Thumbprint"), "owner": r.get("OwnerRoleName") or r.get("Owner")}


def to_table(rows: list[dict[str, Any]], limit: int = 100):
    return [parse_cert_row(x) for x in rows[:limit]]


def group_count(rows: list[dict[str, Any]], key: str):
    c = Counter(str(parse_cert_row(r).get(key) or "Unknown") for r in rows)
    return [{"name": k, "count": v} for k, v in c.most_common()]
