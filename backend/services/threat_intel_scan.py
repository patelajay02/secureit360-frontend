import os
import json
import asyncio
import socket
import httpx
from datetime import datetime, timezone
from services.database import supabase_admin


def _sanitize(obj: dict) -> dict:
    return json.loads(json.dumps(obj, default=str))


def _get_frameworks(country: str, extra: list) -> list:
    c = (country or "NZ").upper()
    if c in ("UAE", "AE"):
        base = ["UAE PDPL 2021", "DIFC Data Protection Law", "ADGM", "ISO 27001"]
    elif c == "AU":
        base = ["Australian Privacy Act 1988", "ISO 27001", "ASD Essential Eight"]
    elif c == "IN":
        base = ["DPDP Act 2023", "RBI Guidelines", "CERT-In", "ISO 27001"]
    else:
        base = ["NZ Privacy Act 2020", "ISO 27001", "ASD Essential Eight"]
    return list(dict.fromkeys(base + (extra or [])))


async def _resolve_ips(domain: str) -> list[str]:
    loop = asyncio.get_event_loop()
    try:
        infos = await asyncio.wait_for(
            loop.run_in_executor(None, socket.getaddrinfo, domain, 80),
            timeout=5.0,
        )
        return list({i[4][0] for i in infos if i[0] == socket.AF_INET})
    except Exception:
        return []


async def _domain_resolves(domain: str) -> bool:
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, socket.getaddrinfo, domain, 80),
            timeout=3.0,
        )
        return bool(result)
    except Exception:
        return False


def _generate_typos(domain: str) -> list[str]:
    parts = domain.lower().split(".")
    if len(parts) < 2:
        return []
    name = parts[0]
    base_tld = ".".join(parts[1:])

    typos: set[str] = set()

    # Alternative TLDs
    for tld in ["com", "net", "org", "co", "nz", "com.au", "biz", "info", "online"]:
        c = f"{name}.{tld}"
        if c != domain:
            typos.add(c)

    # Missing one character
    for i in range(len(name)):
        t = name[:i] + name[i + 1:]
        if len(t) >= 3:
            typos.add(f"{t}.{base_tld}")

    # Adjacent transposition
    for i in range(len(name) - 1):
        chars = list(name)
        chars[i], chars[i + 1] = chars[i + 1], chars[i]
        t = "".join(chars)
        if t != name:
            typos.add(f"{t}.{base_tld}")

    # Character substitutions
    for old, new in [("o", "0"), ("l", "1"), ("i", "l"), ("e", "3"), ("s", "5"), ("a", "4")]:
        if old in name:
            typos.add(f"{name.replace(old, new, 1)}.{base_tld}")

    # Prepended words
    for prefix in ["my", "login", "portal", "app", "secure", "www"]:
        typos.add(f"{prefix}{name}.{base_tld}")

    typos.discard(domain)
    typos = {t for t in typos if "." in t and len(t) > 4}
    return list(typos)[:25]


# ── AbuseIPDB ───────────────────────────────────────────────────────────────

