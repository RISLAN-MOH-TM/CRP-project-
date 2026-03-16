#!/usr/bin/env python3
"""
MCP Server — Kali Pentest Tools + CVE RAG System
Run this file and Claude Desktop gets all tools automatically.

Claude Desktop config (claude_mcp_config.json):
    {
      "mcpServers": {
        "kali-pentest": {
          "command": "python",
          "args": ["C:\\path\\to\\mcp_server.py", "--server", "http://KALI_IP:5000"],
          "env": { "KALI_API_KEY": "your-key" }
        }
      }
    }

On startup this file:
  1. Connects to Kali Flask API (pentest tools)
  2. Loads RAGEngine from rag.py (auto-detects hybrid vs FTS5 mode)
  3. Registers all MCP tools with Claude
"""

import argparse
import json
import logging
import os
import sys
import time
import glob
from typing import Any, Dict, Optional, List
from datetime import datetime
from collections import Counter, defaultdict

import requests
from mcp.server.fastmcp import FastMCP

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# -- Config --------------------------------------------------------------------
DEFAULT_KALI_SERVER  = os.environ.get("KALI_SERVER_URL", "http://192.168.8.177:5000")
DEFAULT_TIMEOUT      = 1800
DEFAULT_API_KEY      = "kali-research-project-2026"
API_KEY              = os.environ.get("KALI_API_KEY", DEFAULT_API_KEY)
RESULTS_DIR          = os.path.join(os.path.dirname(__file__), "results")
RAW_DIR              = os.path.join(RESULTS_DIR, "raw")      # tool JSON outputs
REPORTS_DIR          = os.path.join(RESULTS_DIR, "reports")  # final PDF reports
os.makedirs(RAW_DIR,     exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# -- RAG engine (auto-init on import) -----------------------------------------
try:
    from rag import RAGEngine
    _rag = RAGEngine()
    if _rag.ready:
        logger.info(f"RAG engine ready — mode: {_rag.mode}")
    else:
        logger.warning("RAG DB not built yet. Run: python rag.py --build-fts")
except Exception as _e:
    _rag = None
    logger.warning(f"RAG engine failed to load: {_e}")


# ------------------------------------------------------------------------------
# Kali API client
# ------------------------------------------------------------------------------

class KaliClient:
    def __init__(self, server_url: str, timeout: int = DEFAULT_TIMEOUT, api_key: str = ""):
        if not server_url.startswith(("http://", "https://")):
            server_url = f"http://{server_url}"
        self.url     = server_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"X-API-Key": api_key} if api_key else {}

    def post(self, endpoint: str, data: dict) -> dict:
        """POST to Kali API. Returns job dict (202) or error dict."""
        try:
            r = requests.post(f"{self.url}/{endpoint}", json=data,
                              timeout=30, headers=self.headers)
            if r.status_code == 429:
                return {"success": False, "rate_limited": True,
                        "error": "Rate limit exceeded",
                        "retry_after": r.headers.get("Retry-After", "60s")}
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def wait_for_job(self, job_id: str, poll_interval: int = 5) -> dict:
        """Poll /api/jobs/<id> until status is done/failed. Returns full result."""
        url = f"{self.url}/api/jobs/{job_id}"
        start = time.time()
        while True:
            try:
                r = requests.get(url, headers=self.headers, timeout=15)
                r.raise_for_status()
                data = r.json()
                status = data.get("status", "")
                elapsed = int(time.time() - start)
                if status in ("done", "failed"):
                    return data
                logger.info(f"Job {job_id[:8]} {status} — {elapsed}s elapsed")
                time.sleep(poll_interval)
            except Exception as e:
                return {"success": False, "error": str(e)}

    def get(self, endpoint: str, params: dict = None, timeout: int = None) -> dict:
        try:
            r = requests.get(f"{self.url}/{endpoint}", params=params or {},
                             timeout=timeout or self.timeout, headers=self.headers)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def health(self) -> dict:
        """Quick connectivity check — 5s timeout, never blocks."""
        try:
            r = requests.get(f"{self.url}/health", headers=self.headers, timeout=5)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": f"Cannot connect to Kali server at {self.url} — is kali_server.py running?"}
        except requests.exceptions.Timeout:
            return {"success": False, "error": f"Kali server at {self.url} timed out (5s) — check IP and port"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def _save(tool: str, target: str, result: dict) -> str:
    """Save raw tool JSON output into results/raw/"""
    try:
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = target.replace("/","_").replace(":","_").replace("\\","_")
        path = os.path.join(RAW_DIR, f"{tool}_{safe}_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"tool": tool, "target": target, "timestamp": ts,
                       "datetime": datetime.now().isoformat(), **result},
                      f, indent=2, ensure_ascii=False)
        return path
    except Exception as e:
        logger.error(f"Save error: {e}")
        return ""


