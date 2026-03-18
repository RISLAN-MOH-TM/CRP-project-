#!/usr/bin/env python3
"""
AI Analysis Layer — context window management + structured output schema.

Wired to PROMPT.txt (14-section report template).

Public API used by mcp_server.py:
  prepare_scan_context(raw_results, cve_context)  → condensed string ≤80k tokens
  build_report_prompt(scan_context, meta)          → full prompt → Claude emits JSON
  estimate_tokens(text)                            → int
  chunk_for_summarisation(text, chunk_chars)       → List[str]
"""

import json
import re
from datetime import date as _date
from typing import Any, Dict, List, Optional

# ── Token budget ──────────────────────────────────────────────────────────────
# Claude context ~200k tokens. Reserve:
#   20k  system prompt + schema
#   10k  CVE RAG context
#   10k  Claude JSON output
#   →  80k target for scan data (safe margin)
CHAR_PER_TOKEN = 4
TARGET_TOKENS  = 80_000
TARGET_CHARS   = TARGET_TOKENS * CHAR_PER_TOKEN   # 320_000 chars

# Per-tool hard caps (chars) — one noisy tool can't eat the whole budget
TOOL_CAPS: Dict[str, int] = {
    "nmap":        40_000,
    "nuclei":      30_000,
    "gobuster":    20_000,
    "feroxbuster": 20_000,
    "ffuf":        20_000,
    "nikto":       20_000,
    "sqlmap":      30_000,
    "hydra":       15_000,
    "metasploit":  30_000,
    "whatweb":     10_000,
    "subfinder":   10_000,
    "amass":       10_000,
    "masscan":     15_000,
    "default":     15_000,
}

# Tool priority — most signal-rich first
_PRIORITY = [
    "nmap", "nuclei", "sqlmap", "nikto", "metasploit",
    "whatweb", "gobuster", "ffuf", "feroxbuster",
    "hydra", "masscan", "subfinder", "amass", "wpscan",
    "searchsploit", "enum4linux-ng", "john", "hashcat",
]


# ══════════════════════════════════════════════════════════════════════════════
# Context window management
# ══════════════════════════════════════════════════════════════════════════════

# High-signal line patterns — keep these when truncating large outputs
_SIGNAL_RE = re.compile(
    r"\d+/tcp\s+open"               # nmap open ports
    r"|CVE-\d{4}-\d+"               # CVE IDs anywhere
    r"|\[critical\]|\[high\]|\[medium\]|\[low\]"  # nuclei severity tags
    r"|VULNERABLE|vulnerable|FOUND|found|CONFIRMED"
    r"|^\+\s"                        # nikto findings
    r"|https?://\S+"                 # URLs
    r"|\b(200|301|302|403|500)\b"   # HTTP status codes
    r"|error|Error|ERROR"
    r"|password|credential|admin|root|shell|inject|bypass",
    re.IGNORECASE | re.MULTILINE,
)


def _cap(tool: str, output: str) -> str:
    cap = TOOL_CAPS.get(tool, TOOL_CAPS["default"])
    if len(output) <= cap:
        return output
    return output[:cap] + f"\n... [{len(output)-cap:,} chars truncated — per-tool cap]"


def _extract_signal(output: str) -> str:
    """Keep high-signal lines + first 20 + last 10 lines. Deduplicates."""
    lines = output.splitlines()
    signal = [ln for ln in lines if _SIGNAL_RE.search(ln)]
    combined = lines[:20] + signal + lines[-10:]
    seen, result = set(), []
    for ln in combined:
        if ln not in seen:
            seen.add(ln)
            result.append(ln)
    return "\n".join(result)