async def _check_abuseipdb(domain: str, ips: list, tenant_id: str, scan_id: str, frameworks: list) -> dict | None:
    api_key = os.getenv("ABUSEIPDB_API_KEY")
    if not api_key or not ips:
        return None
    flagged = []
    async with httpx.AsyncClient() as client:
        for ip in ips[:5]:
            try:
                resp = await client.get(
                    "https://api.abuseipdb.com/api/v2/check",
                    params={"ipAddress": ip, "maxAgeInDays": "90"},
                    headers={"Key": api_key, "Accept": "application/json"},
                    timeout=10,
                )
                if resp.is_success:
                    data = resp.json().get("data", {})
                    score = data.get("abuseConfidenceScore", 0)
                    if score > 20:
                        flagged.append({
                            "ip": ip,
                            "abuse_score": score,
                            "country": data.get("countryCode", "Unknown"),
                            "usage_type": data.get("usageType", "Unknown"),
                        })
            except Exception:
                pass

    if not flagged:
        return None

    n = len(flagged)
    return {
        "tenant_id": tenant_id, "scan_id": scan_id, "engine": "threat_intel",
        "severity": "critical" if any(f["abuse_score"] > 75 for f in flagged) else "moderate",
        "title": f"{n} IP address{'es' if n > 1 else ''} flagged on AbuseIPDB blacklists for {domain}",
        "description": (
            f"{n} IP address{'es' if n > 1 else ''} associated with {domain} appear on AbuseIPDB abuse blacklists. "
            "Blacklisted IPs indicate your network may be compromised, used for spam, or associated with malicious activity."
        ),
        "governance_gap": "No formal process exists to monitor IP reputation or blocklist status.",
        "regulations": frameworks,
        "fix_type": "specialist", "score_impact": min(15, n * 5),
        "status": "open",
        "metadata": _sanitize({"flagged_ips": flagged}),
    }


# ── VirusTotal ──────────────────────────────────────────────────────────────

async def _check_virustotal(domain: str, tenant_id: str, scan_id: str, frameworks: list) -> dict | None:
    api_key = os.getenv("VIRUSTOTAL_API_KEY")
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://www.virustotal.com/api/v3/domains/{domain}",
                headers={"x-apikey": api_key},
                timeout=15,
            )
        if not resp.is_success:
            return None
        stats = resp.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        if malicious == 0 and suspicious == 0:
            return None
        total_bad = malicious + suspicious
        return {
            "tenant_id": tenant_id, "scan_id": scan_id, "engine": "threat_intel",
            "severity": "critical" if malicious > 5 else "moderate",
            "title": f"{domain} detected as malicious by {total_bad} VirusTotal security vendor{'s' if total_bad > 1 else ''}",
            "description": (
                f"VirusTotal analysis flagged {domain}: {malicious} vendor(s) classify it as malicious "
                f"and {suspicious} as suspicious. This indicates your domain may be associated with malware, "
                "phishing, or other malicious activity in industry threat databases."
            ),
            "governance_gap": "No formal process exists to monitor domain reputation across threat intelligence databases.",
            "regulations": frameworks,
            "fix_type": "specialist", "score_impact": min(20, total_bad * 2),
            "status": "open",
            "metadata": _sanitize({"malicious_vendors": malicious, "suspicious_vendors": suspicious, "total_flagged": total_bad}),
        }
    except Exception:
        return None


# ── URLScan.io ──────────────────────────────────────────────────────────────

async def _check_urlscan(domain: str, tenant_id: str, scan_id: str, frameworks: list) -> dict | None:
    api_key = os.getenv("URLSCAN_API_KEY")
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://urlscan.io/api/v1/search/",
                params={"q": f"domain:{domain} AND verdicts.malicious:true", "size": "10"},
                headers={"API-Key": api_key},
                timeout=15,
            )
        if not resp.is_success:
            return None
        results = resp.json().get("results", [])
        n = len(results)
        if n == 0:
            return None
        return {
            "tenant_id": tenant_id, "scan_id": scan_id, "engine": "threat_intel",
            "severity": "critical" if n > 3 else "moderate",
            "title": f"{domain} found in {n} malicious URLScan.io record{'s' if n > 1 else ''}",
            "description": (
                f"URLScan.io has recorded {n} malicious scan result{'s' if n > 1 else ''} involving {domain}. "
                "This suggests your domain has been observed in phishing pages, malware delivery, or other malicious scans."
            ),
            "governance_gap": "No formal process exists to monitor malicious URL activity associated with the domain.",
            "regulations": frameworks,
            "fix_type": "specialist", "score_impact": min(15, n * 3),
            "status": "open",
            "metadata": _sanitize({"malicious_scan_count": n}),
        }
    except Exception:
        return None