def _fmt(result: dict, title: str) -> str:
    sep = "=" * 70
    out = f"\n{sep}\n{title}\n{sep}\n\n"
    if result.get("rate_limited"):
        return out + f"RATE LIMITED — retry after {result.get('retry_after','60s')}\n"
    if result.get("concurrent_limit_reached"):
        return out + "MAX CONCURRENT SCANS REACHED — wait and retry\n"
    if not result.get("success") and result.get("error"):
        out += f"ERROR: {result['error']}\n"
        if result.get("stdout"):
            out += f"\nPARTIAL OUTPUT:\n{result['stdout'][:5000]}\n"
        return out
    if result.get("timed_out"):
        out += "TIMED OUT (partial results below)\n\n"
    if result.get("success"):
        out += "COMPLETED SUCCESSFULLY\n\n"
    if result.get("stdout"):
        out += f"OUTPUT:\n{'-'*70}\n{result['stdout']}\n{'-'*70}\n"
    if result.get("stderr", "").strip():
        out += f"\nWARNINGS:\n{result['stderr']}\n"
    out += f"\nReturn code: {result.get('return_code','N/A')}\n{sep}\n"
    return out


def _run_tool(kali: "KaliClient", endpoint: str, data: dict, title: str,
              save_as: str, save_target: str) -> str:
    """
    Submit async job ? poll until done ? format result.
    Returns formatted string for Claude.
    """
    sep = "=" * 70
    # Submit
    resp = kali.post(endpoint, data)
    if resp.get("error") and not resp.get("job_id"):
        return f"\n{sep}\n{title}\n{sep}\nERROR: {resp['error']}\n"
    if resp.get("rate_limited"):
        return f"\n{sep}\n{title}\n{sep}\nRATE LIMITED — {resp.get('retry_after','wait and retry')}\n"

    job_id = resp.get("job_id", "")
    if not job_id:
        # Old-style synchronous response (fallback)
        fp = _save(save_as, save_target, resp)
        out = _fmt(resp, title)
        if fp: out += f"\nSaved: {fp}\n"
        return out

    # Poll
    result = kali.wait_for_job(job_id)
    fp = _save(save_as, save_target, result)
    out = _fmt(result, title)
    out += f"\nJob ID: {job_id}\n"
    if fp: out += f"Saved: {fp}\n"
    return out


def _load_results() -> List[dict]:
    """Load all raw tool JSON outputs from results/raw/, newest first."""
    out = []
    for fp in sorted(glob.glob(os.path.join(RAW_DIR, "*.json")), reverse=True):
        try:
            with open(fp, encoding="utf-8") as f:
                out.append(json.load(f))
        except Exception:
            pass
    return out


def _rag_check() -> Optional[str]:
    """Return error string if RAG not ready, else None."""
    if _rag is None:
        return "RAG engine failed to load. Check rag.py exists."
    if not _rag.ready:
        return "CVE database not built. Run: python rag.py --build-fts"
    return None


# ------------------------------------------------------------------------------
# MCP server setup
# ------------------------------------------------------------------------------