def prepare_scan_context(
    raw_results: List[Dict[str, Any]],
    cve_context: str = "",
) -> str:
    """
    Condense raw scan results into a Claude-safe context block.

    Steps:
      1. Sort by tool priority (nmap first, hashcat last)
      2. Per-tool output cap
      3. Signal-line extraction for outputs >8k chars
      4. Global 320k char (80k token) budget enforcement
      5. CVE context appended last

    Args:
        raw_results: list of dicts — keys: tool, target, stdout, stderr, success
        cve_context: output of cve_build_report_context (already compact)

    Returns:
        Condensed string guaranteed under TARGET_CHARS
    """
    def _pri(r: dict) -> int:
        t = r.get("tool", "")
        return _PRIORITY.index(t) if t in _PRIORITY else 99

    sorted_results = sorted(raw_results, key=_pri)
    sections: List[str] = []
    total_chars = 0

    for r in sorted_results:
        tool    = r.get("tool", "unknown")
        target  = r.get("target", "")
        success = r.get("success", False)
        stdout  = r.get("stdout", "") or ""
        stderr  = r.get("stderr", "") or ""

        if not stdout and not stderr:
            continue

        stdout = _cap(tool, stdout)
        if len(stdout) > 8_000:
            stdout = _extract_signal(stdout)

        section = (
            f"=== {tool.upper()} | target={target} | success={success} ===\n"
            f"{stdout}\n"
        )
        if stderr.strip():
            section += f"[stderr]: {stderr[:500]}\n"

        remaining = TARGET_CHARS - total_chars
        if remaining < 200:
            omitted = len(sorted_results) - sorted_results.index(r)
            sections.append(f"\n[BUDGET EXHAUSTED — {omitted} tool(s) omitted]")
            break
        if len(section) > remaining:
            section = section[:remaining] + "\n[truncated — global budget limit]"
            sections.append(section)
            break

        sections.append(section)
        total_chars += len(section)

    if cve_context:
        sections.append("\n" + cve_context)

    summary = (
        f"[SCAN CONTEXT SUMMARY]\n"
        f"Tools: {len(raw_results)} | Included: {len(sections)} sections | "
        f"Chars: {total_chars:,} / {TARGET_CHARS:,}\n\n"
    )
    return summary + "\n".join(sections)


def estimate_tokens(text: str) -> int:
    return len(text) // CHAR_PER_TOKEN


def chunk_for_summarisation(text: str, chunk_chars: int = 40_000) -> List[str]:
    """
    Split a large single-tool output into overlapping chunks for
    multi-step summarisation when even signal extraction isn't enough.
    """
    chunks, start, overlap = [], 0, 500
    while start < len(text):
        chunks.append(text[start:start + chunk_chars])
        start += chunk_chars - overlap
    return chunks


# ══════════════════════════════════════════════════════════════════════════════
# JSON output schema — matches PROMPT.txt 14-section structure exactly
# ══════════════════════════════════════════════════════════════════════════════