# ── AlienVault OTX ──────────────────────────────────────────────────────────

async def _check_otx(domain: str, ips: list, tenant_id: str, scan_id: str, frameworks: list) -> dict | None:
    api_key = os.getenv("OTX_API_KEY")
    if not api_key:
        return None
    try:
        pulse_count = 0
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://otx.alienvault.com/api/v1/indicators/domain/{domain}/general",
                headers={"X-OTX-API-KEY": api_key},
                timeout=15,
            )
            if resp.is_success:
                pulse_count += resp.json().get("pulse_info", {}).get("count", 0)

            for ip in ips[:3]:
                ip_resp = await client.get(
                    f"https://otx.alienvault.com/api/v1/indicators/IPv4/{ip}/general",
                    headers={"X-OTX-API-KEY": api_key},
                    timeout=10,
                )
                if ip_resp.is_success:
                    pulse_count += ip_resp.json().get("pulse_info", {}).get("count", 0)

        if pulse_count == 0:
            return None
        return {
            "tenant_id": tenant_id, "scan_id": scan_id, "engine": "threat_intel",
            "severity": "critical" if pulse_count > 5 else "moderate",
            "title": f"{domain} found in {pulse_count} AlienVault OTX threat intelligence feed{'s' if pulse_count > 1 else ''}",
            "description": (
                f"AlienVault OTX has {pulse_count} threat intelligence pulse{'s' if pulse_count > 1 else ''} referencing "
                f"{domain} or its IP addresses. OTX pulses indicate your domain or IPs have been observed in "
                "active threat campaigns reported by the global security community."
            ),
            "governance_gap": "No formal process exists to monitor threat intelligence feeds for domain or IP indicators of compromise.",
            "regulations": frameworks,
            "fix_type": "specialist", "score_impact": min(15, pulse_count * 2),
            "status": "open",
            "metadata": _sanitize({"pulse_count": pulse_count, "checked_ips": ips[:3]}),
        }
    except Exception:
        return None


# ── Typosquatting ───────────────────────────────────────────────────────────

async def _check_typosquatting(domain: str, tenant_id: str, scan_id: str, frameworks: list) -> dict | None:
    typos = _generate_typos(domain)
    if not typos:
        return None

    results = await asyncio.gather(*[_domain_resolves(t) for t in typos], return_exceptions=True)
    registered = [t for t, r in zip(typos, results) if r is True]

    if not registered:
        return None

    n = len(registered)
    return {
        "tenant_id": tenant_id, "scan_id": scan_id, "engine": "threat_intel",
        "severity": "critical" if n > 3 else "moderate",
        "title": f"{n} typosquatting domain{'s' if n > 1 else ''} registered that impersonate {domain}",
        "description": (
            f"{n} registered domain{'s' if n > 1 else ''} closely resemble your domain {domain}. "
            "Typosquatting domains are commonly used to deceive customers, intercept emails, or conduct "
            "phishing attacks that impersonate your business."
        ),
        "governance_gap": "No formal process exists to monitor domain impersonation attempts.",
        "regulations": frameworks,
        "fix_type": "specialist", "score_impact": min(25, n * 5),
        "status": "open",
        "metadata": _sanitize({"registered_typos": registered, "total_checked": len(typos)}),
    }


# ── Have I Been Pwned ───────────────────────────────────────────────────────

