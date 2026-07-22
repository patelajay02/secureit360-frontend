# SecureIT360 - Network Scan Engine
# Checks for dangerous open ports with specific regulation clause references

import os
import shodan
from services.database import supabase_admin
from services.target_guard import assert_scannable, TargetValidationError

SHODAN_API_KEY = os.getenv("SHODAN_API_KEY")

DANGEROUS_PORTS = {
    3389: {
        "title": "Windows remote access is open to the internet - the number one ransomware entry point",
        "description": "Your network has Windows Remote Desktop (RDP) accessible from the internet. This is the most common way ransomware gangs break into businesses. They scan the internet for exactly this and use automated tools to guess passwords. If they get in, they can lock every computer in your business within minutes.",
        "severity": "critical",
        "score_impact": 35,
        "governance_gap": "No network security policy or firewall management process exists. Nobody is responsible for monitoring open network access points.",
        "regulations": [
            "AU Essential Eight ML2 - Restrict administrative privileges (RDP must be restricted)",
            "AU Essential Eight ML1 - Patch operating systems (exposed RDP is unacceptable)",
            "AU Cyber Security Act 2024 - s30 (ransomware incident reporting obligations)",
            "NZ NCSC Guidelines - Network security baseline (close unnecessary remote access)",
            "NZ Privacy Act 2020 - IPP 5 (security safeguards for personal information)",
            "AU Privacy Act 1988 - APP 11.1 (reasonable steps to protect personal information)"
        ]
    },
    22: {
        "title": "Remote server access is open to the internet",
        "description": "Your network has SSH (remote server access) accessible from the internet. While sometimes necessary, this is a common target for automated hacking attempts. Attackers run thousands of password guesses per minute against open SSH ports.",
        "severity": "moderate",
        "score_impact": 15,
        "governance_gap": "No network security policy exists. There is no process for reviewing and closing unnecessary network access.",
        "regulations": [
            "AU Essential Eight ML1 - Restrict administrative privileges",
            "NZ NCSC Guidelines - Network security baseline",
            "AU Privacy Act 1988 - APP 11.1 (reasonable steps to protect personal information)",
            "NZ Privacy Act 2020 - IPP 5 (security safeguards)"
        ]
    },
    21: {
        "title": "Old file transfer service is open to the internet",
        "description": "Your network has FTP (an old file transfer service) accessible from the internet. FTP sends data without encryption, meaning anyone watching your network can see the files being transferred. This service should be replaced with a secure alternative.",
        "severity": "moderate",
        "score_impact": 10,
        "governance_gap": "No network security policy exists. Outdated and insecure services are not being identified or removed.",
        "regulations": [
            "AU Essential Eight ML1 - Patch applications (insecure protocols must be removed)",
            "NZ NCSC Guidelines - Network security baseline",
            "AU Privacy Act 1988 - APP 11.1 (reasonable steps to protect personal information)",
            "NZ Privacy Act 2020 - IPP 5 (security safeguards)"
        ]
    },
    23: {
        "title": "Unsecured remote access is open to the internet",
        "description": "Your network has Telnet accessible from the internet. Telnet is an old and completely unsecured remote access tool that sends everything including passwords in plain text. This should be disabled immediately.",
        "severity": "critical",
        "score_impact": 20,
        "governance_gap": "No network security policy exists. Outdated and insecure services are not being removed from the network.",
        "regulations": [
            "AU Essential Eight ML1 - Patch applications (insecure protocols must be disabled)",
            "AU Essential Eight ML1 - Restrict administrative privileges",
            "NZ NCSC Guidelines - Network security baseline",
            "AU Privacy Act 1988 - APP 11.1 (reasonable steps to protect personal information)",
            "NZ Privacy Act 2020 - IPP 5 (security safeguards)"
        ]
    },
    445: {
        "title": "Windows file sharing is exposed to the internet",
        "description": "Your network has Windows file sharing (SMB) accessible from the internet. This is the vulnerability that allowed the WannaCry ransomware to spread across the world in 2017. Having this open is extremely dangerous and puts your entire business at risk.",
        "severity": "critical",
        "score_impact": 30,
        "governance_gap": "No network security policy or firewall management process exists. Critical network services are not being protected from external access.",
        "regulations": [
            "AU Essential Eight ML1 - Patch operating systems (SMB must be blocked externally)",
            "AU Essential Eight ML2 - Restrict administrative privileges",
            "AU Cyber Security Act 2024 - s30 (ransomware incident reporting obligations)",
            "NZ NCSC Guidelines - Network security baseline",
            "AU Privacy Act 1988 - APP 11.1 (reasonable steps to protect personal information)",
            "NZ Privacy Act 2020 - IPP 5 (security safeguards)"
        ]
    }
}


def upsert_finding(tenant_id, scan_id, engine, severity, title, description, governance_gap, regulations, fix_type, score_impact):
    existing = supabase_admin.table("findings")\
        .select("id")\
        .eq("tenant_id", tenant_id)\
        .eq("engine", engine)\
        .eq("title", title)\
        .execute()

    if existing.data:
        supabase_admin.table("findings")\
            .update({
                "scan_id": scan_id,
                "severity": severity,
                "description": description,
                "governance_gap": governance_gap,
                "regulations": regulations,
                "fix_type": fix_type,
                "score_impact": score_impact,
                "status": "open"
            })\
            .eq("id", existing.data[0]["id"])\
            .execute()
        return False
    else:
        supabase_admin.table("findings").insert({
            "tenant_id": tenant_id,
            "scan_id": scan_id,
            "engine": engine,
            "severity": severity,
            "title": title,
            "description": description,
            "governance_gap": governance_gap,
            "regulations": regulations,
            "fix_type": fix_type,
            "score_impact": score_impact,
            "status": "open"
        }).execute()
        return True


async def run_network_scan(tenant_id: str, scan_id: str, domain: str):
    try:
        findings_count = 0
        api = shodan.Shodan(SHODAN_API_KEY)

        # Validate the target and resolve it to a permitted PUBLIC IP only.
        # Rejects localhost/private/link-local/metadata targets (SSRF guard).
        try:
            _normalized, validated_ips = assert_scannable(domain)
            ip_address = validated_ips[0]
        except TargetValidationError:
            supabase_admin.table("scan_engine_results").upsert({
                "tenant_id": tenant_id,
                "scan_id": scan_id,
                "engine": "network",
                "status": "skipped",
                "findings_count": 0
            }).execute()
            return {"status": "skipped", "message": "Target is not a permitted public host"}

        try:
            host = api.host(ip_address)
            open_ports = host.get("ports", [])

            for port in open_ports:
                if port in DANGEROUS_PORTS:
                    port_info = DANGEROUS_PORTS[port]
                    upsert_finding(
                        tenant_id, scan_id, "network",
                        port_info["severity"],
                        port_info["title"],
                        port_info["description"],
                        port_info["governance_gap"],
                        port_info["regulations"],
                        "specialist" if port_info["severity"] == "critical" else "voice",
                        port_info["score_impact"]
                    )
                    findings_count += 1

        except shodan.APIError:
            findings_count = 0

        supabase_admin.table("scan_engine_results").upsert({
            "tenant_id": tenant_id,
            "scan_id": scan_id,
            "engine": "network",
            "status": "complete",
            "findings_count": findings_count
        }).execute()

        return {"status": "complete", "findings_count": findings_count}

    except Exception as e:
        supabase_admin.table("scan_engine_results").upsert({
            "tenant_id": tenant_id,
            "scan_id": scan_id,
            "engine": "network",
            "status": "error",
            "findings_count": 0
        }).execute()
        return {"status": "error", "message": str(e)}