REPORT_SCHEMA = {
    "type": "object",
    "required": [
        "metadata", "executive_summary", "target_information",
        "tools_and_methodology", "findings", "risk_assessment",
        "incident_response", "mitigations", "cve_intelligence_analysis",
        "conclusion", "ethical_disclaimer", "glossary", "signoff"
    ],
    "properties": {

        # Section 1 + 2 metadata (cover page + TOC data)
        "metadata": {
            "type": "object",
            "required": ["target", "tester", "date", "report_ref", "scope",
                         "overall_risk", "cve_db_count"],
            "properties": {
                "target":       {"type": "string"},
                "tester":       {"type": "string"},
                "date":         {"type": "string"},
                "report_ref":   {"type": "string"},
                "scope":        {"type": "string"},
                "overall_risk": {"type": "string", "enum": ["CRITICAL","HIGH","MEDIUM","LOW"]},
                "cve_db_count": {"type": "integer",
                                 "description": "Total CVEs in local RAG database"},
            }
        },

        # Section 3 — Executive Summary
        "executive_summary": {
            "type": "object",
            "required": ["scorecard", "narrative", "cve_intelligence_summary"],
            "properties": {
                "scorecard": {
                    "type": "object",
                    "properties": {
                        "critical": {"type": "integer"},
                        "high":     {"type": "integer"},
                        "medium":   {"type": "integer"},
                        "low":      {"type": "integer"},
                        "info":     {"type": "integer"},
                    }
                },
                "narrative":   {"type": "string",
                                "description": "3-4 paragraph non-technical summary"},
                "cve_intelligence_summary": {
                    "type": "object",
                    "properties": {
                        "total_cves_matched": {"type": "integer"},
                        "most_critical_cve":  {"type": "string"},
                        "most_critical_cvss": {"type": "number"},
                        "summary_text":       {"type": "string"},
                    }
                }
            }
        },

        # Section 4 — Target Information
        "target_information": {
            "type": "object",
            "properties": {
                "url_or_ip":      {"type": "string"},
                "technology_stack": {"type": "array", "items": {"type": "string"}},
                "open_ports":     {"type": "array", "items": {"type": "string"}},
                "os_detected":    {"type": "string"},
                "scope":          {"type": "string"},
                "objectives":     {"type": "string"},
                "limitations":    {"type": "string"},
                "testing_window": {"type": "string"},
            }
        },

        # Section 5 — Tools & Methodology
        "tools_and_methodology": {
            "type": "object",
            "properties": {
                "tools_used": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name":    {"type": "string"},
                            "version": {"type": "string"},
                            "purpose": {"type": "string"},
                            "result_summary": {"type": "string"},
                        }
                    }
                },
                "methodology_phases": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "5 phases: Recon, Scan, Exploit, CVE Enrich, Report"
                },
                "cve_rag_note": {"type": "string"},
            }
        },

        # Section 6 — Findings (one object per confirmed vulnerability)
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "id", "title", "severity", "cvss_score", "cvss_vector",
                    "cwe", "cve_reference", "component", "tool_found_by",
                    "description", "technical_detail",
                    "http_request", "http_response",
                    "cve_intelligence", "risk_story",
                    "exploitation_likelihood", "cve_references"
                ],
                "properties": {
                    "id":               {"type": "string", "description": "e.g. VULN-01"},
                    "title":            {"type": "string"},
                    "severity":         {"type": "string",
                                         "enum": ["CRITICAL","HIGH","MEDIUM","LOW","INFO"]},
                    "cvss_score":       {"type": "number",
                                         "description": "CVSS v3.1 base score 0.0-10.0"},
                    "cvss_vector":      {"type": "string",
                                         "description": "e.g. CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
                    "cwe":              {"type": "string",
                                         "description": "e.g. CWE-89: SQL Injection"},
                    "cve_reference":    {"type": "string",
                                         "description": "e.g. CVE-2021-44228 or N/A"},
                    "component":        {"type": "string",
                                         "description": "Affected component + version"},
                    "tool_found_by":    {"type": "string"},
                    "description":      {"type": "string",
                                         "description": "What the vulnerability is"},
                    "technical_detail": {"type": "string",
                                         "description": "How it was found, exact params tested"},
                    "http_request":     {"type": "string",
                                         "description": "Exact HTTP request sent (or N/A)"},
                    "http_response":    {"type": "string",
                                         "description": "Exact HTTP response / tool output (or N/A)"},
                    "cve_intelligence": {
                        "type": "object",
                        "required": ["related_cves","historical_context",
                                     "known_exploits","affected_versions","patches"],
                        "properties": {
                            "related_cves": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "cve_id":   {"type": "string"},
                                        "cvss":     {"type": "number"},
                                        "severity": {"type": "string"},
                                        "summary":  {"type": "string"},
                                    }
                                }
                            },
                            "historical_context": {"type": "string"},
                            "known_exploits":     {"type": "string"},
                            "affected_versions":  {"type": "string"},
                            "patches":            {"type": "string"},
                        }
                    },
                    "risk_story":              {"type": "string",
                                                "description": "Real-world impact: 'An attacker could...'"},
                    "exploitation_likelihood": {"type": "string",
                                                "description": "e.g. '95% — public exploit, no auth required'"},
                    "cve_references":          {"type": "array", "items": {"type": "string"},
                                                "description": "NVD + MITRE URLs"},
                }
            }
        },

        # Section 7 — Risk Assessment
        "risk_assessment": {
            "type": "object",
            "properties": {
                "business_impact_table": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "finding_id":       {"type": "string"},
                            "confidentiality":  {"type": "string"},
                            "integrity":        {"type": "string"},
                            "availability":     {"type": "string"},
                            "business_impact":  {"type": "string"},
                        }
                    }
                },
                "attack_chain_ascii": {"type": "string",
                                       "description": "ASCII diagram of attack path"},
                "cve_risk_scoring":   {"type": "string",
                                       "description": "Comparison vs historical CVE severity trends"},
            }
        },

        # Section 8 — Incident Response
        "incident_response": {
            "type": "object",
            "properties": {
                "ir_protocol": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "6 steps: Identify, Contain, Eradicate, Recover, Review, Report"
                },
                "per_vuln_response": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "finding_id":     {"type": "string"},
                            "response_steps": {"type": "string"},
                        }
                    }
                }
            }
        },

        # Section 9 — Mitigations
        "mitigations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["finding_id","immediate","short_term","long_term"],
                "properties": {
                    "finding_id":  {"type": "string"},
                    "immediate":   {"type": "string",
                                    "description": "Fix within 24 hours"},
                    "short_term":  {"type": "string",
                                    "description": "Fix within 1 week"},
                    "long_term":   {"type": "string",
                                    "description": "Fix within 1 month"},
                    "cve_patches": {"type": "string",
                                    "description": "Vendor advisories from RAG database"},
                }
            }
        },

        # Section 10 — CVE Intelligence Analysis
        "cve_intelligence_analysis": {
            "type": "object",
            "properties": {
                "total_searches":       {"type": "integer"},
                "matches_by_severity": {
                    "type": "object",
                    "properties": {
                        "critical": {"type": "integer"},
                        "high":     {"type": "integer"},
                        "medium":   {"type": "integer"},
                        "low":      {"type": "integer"},
                    }
                },
                "top_5_critical_cves": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "cve_id":  {"type": "string"},
                            "cvss":    {"type": "number"},
                            "summary": {"type": "string"},
                        }
                    }
                },
                "trending_vulns_in_stack": {"type": "string"},
                "historical_patterns":     {"type": "string",
                                            "description": "Patterns 1999-2026 for affected products"},
                "vendor_stats":            {"type": "string"},
            }
        },

        # Section 11 — Conclusion
        "conclusion": {
            "type": "object",
            "required": ["positives","concerns","cve_key_insight","security_posture"],
            "properties": {
                "positives":        {"type": "string"},
                "concerns":         {"type": "string"},
                "cve_key_insight":  {"type": "string",
                                     "description": "Most significant historical pattern found"},
                "security_posture": {"type": "string",
                                     "enum": ["CRITICAL","HIGH","MEDIUM","LOW"]},
            }
        },

        # Section 12 — Ethical Disclaimer
        "ethical_disclaimer": {
            "type": "object",
            "properties": {
                "authorisation_statement": {"type": "string"},
                "legal_notice":            {"type": "string"},
                "scope_limitation":        {"type": "string"},
                "responsible_disclosure":  {"type": "string"},
            }
        },

        # Section 13 — Glossary (25+ terms)
        "glossary": {
            "type": "array",
            "minItems": 25,
            "items": {
                "type": "object",
                "properties": {
                    "term":       {"type": "string"},
                    "definition": {"type": "string"},
                }
            }
        },

        # Section 14 — Sign-off
        "signoff": {
            "type": "object",
            "properties": {
                "tester":       {"type": "string"},
                "reviewer":     {"type": "string"},
                "system_owner": {"type": "string"},
                "dpo":          {"type": "string"},
                "version":      {"type": "string"},
                "classification": {"type": "string"},
                "distribution":   {"type": "array", "items": {"type": "string"}},
            }
        },
    }
}