async def _check_hibp(domain: str, tenant_id: str, scan_id: str, frameworks: list) -> dict | None:
    api_key = os.getenv("HIBP_API_KEY")
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://haveibeenpwned.com/api/v3/breacheddomain/{domain}",
                headers={"hibp-api-key": api_key, "user-agent": "SecureIT360"},
                timeout=15,
            )
        if resp.status_code == 404:
            return None
        if not resp.is_success:
            return None

        data = resp.json()
        alias_count = len(data)
        if alias_count == 0:
            return None

        unique_breaches = list({b for breaches in data.values() for b in breaches})
        sample_emails = [f"{alias}@{domain}" for alias in list(data.keys())[:10]]

        return {
            "tenant_id": tenant_id, "scan_id": scan_id, "engine": "threat_intel",
            "severity": "critical",
            "title": f"Data breach detected — {alias_count} email account{'s' if alias_count > 1 else ''} from {domain} exposed",
            "description": (
                f"{alias_count} email address{'es' if alias_count > 1 else ''} from {domain} have appeared in known data breaches "
                f"according to Have I Been Pwned. Affected accounts were found in: {', '.join(unique_breaches[:5])}. "
                "Breached credentials are actively sold and used for account takeover attacks."
            ),
            "governance_gap": "No formal process exists to monitor employee credentials against breach databases.",
            "regulations": frameworks,
            "fix_type": "specialist", "score_impact": min(25, alias_count * 2),
            "status": "open",
            "metadata": _sanitize({
                "total_aliases_breached": alias_count,
                "breach_names": unique_breaches,
                "sample_affected_emails": sample_emails,
            }),
        }
    except Exception:
        return None


# ── Main entry point ────────────────────────────────────────────────────────

async def run_threat_intel_scan(tenant_id: str, scan_id: str) -> dict:
    domains_result = supabase_admin.table("domains")\
        .select("domain")\
        .eq("tenant_id", tenant_id)\
        .order("created_at")\
        .execute()

    if not domains_result.data:
        return {"findings_count": 0, "skipped": True, "reason": "No domains configured"}

    domain = domains_result.data[0]["domain"].lower().strip()

    tenant_r = supabase_admin.table("tenants")\
        .select("country, compliance_frameworks")\
        .eq("id", tenant_id)\
        .single()\
        .execute()

    country = "NZ"
    extra_frameworks: list = []
    if tenant_r.data:
        country = tenant_r.data.get("country") or "NZ"
        extra_frameworks = tenant_r.data.get("compliance_frameworks") or []

    frameworks = _get_frameworks(country, extra_frameworks)

    # Resolve domain IPs once — reused by AbuseIPDB and OTX
    ips = await _resolve_ips(domain)

    # Run all checks concurrently
    check_results = await asyncio.gather(
        _check_abuseipdb(domain, ips, tenant_id, scan_id, frameworks),
        _check_virustotal(domain, tenant_id, scan_id, frameworks),
        _check_urlscan(domain, tenant_id, scan_id, frameworks),
        _check_otx(domain, ips, tenant_id, scan_id, frameworks),
        _check_typosquatting(domain, tenant_id, scan_id, frameworks),
        _check_hibp(domain, tenant_id, scan_id, frameworks),
        return_exceptions=True,
    )

    findings = []
    for r in check_results:
        if isinstance(r, Exception):
            print(f"[ThreatIntel] Check error: {r}")
        elif r is not None:
            findings.append(r)

    inserted = 0
    for finding in findings:
        try:
            existing = supabase_admin.table("findings")\
                .select("id")\
                .eq("tenant_id", finding["tenant_id"])\
                .eq("title", finding["title"])\
                .limit(1)\
                .execute()

            if existing.data:
                existing_id = existing.data[0]["id"]
                update_payload = {k: v for k, v in finding.items() if k != "tenant_id"}
                supabase_admin.table("findings")\
                    .update(update_payload)\
                    .eq("id", existing_id)\
                    .execute()
            else:
                supabase_admin.table("findings").insert(finding).execute()
            inserted += 1
        except Exception as e:
            print(f"[ThreatIntel] Failed to upsert '{finding.get('title', '?')}': {e}")

    supabase_admin.table("integrations")\
        .update({"last_synced_at": datetime.now(timezone.utc).isoformat()})\
        .eq("tenant_id", tenant_id)\
        .eq("platform", "threat_intel")\
        .execute()

    return {"findings_count": inserted, "domain": domain}