def build_mcp(kali: KaliClient) -> FastMCP:
    mcp = FastMCP("kali-pentest-rag")

    # -- Pentest tools ---------------------------------------------------------

    @mcp.tool(name="nmap_scan")
    def nmap_scan(target: str, scan_type: str = "-sCV", ports: str = "",
                  additional_args: str = "") -> str:
        """Nmap port scan + service/version detection."""
        return _run_tool(kali, "api/tools/nmap",
            {"target": target, "scan_type": scan_type, "ports": ports, "additional_args": additional_args},
            f"Nmap: {target}", "nmap", target)

    @mcp.tool(name="masscan_scan")
    def masscan_scan(target: str, ports: str = "1-65535", rate: int = 1000, additional_args: str = "") -> str:
        """Masscan fast port scanner."""
        return _run_tool(kali, "api/tools/masscan",
            {"target": target, "ports": ports, "rate": rate, "additional_args": additional_args},
            f"Masscan: {target}", "masscan", target)

    @mcp.tool(name="nikto_scan")
    def nikto_scan(target: str, additional_args: str = "") -> str:
        """Nikto web server vulnerability scanner."""
        return _run_tool(kali, "api/tools/nikto",
            {"target": target, "additional_args": additional_args},
            f"Nikto: {target}", "nikto", target)

    @mcp.tool(name="whatweb_scan")
    def whatweb_scan(target: str, aggression: int = 1, additional_args: str = "") -> str:
        """WhatWeb technology fingerprinting."""
        return _run_tool(kali, "api/tools/whatweb",
            {"target": target, "aggression": aggression, "additional_args": additional_args},
            f"WhatWeb: {target}", "whatweb", target)

    @mcp.tool(name="gobuster_scan")
    def gobuster_scan(url: str, mode: str = "dir", wordlist: str = "/usr/share/wordlists/dirb/common.txt", additional_args: str = "") -> str:
        """Gobuster directory/DNS/vhost enumeration."""
        return _run_tool(kali, "api/tools/gobuster",
            {"url": url, "mode": mode, "wordlist": wordlist, "additional_args": additional_args},
            f"Gobuster: {url}", "gobuster", url)

    @mcp.tool(name="ffuf_scan")
    def ffuf_scan(url: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt", mode: str = "dir", max_results: int = 100, additional_args: str = "") -> str:
        """FFUF web fuzzer."""
        return _run_tool(kali, "api/tools/ffuf",
            {"url": url, "wordlist": wordlist, "mode": mode, "max_results": max_results, "additional_args": additional_args},
            f"FFUF: {url}", "ffuf", url)

    @mcp.tool(name="feroxbuster_scan")
    def feroxbuster_scan(url: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt", threads: int = 50, max_results: int = 200, additional_args: str = "") -> str:
        """Feroxbuster recursive web content scanner."""
        return _run_tool(kali, "api/tools/feroxbuster",
            {"url": url, "wordlist": wordlist, "threads": threads, "max_results": max_results, "additional_args": additional_args},
            f"Feroxbuster: {url}", "feroxbuster", url)

    @mcp.tool(name="sqlmap_scan")
    def sqlmap_scan(url: str, data: str = "", additional_args: str = "") -> str:
        """SQLmap SQL injection scanner."""
        return _run_tool(kali, "api/tools/sqlmap",
            {"url": url, "data": data, "additional_args": additional_args},
            f"SQLmap: {url}", "sqlmap", url)

    @mcp.tool(name="nuclei_scan")
    def nuclei_scan(target: str, templates: str = "", severity: str = "critical,high,medium", additional_args: str = "") -> str:
        """Nuclei CVE template-based vulnerability scanner."""
        return _run_tool(kali, "api/tools/nuclei",
            {"target": target, "templates": templates, "severity": severity, "additional_args": additional_args},
            f"Nuclei: {target}", "nuclei", target)

    @mcp.tool(name="hydra_attack")
    def hydra_attack(target: str, service: str, username: str = "", username_file: str = "", password: str = "", password_file: str = "", additional_args: str = "") -> str:
        """Hydra brute-force credential testing."""
        return _run_tool(kali, "api/tools/hydra",
            {"target": target, "service": service, "username": username, "username_file": username_file,
             "password": password, "password_file": password_file, "additional_args": additional_args},
            f"Hydra: {target} [{service}]", "hydra", f"{target}_{service}")

    @mcp.tool(name="wpscan_analyze")
    def wpscan_analyze(url: str, additional_args: str = "") -> str:
        """WPScan WordPress vulnerability scanner."""
        return _run_tool(kali, "api/tools/wpscan",
            {"url": url, "additional_args": additional_args},
            f"WPScan: {url}", "wpscan", url)

    @mcp.tool(name="metasploit_run")
    def metasploit_run(module: str, options: Dict[str, Any] = {}) -> str:
        """Run a Metasploit module."""
        target = options.get("RHOSTS", options.get("RHOST", module.split("/")[-1]))
        return _run_tool(kali, "api/tools/metasploit",
            {"module": module, "options": options},
            f"Metasploit: {module}", "metasploit", target)

    @mcp.tool(name="searchsploit_search")
    def searchsploit_search(query: str, additional_args: str = "") -> str:
        """Search Exploit-DB for exploits."""
        return _run_tool(kali, "api/tools/searchsploit",
            {"query": query, "additional_args": additional_args},
            f"Searchsploit: {query}", "searchsploit", query)

    @mcp.tool(name="subfinder_scan")
    def subfinder_scan(domain: str, additional_args: str = "-silent") -> str:
        """Subfinder passive subdomain discovery."""
        return _run_tool(kali, "api/tools/subfinder",
            {"domain": domain, "additional_args": additional_args},
            f"Subfinder: {domain}", "subfinder", domain)

    @mcp.tool(name="amass_scan")
    def amass_scan(domain: str, mode: str = "enum", additional_args: str = "") -> str:
        """Amass subdomain enumeration."""
        return _run_tool(kali, "api/tools/amass",
            {"domain": domain, "mode": mode, "additional_args": additional_args},
            f"Amass: {domain}", "amass", domain)

    @mcp.tool(name="enum4linux_ng_scan")
    def enum4linux_ng_scan(target: str, additional_args: str = "-A") -> str:
        """Enum4linux-ng Windows/Samba enumeration."""
        return _run_tool(kali, "api/tools/enum4linux-ng",
            {"target": target, "additional_args": additional_args},
            f"Enum4linux-ng: {target}", "enum4linux-ng", target)

    @mcp.tool(name="john_crack")
    def john_crack(hash_file: str, wordlist: str = "/usr/share/wordlists/rockyou.txt", format_type: str = "", additional_args: str = "") -> str:
        """John the Ripper password cracker."""
        return _run_tool(kali, "api/tools/john",
            {"hash_file": hash_file, "wordlist": wordlist, "format": format_type, "additional_args": additional_args},
            f"John: {hash_file}", "john", hash_file.split("/")[-1])

    @mcp.tool(name="hashcat_crack")
    def hashcat_crack(hash_file: str, wordlist: str = "/usr/share/wordlists/rockyou.txt", hash_type: str = "", attack_mode: int = 0, additional_args: str = "") -> str:
        """Hashcat GPU/CPU password cracker."""
        return _run_tool(kali, "api/tools/hashcat",
            {"hash_file": hash_file, "wordlist": wordlist, "hash_type": hash_type, "attack_mode": attack_mode, "additional_args": additional_args},
            f"Hashcat: {hash_file}", "hashcat", hash_file.split("/")[-1])

    @mcp.tool(name="execute_command")
    def execute_command(command: str) -> str:
        """Execute an arbitrary command on the Kali server."""
        return _run_tool(kali, "api/command", {"command": command},
            f"Command: {command}", "command", command[:30])

    @mcp.tool(name="server_health")
    def server_health() -> str:
        """Check Kali API server health and available tools. Returns immediately (5s timeout)."""
        result = kali.health()
        if result.get("error"):
            return (
                f"KALI SERVER UNREACHABLE\n"
                f"{'='*50}\n"
                f"Error  : {result['error']}\n"
                f"Server : {kali.url}\n\n"
                f"Fix checklist:\n"
                f"  1. Is kali_server.py running on Kali?  ?  python kali_server.py\n"
                f"  2. Is the IP correct?  ?  check .env KALI_SERVER_URL or --server arg\n"
                f"  3. Is port 5000 reachable from Windows?  ?  ping {kali.url.split('//')[1].split(':')[0]}\n"
                f"  4. Is the API key correct?  ?  KALI_API_KEY in .env\n\n"
                f"RAG tools (cve_search, cve_lookup, etc.) still work without Kali."
            )
        lines = [
            f"KALI SERVER ONLINE",
            f"{'='*50}",
            f"Status          : {result.get('status','unknown')}",
            f"Async mode      : {result.get('async_mode', False)}",
            f"Max concurrent  : {result.get('max_concurrent_jobs', 'N/A')} jobs",
            f"Active jobs     : {result.get('active_jobs', 0)}",
            f"\nTools:",
        ]
        for tool, avail in result.get("tools_status", {}).items():
            lines.append(f"  {'?' if avail else '? MISSING'} {tool}")
        rag_status = "ready" if (_rag and _rag.ready) else "not built — run: python rag.py --build-fts"
        lines.append(f"\nRAG engine      : {rag_status}")
        if _rag and _rag.ready:
            lines.append(f"RAG mode        : {_rag.mode}")
        return "\n".join(lines)

    @mcp.tool(name="get_job_status")
    def get_job_status(job_id: str) -> str:
        """Poll a running job by ID. Returns current status and output so far."""
        result = kali.get(f"api/jobs/{job_id}", timeout=10)
        if result.get("error"):
            return f"ERROR: {result['error']}"
        status = result.get("status","unknown")
        out = f"Job {job_id[:8]}... | Status: {status}\n"
        out += f"Tool: {result.get('tool','')} | Started: {result.get('started','')}\n"
        if status in ("done","failed"):
            out += f"Finished: {result.get('finished','')} | RC: {result.get('return_code','N/A')}\n"
            stdout = result.get("stdout","")
            if stdout:
                out += f"\nOUTPUT:\n{'-'*60}\n{stdout[:8000]}\n"
        return out

    @mcp.tool(name="get_scan_history")
    def get_scan_history(limit: int = 20) -> str:
        """Get recent job history from Kali server AND show what's already saved locally."""
        sep = "=" * 70
        lines = [f"\n{sep}", "SCAN HISTORY", sep]

        # Remote jobs on Kali server
        result = kali.get("api/jobs", {"limit": limit}, timeout=10)
        if result.get("error"):
            lines.append(f"Kali server: ERROR — {result['error']}")
        else:
            jobs = result.get("jobs", [])
            lines.append(f"\nKali server — {len(jobs)} recent job(s):")
            for j in jobs:
                icon = "DONE" if j.get("status") == "done" else j.get("status","?").upper()
                lines.append(f"  [{icon}] {j.get('tool','').upper():15s} job={j.get('job_id','')[:8]}...  started={j.get('started','')}")

        # Local results already saved
        local = _load_results()
        lines.append(f"\nLocal results/raw/ — {len(local)} file(s):")
        for r in local[:limit]:
            lines.append(f"  [SAVED] {r.get('tool','?').upper():15s} target={r.get('target','')}  ts={r.get('timestamp','')}")

        lines.append(f"\n{sep}")
        lines.append("TIP: Call pull_scan_results() to fetch completed Kali jobs into results/raw/")
        lines.append(f"{sep}\n")
        return "\n".join(lines)

    @mcp.tool(name="pull_scan_results")
    def pull_scan_results(target_filter: str = "", limit: int = 50) -> str:
        """
        Pull completed scan results from the Kali server into results/raw/.

        Use this to recover results from a previous MCP session or if scan
        results were not saved locally (e.g. after a restart).

        How it works:
          1. Fetches the job list from GET /api/jobs on the Kali server
          2. For each completed job not already saved locally, fetches full output
             from GET /api/jobs/<job_id>
          3. Writes the result as a JSON file into results/raw/
          4. prepare_scan_context() will then pick them all up automatically

        Args:
            target_filter: optional string — only pull jobs whose tool output
                           contains this string (e.g. an IP or domain).
                           Leave empty to pull all completed jobs.
            limit:         max number of jobs to fetch (default 50)

        Returns:
            Summary of what was pulled and saved.
        """
        sep = "=" * 70
        lines = [f"\n{sep}", "PULL SCAN RESULTS FROM KALI SERVER", sep]

        # Get job list from server
        result = kali.get("api/jobs", {"limit": limit}, timeout=10)
        if result.get("error"):
            return f"ERROR fetching job list: {result['error']}"

        jobs = result.get("jobs", [])
        if not jobs:
            return "No jobs found on Kali server."

        # Build set of job_ids already saved locally to avoid duplicates
        existing_ids: set = set()
        for r in _load_results():
            jid = r.get("job_id", "")
            if jid:
                existing_ids.add(jid)

        pulled = 0
        skipped_existing = 0
        skipped_not_done = 0
        errors = 0

        for j in jobs:
            job_id = j.get("job_id", "")
            status = j.get("status", "")
            tool   = j.get("tool", "unknown")

            if status != "done":
                skipped_not_done += 1
                continue

            if job_id in existing_ids:
                skipped_existing += 1
                continue

            # Fetch full result
            full = kali.get(f"api/jobs/{job_id}")
            if full.get("error"):
                lines.append(f"  ERROR fetching {job_id[:8]}: {full['error']}")
                errors += 1
                continue

            stdout = full.get("stdout", "")

            # Apply target filter if specified
            if target_filter and target_filter.lower() not in stdout.lower():
                continue

            # Derive target from stdout or job metadata
            target = j.get("target", target_filter or "unknown")

            # Save into results/raw/
            fp = _save(tool, target, full)
            if fp:
                lines.append(f"  [PULLED] {tool.upper():15s} job={job_id[:8]}...  ? {os.path.basename(fp)}")
                pulled += 1
            else:
                errors += 1

        lines.append(f"\n{sep}")
        lines.append(f"Pulled   : {pulled} new result(s) saved to results/raw/")
        lines.append(f"Skipped  : {skipped_existing} already local, {skipped_not_done} still running")
        if errors:
            lines.append(f"Errors   : {errors}")
        lines.append(f"{sep}")

        if pulled > 0:
            lines.append("\nResults are now in results/raw/ — call prepare_scan_context() to build the report.")
        else:
            lines.append("\nNo new results to pull.")

        return "\n".join(lines)


    # -- CVE RAG tools ---------------------------------------------------------

    @mcp.tool(name="cve_search")
    def cve_search(query: str, top_k: int = 10) -> str:
        """Hybrid CVE search — vector + FTS5 + alias resolver + RRF merge.
        Works for natural language: 'react file upload', 'rce apache', 'sql injection mysql 5.7'."""
        err = _rag_check()
        if err: return f"RAG ERROR: {err}"
        results = _rag.search(query, top_k=top_k)
        if not results: return f"No CVEs found for: '{query}'"
        sep = "=" * 70
        out = f"\n{sep}\nCVE SEARCH: {query}\n{sep}\nMode: {_rag.mode} | Found: {len(results)}\n\n"
        out += _rag.format_results(results)
        return out

    @mcp.tool(name="cve_lookup")
    def cve_lookup(cve_id: str) -> str:
        """Exact CVE ID lookup — full details: CVSS, CWE, affected versions, references."""
        err = _rag_check()
        if err: return f"RAG ERROR: {err}"
        r = _rag.get(cve_id)
        if not r: return f"CVE '{cve_id}' not found in local database."
        sep = "=" * 70
        out  = f"\n{sep}\n{r['cve_id']} — {r.get('severity','UNKNOWN')}\n{sep}\n"
        out += f"CVSS Score  : {r.get('cvss_score','N/A')}\n"
        out += f"CVSS Vector : {r.get('cvss_vector','N/A')}\n"
        out += f"CWE         : {', '.join(r.get('cwes',[])) or 'N/A'}\n"
        out += f"Vendor      : {', '.join(r.get('vendors',[])) or 'N/A'}\n"
        out += f"Product     : {', '.join(r.get('products',[])) or 'N/A'}\n"
        out += f"Versions    : {', '.join(r.get('versions',[])[:5]) or 'N/A'}\n"
        out += f"Published   : {r.get('date_published','N/A')}\n"
        out += f"\nDescription:\n{r.get('description','N/A')}\n"
        refs = r.get("references", [])
        if refs:
            out += "\nReferences:\n" + "\n".join(f"  {ref}" for ref in refs[:3])
        out += f"\n{sep}\n"
        return out

    @mcp.tool(name="cve_enrich_services")
    def cve_enrich_services(services: str, limit_per: int = 5) -> str:
        """Batch CVE enrichment for all services from nmap/whatweb.
        services: comma-separated 'product version' pairs e.g. 'apache 2.4.49, php 7.4.3'"""
        err = _rag_check()
        if err: return f"RAG ERROR: {err}"
        svc_list = [s.strip() for s in services.split(",") if s.strip()]
        if not svc_list: return "No services provided."
        results = _rag.batch_search(svc_list, limit_per=limit_per)
        sep = "=" * 70
        out = f"\n{sep}\nCVE ENRICHMENT — {len(svc_list)} service(s)\n{sep}\n"
        total = 0
        for svc, cves in results.items():
            out += f"\n[{svc.upper()}] — {len(cves)} CVE(s)\n{'-'*60}\n"
            out += _rag.format_results(cves) if cves else "  No CVEs found.\n"
            total += len(cves)
        out += f"\n{sep}\nTotal CVEs: {total}\n{sep}\n"
        return out

    @mcp.tool(name="cve_by_severity")
    def cve_by_severity(severity: str, year: str = "", limit: int = 20) -> str:
        """Get top CVEs by severity (CRITICAL/HIGH/MEDIUM/LOW), optionally filtered by year."""
        err = _rag_check()
        if err: return f"RAG ERROR: {err}"
        results = _rag.by_severity(severity, year=year, limit=limit)
        if not results: return f"No {severity} CVEs found{' for '+year if year else ''}."
        sep = "=" * 70
        label = f"{severity.upper()} CVEs{' ('+year+')' if year else ''}"
        return f"\n{sep}\n{label} — Top {len(results)}\n{sep}\n\n" + _rag.format_results(results)

    @mcp.tool(name="cve_database_stats")
    def cve_database_stats() -> str:
        """CVE database statistics — total, severity breakdown, vector count, search mode."""
        err = _rag_check()
        if err: return f"RAG ERROR: {err}"
        s = _rag.stats()
        if "error" in s: return f"ERROR: {s['error']}"
        sep = "=" * 70
        out  = f"\n{sep}\nCVE DATABASE STATISTICS\n{sep}\n"
        out += f"Total CVEs     : {s.get('total_cves',0):,}\n"
        out += f"Vector indexed : {s.get('vector_count',0):,}\n"
        out += f"Search mode    : {s.get('search_mode','')}\n"
        out += f"DB size        : {s.get('db_size_mb',0)} MB\n"
        out += f"FTS built at   : {s.get('fts_built_at','not built')}\n"
        out += "\nBy Severity:\n" + "\n".join(f"  {k:10s}: {v:,}" for k,v in s.get("by_severity",{}).items())
        out += "\nBy Source:\n"   + "\n".join(f"  {k:10s}: {v:,}" for k,v in s.get("by_source",{}).items())
        out += "\nRecent Years:\n"+ "\n".join(f"  {k}: {v:,}" for k,v in s.get("recent_years",{}).items())
        out += f"\n{sep}\n"
        return out

    @mcp.tool(name="cve_build_report_context")
    def cve_build_report_context(services: str = "", confirmed_cves: str = "",
                                  vuln_types: str = "", max_per_item: int = 5) -> str:
        """Build complete CVE intelligence context block for report generation.
        Call once after all scans. services: 'apache 2.4.49, php 7.4'
        confirmed_cves: 'CVE-2021-44228, CVE-2023-44487'  vuln_types: 'sql injection, xss'"""
        err = _rag_check()
        if err: return f"RAG ERROR: {err}"
        sep = "=" * 70
        lines = [f"\n{sep}", "CVE INTELLIGENCE CONTEXT", sep, f"Search mode: {_rag.mode}\n"]
        if confirmed_cves:
            ids = [c.strip() for c in confirmed_cves.split(",") if c.strip()]
            lines.append(f"--- CONFIRMED CVEs ({len(ids)}) ---")
            for cid in ids:
                r = _rag.get(cid)
                if r:
                    lines.append(f"\n{cid} [{r.get('severity','?')}] CVSS:{r.get('cvss_score','N/A')}")
                    lines.append(f"  CWE: {', '.join(r.get('cwes',[])) or 'N/A'}")
                    lines.append(f"  Desc: {r.get('description','')[:300]}")
                    lines.append(f"  Ref: {(r.get('references') or ['N/A'])[0]}")
                else:
                    lines.append(f"\n{cid}: not in local DB")
        if services:
            svc_list = [s.strip() for s in services.split(",") if s.strip()]
            lines.append(f"\n--- SERVICE ENRICHMENT ({len(svc_list)} services) ---")
            for svc in svc_list:
                results = _rag.search(svc, top_k=max_per_item)
                lines.append(f"\n[{svc.upper()}] — {len(results)} CVE(s)")
                for r in results:
                    lines.append(f"  — {r['cve_id']} [{r.get('severity','')}] CVSS:{r.get('cvss_score','N/A')} — {r.get('description','')[:180]}")
        if vuln_types:
            vt_list = [v.strip() for v in vuln_types.split(",") if v.strip()]
            lines.append(f"\n--- VULNERABILITY TYPE HISTORY ---")
            for vt in vt_list:
                results = _rag.search(vt, top_k=max_per_item)
                lines.append(f"\n[{vt.upper()}] — {len(results)} historical CVE(s)")
                for r in results:
                    lines.append(f"  — {r['cve_id']} [{r.get('severity','')}] CVSS:{r.get('cvss_score','N/A')}")
        lines.append(f"\n{sep}\nEND CVE CONTEXT\n{sep}")
        return "\n".join(lines)

    # -- Report generation tools removed ---------------------------------------
    # System stops after scanning and CVE enrichment.
    # No prepare_scan_context, render_pdf_report, or chunk_large_output.
    # Users manually analyze results from results/raw/ directory.

    return mcp


# ------------------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Kali Pentest MCP Server with CVE RAG + AI Analysis")
    parser.add_argument("--server",  default=DEFAULT_KALI_SERVER,
                        help=f"Kali API URL (default: {DEFAULT_KALI_SERVER})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--debug",   action="store_true")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    kali = KaliClient(args.server, args.timeout, API_KEY)
    health = kali.health()
    if health.get("error"):
        logger.warning(f"Kali server unreachable: {health['error']} — pentest tools will fail")
    else:
        logger.info(f"Kali server connected: {health.get('status','ok')}")

    mcp = build_mcp(kali)
    logger.info("MCP server starting — all tools registered")
    mcp.run()


if __name__ == "__main__":
    main()