# ══════════════════════════════════════════════════════════════════════════════
# Prompt builder — wired to PROMPT.txt template
# ══════════════════════════════════════════════════════════════════════════════

# Inline system prompt from PROMPT.txt (agent behaviour instructions)
_SYSTEM_PROMPT = """\
You are an expert penetration tester and security report writer.
Your job is to analyse the scan results and CVE intelligence provided,
then produce a professional penetration testing report.

CRITICAL EVIDENCE RULES — STRICTLY ENFORCED:
  ✓ ONLY report vulnerabilities with DIRECT EVIDENCE in the scan output
  ✓ If a port is not explicitly shown as "open" in nmap output, DO NOT report it as open
  ✓ If a tool shows "connection refused", "filtered", or "failed", DO NOT report findings for that service
  ✓ If no SQLmap/FFUF output exists, DO NOT report POST endpoint vulnerabilities
  ✓ If no header analysis exists, DO NOT report missing headers as a vulnerability
  ✓ Every finding MUST quote the exact tool output that proves it exists
  ✓ Every finding needs: CVSS v3.1 score + vector, CWE ID, CVE ID (or N/A if not applicable)
  ✓ Every finding needs: exact HTTP request + response in http_request/http_response fields
  ✓ Every finding needs: cve_intelligence section populated from the CVE context
  ✓ Every finding needs: exploitation_likelihood with percentage and reason
  ✓ risk_story must be a real-world narrative: "An attacker could..."
  ✗ NEVER fabricate findings based on assumptions
  ✗ NEVER report theoretical vulnerabilities
  ✗ NEVER assume a service exists if the scan shows it's filtered/refused
  ✗ NEVER report "missing security headers" without actual header scan output

EVIDENCE VALIDATION CHECKLIST:
  Before adding ANY finding to the report, verify:
  1. Can I quote the exact line from tool output that proves this?
  2. Did the tool successfully connect and find this issue?
  3. Is this a confirmed vulnerability or just a failed scan?
  4. Do I have the actual HTTP request/response or tool output?

IF ALL SCANS FAILED:
  • Report ZERO findings in the findings[] array
  • In target_information.limitations, explain all scans were blocked
  • In conclusion.concerns, note the target appears heavily firewalled
  • Set overall_risk to "LOW" since no vulnerabilities were confirmed
  • In tools_and_methodology, document which tools failed and why

VISUAL DESIGN NOTES (for the renderer that will consume this JSON):
  • Severity colours: CRITICAL=red | HIGH=orange | MEDIUM=yellow | LOW=green
  • Dark navy (#1B2A4A) header bars on section titles
  • Dark monospace code blocks for http_request and http_response fields
  • Two-column info tables (navy label | white value)
  • Left-border callout boxes for risk_story and exploitation_likelihood
"""

_METHODOLOGY_PHASES = [
    "Phase 1 — Recon: Technology fingerprinting (whatweb, nmap OS detection)",
    "Phase 2 — Scan: Port scan, web scan, directory enum, fuzzing",
    "Phase 3 — Exploit: SQL injection, brute-force, CVE template scanning",
    "Phase 4 — CVE Enrich: Real-time RAG lookup after every finding",
    "Phase 5 — Report: Structured JSON report with full CVE intelligence",
]

_CVE_RAG_NOTE = (
    "CVE intelligence sourced from local RAG database: ~320,000 CVEs (NVD 1999–2026 + OSV.dev). "
    "Hybrid search: FTS5 keyword + all-MiniLM-L6-v2 vector embeddings + RRF merge. "
    "Query latency <10ms. Alias resolver handles product name variants."
)


def validate_scan_results(raw_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze scan results to detect if scans actually succeeded.
    Returns validation metadata to guide report generation.
    """
    validation = {
        "has_open_ports": False,
        "has_successful_web_scans": False,
        "has_sql_injection_tests": False,
        "has_header_analysis": False,
        "failed_tools": [],
        "successful_tools": [],
        "open_ports": [],
        "filtered_ports": [],
    }
    
    for result in raw_results:
        tool = result.get("tool", "")
        stdout = result.get("stdout", "") or ""
        stderr = result.get("stderr", "") or ""
        success = result.get("success", False)
        
        # Check for connection failures
        if any(phrase in stdout.lower() or phrase in stderr.lower() 
               for phrase in ["connection refused", "connection timed out", "failed to connect", 
                             "could not connect", "no route to host"]):
            validation["failed_tools"].append(tool)
            continue
            
        # Nmap port analysis
        if tool == "nmap":
            # Look for actual open ports
            open_port_matches = re.findall(r"(\d+)/tcp\s+open", stdout)
            filtered_port_matches = re.findall(r"(\d+)/tcp\s+filtered", stdout)
            
            if open_port_matches:
                validation["has_open_ports"] = True
                validation["open_ports"].extend(open_port_matches)
                validation["successful_tools"].append(tool)
            
            if filtered_port_matches:
                validation["filtered_ports"].extend(filtered_port_matches)
                
        # Web scanning tools
        elif tool in ["gobuster", "ffuf", "feroxbuster", "nikto"]:
            if success and stdout and len(stdout) > 100:
                # Check if it actually found something vs just errored
                if not any(err in stdout.lower() for err in ["error", "failed", "refused"]):
                    validation["has_successful_web_scans"] = True
                    validation["successful_tools"].append(tool)
                else:
                    validation["failed_tools"].append(tool)
            else:
                validation["failed_tools"].append(tool)
                
        # SQL injection testing
        elif tool == "sqlmap":
            if "parameter" in stdout.lower() and "vulnerable" in stdout.lower():
                validation["has_sql_injection_tests"] = True
                validation["successful_tools"].append(tool)
            elif stdout:
                validation["failed_tools"].append(tool)
                
        # Header analysis
        elif tool in ["nmap"] and "--script" in result.get("command", ""):
            if "http-headers" in stdout.lower() or "security-headers" in stdout.lower():
                validation["has_header_analysis"] = True
                
    return validation


def build_report_prompt(
    scan_context: str,
    target: str,
    tester: str = "MT. RISLAN MOHAMED — Security Analyst",
    date: str = "",
    scope: str = "",
    report_ref: str = "",
    extra_instructions: str = "",
    validation: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build the complete structured prompt Claude uses to generate the report.

    The prompt:
      1. Embeds the PROMPT.txt system instructions
      2. Fills {{TARGET_URL}}, {{SCOPE}}, {{DATE}}, {{REF}} template vars
      3. Injects the condensed scan context + CVE intelligence
      4. Enforces REPORT_SCHEMA — Claude must emit matching JSON
      5. Includes methodology phases and CVE RAG note for Section 5

    Args:
        scan_context:  output of prepare_scan_context()
        target:        target URL or IP
        tester:        tester name
        date:          ISO date string (auto-filled if empty)
        scope:         engagement scope
        report_ref:    report reference ID (auto-generated if empty)
        extra_instructions: any additional constraints to append

    Returns:
        Complete prompt string — pass directly to Claude
    """
    if not date:
        date = _date.today().isoformat()
    if not report_ref:
        safe = re.sub(r"[^A-Z0-9]", "", target.upper())[:8]
        report_ref = f"PENTEST-{_date.today().year}-{safe}"

    schema_str = json.dumps(REPORT_SCHEMA, indent=2)
    phases_str = "\n".join(f"  {p}" for p in _METHODOLOGY_PHASES)
    
    # Add validation context if provided
    validation_note = ""
    if validation:
        validation_note = f"""
═══════════════════════════════════════════════════════════════
  SCAN VALIDATION RESULTS — READ THIS FIRST
═══════════════════════════════════════════════════════════════

IMPORTANT: Review these validation results before generating findings:

Open Ports Found: {validation.get('open_ports', [])}
Filtered Ports: {validation.get('filtered_ports', [])}
Successful Tools: {validation.get('successful_tools', [])}
Failed Tools: {validation.get('failed_tools', [])}

Has Open Ports: {validation.get('has_open_ports', False)}
Has Successful Web Scans: {validation.get('has_successful_web_scans', False)}
Has SQL Injection Tests: {validation.get('has_sql_injection_tests', False)}
Has Header Analysis: {validation.get('has_header_analysis', False)}

CRITICAL INSTRUCTIONS BASED ON VALIDATION:
- If has_open_ports is False, DO NOT report any open port vulnerabilities
- If has_successful_web_scans is False, DO NOT report web vulnerabilities
- If has_sql_injection_tests is False, DO NOT report SQL injection findings
- If has_header_analysis is False, DO NOT report missing header findings
- Only report findings for tools in the "Successful Tools" list
- For tools in "Failed Tools", mention the failure in limitations section

If ALL scans failed (all tools in Failed Tools list):
  → findings[] MUST be empty []
  → overall_risk MUST be "LOW"
  → Explain in limitations that target is heavily firewalled/protected

"""

    prompt = f"""{_SYSTEM_PROMPT}
{validation_note}
═══════════════════════════════════════════════════════════════
  REPORT GENERATION REQUEST
  Tester : {tester}
═══════════════════════════════════════════════════════════════

TARGET METADATA
  URL / IP    : {target}
  Scope       : {scope or 'As defined in engagement'}
  Date        : {date}
  Report Ref  : {report_ref}
  Tester      : {tester}

METHODOLOGY (populate tools_and_methodology.methodology_phases with these):
{phases_str}

CVE RAG NOTE (populate tools_and_methodology.cve_rag_note with this):
  {_CVE_RAG_NOTE}

═══════════════════════════════════════════════════════════════
  OUTPUT FORMAT — READ CAREFULLY
═══════════════════════════════════════════════════════════════

1. Respond with ONLY valid JSON. No markdown fences, no prose outside JSON.
2. The JSON MUST match this schema exactly:

{schema_str}

3. findings[] — one object per CONFIRMED vulnerability only.
4. mitigations[] — one object per finding, same finding_id.
5. incident_response.per_vuln_response[] — one object per finding.
6. risk_assessment.business_impact_table[] — one row per finding.
7. glossary[] — minimum 25 terms. Must include:
   RAG, FTS5, CVE, CVSS, CWE, NVD, MITRE, OWASP, SQL Injection,
   XSS, RCE, LFI, SSRF, IDOR, Brute Force, Directory Traversal,
   Privilege Escalation, Payload, Exploit, Vulnerability, Patch,
   Zero-Day, Attack Surface, Penetration Testing, Scope.
8. signoff.tester = "{tester}"
9. metadata.tester = "{tester}"
10. metadata.report_ref = "{report_ref}"
{extra_instructions}

═══════════════════════════════════════════════════════════════
  SCAN RESULTS AND CVE INTELLIGENCE
═══════════════════════════════════════════════════════════════

{scan_context}

═══════════════════════════════════════════════════════════════
Respond now with the JSON report object only.
═══════════════════════════════════════════════════════════════"""

    return prompt
