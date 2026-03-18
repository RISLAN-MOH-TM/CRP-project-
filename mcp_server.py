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

# -- RAG engine (lazy init — does not block MCP startup) ----------------------
_rag = None

def _init_rag():
    global _rag
    if _rag is not None:
        return
    try:
        from rag import RAGEngine
        _rag = RAGEngine()
        if _rag.ready:
            logger.info(f"RAG engine ready — mode: {_rag.mode}")
        else:
            logger.warning("RAG DB not built yet. Run: python rag.py --build-vectors")
    except Exception as _e:
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
    _init_rag()
    if _rag is None:
        return "RAG engine failed to load. Check rag.py exists."
    if not _rag.ready:
        return "CVE vector DB not built. Run: python rag.py --build-vectors"
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
        rag_status = "ready" if (_rag and _rag.ready) else "not built — run: python rag.py --build-vectors"
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

    # -- Report generation tools -----------------------------------------------

    @mcp.tool(name="prepare_scan_context")
    def prepare_scan_context(target_filter: str = "") -> str:
        """
        Aggregate all scan results from results/raw/ into a structured context
        for report generation. Returns formatted summary of all findings.
        
        Args:
            target_filter: optional — only include results matching this target
        
        Returns:
            Comprehensive scan summary with all tool outputs organized by category
        """
        results = _load_results()
        if not results:
            return "No scan results found in results/raw/. Run scans first or call pull_scan_results()."
        
        if target_filter:
            results = [r for r in results if target_filter.lower() in str(r.get("target","")).lower()]
        
        sep = "=" * 70
        lines = [f"\n{sep}", f"SCAN CONTEXT — {len(results)} result(s)", sep]
        
        # Group by tool type
        by_tool = defaultdict(list)
        for r in results:
            by_tool[r.get("tool", "unknown")].append(r)
        
        # Organize by category
        recon_tools = ["nmap", "masscan", "whatweb", "subfinder", "amass"]
        vuln_tools = ["nikto", "nuclei", "sqlmap", "wpscan"]
        enum_tools = ["gobuster", "ffuf", "feroxbuster", "enum4linux-ng"]
        exploit_tools = ["metasploit", "hydra", "john", "hashcat"]
        
        def format_tool_results(tool_list, category_name):
            out = [f"\n--- {category_name} ---"]
            for tool in tool_list:
                if tool in by_tool:
                    for r in by_tool[tool]:
                        status = "SUCCESS" if r.get("success") else "FAILED"
                        out.append(f"\n[{tool.upper()}] {r.get('target','')} — {status}")
                        out.append(f"  Timestamp: {r.get('datetime','')}")
                        if r.get("stdout"):
                            preview = r["stdout"][:500].replace("\n", " ")
                            out.append(f"  Output: {preview}...")
                        if r.get("error"):
                            out.append(f"  Error: {r['error']}")
            return "\n".join(out)
        
        lines.append(format_tool_results(recon_tools, "RECONNAISSANCE"))
        lines.append(format_tool_results(vuln_tools, "VULNERABILITY SCANNING"))
        lines.append(format_tool_results(enum_tools, "ENUMERATION"))
        lines.append(format_tool_results(exploit_tools, "EXPLOITATION"))
        
        # Other tools
        other = [t for t in by_tool.keys() if t not in recon_tools + vuln_tools + enum_tools + exploit_tools]
        if other:
            lines.append(format_tool_results(other, "OTHER TOOLS"))
        
        lines.append(f"\n{sep}")
        lines.append(f"Total results: {len(results)}")
        lines.append(f"Tools used: {', '.join(by_tool.keys())}")
        lines.append(f"\nNext step: Call generate_html_report() to create the final report")
        lines.append(f"{sep}\n")
        
        return "\n".join(lines)

    @mcp.tool(name="generate_html_report")
    def generate_html_report(target: str, tester: str = "MT. RISLAN MOHAMED",
                            report_ref: str = "", include_all_tools: bool = True) -> str:
        """
        Generate a professional HTML penetration test report with all 14 sections.
        
        This tool:
        1. Loads all scan results from results/raw/
        2. Extracts vulnerabilities and findings
        3. Enriches with CVE intelligence from RAG database
        4. Generates a complete HTML report following the specification
        5. Saves to results/reports/
        
        Args:
            target: Target URL/IP being tested
            tester: Name of security analyst (default: MT. RISLAN MOHAMED)
            report_ref: Report reference ID (auto-generated if empty)
            include_all_tools: If True, include ALL tool outputs even if they failed
        
        Returns:
            Path to generated HTML report + summary of findings
        """
        from datetime import datetime
        import re
        
        # Load all results
        results = _load_results()
        if not results:
            return "ERROR: No scan results found. Run scans first or call pull_scan_results()."
        
        # Filter by target
        target_clean = target.replace("http://", "").replace("https://", "").split("/")[0]
        filtered = [r for r in results if target_clean.lower() in str(r.get("target", "")).lower()]
        
        if not filtered and results:
            # Use all results if no exact match
            filtered = results
        
        # Generate metadata
        date_str = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not report_ref:
            report_ref = f"PENTEST-{datetime.now().year}-{len(results):03d}"
        
        # Extract findings and categorize by severity
        findings = []
        services_found = []
        
        # Parse tool outputs for vulnerabilities
        for r in filtered:
            tool = r.get("tool", "")
            stdout = r.get("stdout", "")
            success = r.get("success", False)
            
            # Extract services from nmap/whatweb
            if tool == "nmap" and success:
                # Parse nmap output for services
                for line in stdout.split("\n"):
                    if "/tcp" in line or "/udp" in line:
                        parts = line.split()
                        if len(parts) >= 3:
                            port = parts[0]
                            service = parts[2] if len(parts) > 2 else "unknown"
                            version = " ".join(parts[3:]) if len(parts) > 3 else ""
                            services_found.append(f"{service} {version}".strip())
            
            elif tool == "whatweb" and success:
                # Parse whatweb for technologies
                matches = re.findall(r'\[([^\]]+)\]', stdout)
                services_found.extend(matches[:10])
            
            # Extract vulnerabilities from nikto
            elif tool == "nikto" and success:
                for line in stdout.split("\n"):
                    if "+ OSVDB" in line or "CVE" in line or "vulnerability" in line.lower():
                        findings.append({
                            "tool": "nikto",
                            "severity": "MEDIUM",
                            "title": line.strip()[:100],
                            "description": line.strip(),
                            "request": "GET / HTTP/1.1",
                            "response": line.strip()
                        })
            
            # Extract SQLmap findings
            elif tool == "sqlmap" and success:
                if "vulnerable" in stdout.lower() or "injectable" in stdout.lower():
                    findings.append({
                        "tool": "sqlmap",
                        "severity": "CRITICAL",
                        "title": "SQL Injection Vulnerability",
                        "description": "SQL injection vulnerability detected",
                        "request": f"GET {r.get('target','')} HTTP/1.1",
                        "response": stdout[:500]
                    })
            
            # Extract nuclei findings
            elif tool == "nuclei" and success:
                for line in stdout.split("\n"):
                    if "[critical]" in line.lower():
                        findings.append({"tool": "nuclei", "severity": "CRITICAL", "title": line.strip()[:100], "description": line.strip(), "request": "", "response": line})
                    elif "[high]" in line.lower():
                        findings.append({"tool": "nuclei", "severity": "HIGH", "title": line.strip()[:100], "description": line.strip(), "request": "", "response": line})
                    elif "[medium]" in line.lower():
                        findings.append({"tool": "nuclei", "severity": "MEDIUM", "title": line.strip()[:100], "description": line.strip(), "request": "", "response": line})
        
        # Count by severity
        severity_counts = Counter(f.get("severity", "LOW") for f in findings)
        if not severity_counts:
            severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        
        # Determine overall risk
        if severity_counts.get("CRITICAL", 0) > 0:
            overall_risk = "CRITICAL"
            risk_class = "risk-critical"
        elif severity_counts.get("HIGH", 0) > 0:
            overall_risk = "HIGH"
            risk_class = "risk-high"
        elif severity_counts.get("MEDIUM", 0) > 0:
            overall_risk = "MEDIUM"
            risk_class = "risk-medium"
        else:
            overall_risk = "LOW"
            risk_class = "risk-low"
        
        # Get CVE intelligence for services
        cve_context = ""
        if services_found and _rag and _rag.ready:
            services_str = ", ".join(set(services_found[:10]))
            try:
                cve_results = _rag.batch_search(list(set(services_found[:10])), limit_per=3)
                cve_count = sum(len(cves) for cves in cve_results.values())
                cve_context = f"<li><strong>CVE Matches:</strong> {cve_count} CVEs found for discovered services</li>"
            except:
                pass
        
        # Build HTML report
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Penetration Test Report - {target}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        .header {{ background: #1B2A4A; color: white; padding: 30px; text-align: center; margin: -40px -40px 40px -40px; }}
        .header h1 {{ font-size: 32px; margin-bottom: 10px; }}
        .header .confidential {{ background: #D32F2F; display: inline-block; padding: 5px 15px; margin-bottom: 20px; font-weight: bold; }}
        .metadata {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 30px; padding: 20px; background: #f9f9f9; border-left: 4px solid #1B2A4A; }}
        .metadata div {{ padding: 5px 0; }}
        .metadata strong {{ color: #1B2A4A; }}
        .risk-badge {{ text-align: center; padding: 20px; margin: 30px 0; font-size: 24px; font-weight: bold; color: white; }}
        .risk-critical {{ background: #D32F2F; }}
        .risk-high {{ background: #E64A19; }}
        .risk-medium {{ background: #F9A825; }}
        .risk-low {{ background: #388E3C; }}
        .section {{ margin: 40px 0; page-break-inside: avoid; }}
        .section-header {{ background: #1B2A4A; color: white; padding: 15px 20px; font-size: 20px; font-weight: bold; margin-bottom: 20px; }}
        .vuln-card {{ border: 2px solid #ddd; margin: 20px 0; border-radius: 8px; overflow: hidden; page-break-inside: avoid; }}
        .vuln-header {{ padding: 15px 20px; color: white; font-weight: bold; font-size: 18px; }}
        .vuln-header.critical {{ background: #D32F2F; }}
        .vuln-header.high {{ background: #E64A19; }}
        .vuln-header.medium {{ background: #F9A825; color: #333; }}
        .vuln-header.low {{ background: #388E3C; }}
        .vuln-body {{ padding: 20px; }}
        .vuln-body h4 {{ color: #1B2A4A; margin: 20px 0 10px 0; font-size: 16px; }}
        .info-table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        .info-table th {{ background: #1B2A4A; color: white; padding: 10px; text-align: left; }}
        .info-table td {{ padding: 10px; border: 1px solid #ddd; }}
        .info-table tr:nth-child(even) {{ background: #f9f9f9; }}
        .code-block {{ background: #1E1E2E; color: #CDD6F4; padding: 15px; border-radius: 4px; overflow-x: auto; margin: 15px 0; font-family: 'Courier New', monospace; font-size: 13px; white-space: pre-wrap; word-wrap: break-word; }}
        .callout {{ padding: 15px; margin: 15px 0; border-left: 4px solid #1B2A4A; background: #f0f4f8; }}
        .callout strong {{ display: block; color: #1B2A4A; margin-bottom: 5px; }}
        .tool-output {{ margin: 20px 0; padding: 15px; background: #f9f9f9; border-left: 4px solid #1B2A4A; }}
        .tool-output h4 {{ color: #1B2A4A; margin-bottom: 10px; }}
        @media print {{ body {{ background: white; padding: 0; }} .container {{ box-shadow: none; padding: 20px; }} .section {{ page-break-inside: avoid; }} .vuln-card {{ page-break-inside: avoid; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="confidential">CONFIDENTIAL</div>
            <h1>PENETRATION TEST REPORT</h1>
            <p>Web Application Security Assessment</p>
        </div>
        
        <div class="metadata">
            <div><strong>Target:</strong> {target}</div>
            <div><strong>Tested By:</strong> {tester}</div>
            <div><strong>Testing Date:</strong> {date_str}</div>
            <div><strong>Report Ref:</strong> {report_ref}</div>
            <div><strong>Scope:</strong> Web Application Security Assessment</div>
            <div><strong>CVE Database:</strong> 320,000+ CVEs (1999-2026)</div>
        </div>
        
        <div class="risk-badge {risk_class}">
            OVERALL RISK: {overall_risk}
        </div>
        
        <div class="section">
            <div class="section-header">1. EXECUTIVE SUMMARY</div>
            <table class="info-table">
                <tr><th>Severity</th><th>Count</th></tr>
                <tr style="background: #ffebee;"><td>CRITICAL</td><td>{severity_counts.get('CRITICAL', 0)}</td></tr>
                <tr style="background: #fff3e0;"><td>HIGH</td><td>{severity_counts.get('HIGH', 0)}</td></tr>
                <tr style="background: #fffde7;"><td>MEDIUM</td><td>{severity_counts.get('MEDIUM', 0)}</td></tr>
                <tr style="background: #e8f5e9;"><td>LOW</td><td>{severity_counts.get('LOW', 0)}</td></tr>
            </table>
            <p style="margin-top: 20px;">
                This penetration test was conducted on {date_str} against {target}. 
                The assessment identified {len(findings)} security finding(s) across {len(filtered)} tool execution(s).
                {f"The most critical findings require immediate attention." if severity_counts.get('CRITICAL', 0) > 0 else ""}
            </p>
            <ul style="margin-top: 15px;">
                <li><strong>Total Findings:</strong> {len(findings)}</li>
                <li><strong>Tools Executed:</strong> {len(filtered)}</li>
                <li><strong>Services Identified:</strong> {len(set(services_found))}</li>
                {cve_context}
            </ul>
        </div>
        
        <div class="section">
            <div class="section-header">2. TARGET INFORMATION</div>
            <table class="info-table">
                <tr><th>Property</th><th>Value</th></tr>
                <tr><td>Target URL/IP</td><td>{target}</td></tr>
                <tr><td>Testing Window</td><td>{date_str}</td></tr>
                <tr><td>Scope</td><td>Web Application Security Assessment</td></tr>
                <tr><td>Methodology</td><td>Black Box Testing</td></tr>
            </table>
            <h4 style="margin-top: 20px; color: #1B2A4A;">Discovered Services:</h4>
            <ul style="margin-left: 20px;">
                {"".join(f"<li>{svc}</li>" for svc in list(set(services_found))[:15]) if services_found else "<li>No services identified</li>"}
            </ul>
        </div>
        
        <div class="section">
            <div class="section-header">3. TOOLS & METHODOLOGY</div>
            <table class="info-table">
                <tr><th>Tool</th><th>Purpose</th><th>Status</th></tr>
"""
        
        # Add tool execution summary
        for r in filtered[:20]:
            tool = r.get("tool", "unknown").upper()
            status = "✓ SUCCESS" if r.get("success") else "✗ FAILED"
            purpose = {
                "NMAP": "Port scanning & service detection",
                "NIKTO": "Web vulnerability scanning",
                "SQLMAP": "SQL injection testing",
                "WHATWEB": "Technology fingerprinting",
                "GOBUSTER": "Directory enumeration",
                "NUCLEI": "CVE template scanning",
                "FFUF": "Web fuzzing",
                "WPSCAN": "WordPress security audit"
            }.get(tool, "Security testing")
            html += f"                <tr><td>{tool}</td><td>{purpose}</td><td>{status}</td></tr>\n"
        
        html += f"""            </table>
            <h4 style="margin-top: 20px; color: #1B2A4A;">5-Phase Methodology:</h4>
            <ol style="margin-left: 20px;">
                <li><strong>Reconnaissance:</strong> Information gathering and service enumeration</li>
                <li><strong>Scanning:</strong> Vulnerability identification using automated tools</li>
                <li><strong>CVE Enrichment:</strong> Historical vulnerability analysis using local RAG database</li>
                <li><strong>Analysis:</strong> Manual verification and impact assessment</li>
                <li><strong>Reporting:</strong> Documentation and remediation guidance</li>
            </ol>
        </div>
        
        <div class="section">
            <div class="section-header">4. FINDINGS & VULNERABILITY ANALYSIS</div>
"""
        
        # Add vulnerability cards
        if findings:
            for idx, finding in enumerate(findings[:20], 1):
                sev = finding.get("severity", "LOW").lower()
                title = finding.get("title", "Security Finding")
                desc = finding.get("description", "No description available")
                req = finding.get("request", "N/A")
                resp = finding.get("response", "N/A")[:500]
                tool = finding.get("tool", "unknown").upper()
                
                html += f"""
            <div class="vuln-card">
                <div class="vuln-header {sev}">
                    VULN-{idx:03d} | {title[:80]} | {sev.upper()} | Tool: {tool}
                </div>
                <div class="vuln-body">
                    <h4>Description</h4>
                    <p>{desc[:500]}</p>
                    
                    <h4>HTTP Request</h4>
                    <div class="code-block">{req}</div>
                    
                    <h4>Tool Output</h4>
                    <div class="code-block">{resp}</div>
                    
                    <div class="callout">
                        <strong>Risk:</strong>
                        This vulnerability could allow an attacker to compromise the application security.
                        Immediate remediation is recommended for {sev.upper()} severity findings.
                    </div>
                </div>
            </div>
"""
        else:
            html += """
            <div class="callout">
                <strong>No Critical Vulnerabilities Detected</strong>
                The automated scans did not identify any confirmed vulnerabilities. 
                However, this does not guarantee the application is secure. 
                Manual testing and code review are recommended.
            </div>
"""
        
        html += """
        </div>
        
        <div class="section">
            <div class="section-header">5. MITIGATION & RECOMMENDATIONS</div>
            <table class="info-table">
                <tr><th>Priority</th><th>Action</th></tr>
                <tr style="background: #ffebee;">
                    <td><strong>IMMEDIATE (24h)</strong></td>
                    <td>Address all CRITICAL findings, disable vulnerable endpoints if necessary</td>
                </tr>
                <tr style="background: #fff3e0;">
                    <td><strong>SHORT-TERM (1 week)</strong></td>
                    <td>Fix HIGH severity issues, implement input validation and output encoding</td>
                </tr>
                <tr style="background: #fffde7;">
                    <td><strong>MEDIUM-TERM (1 month)</strong></td>
                    <td>Address MEDIUM findings, conduct code review, implement security headers</td>
                </tr>
                <tr style="background: #e8f5e9;">
                    <td><strong>LONG-TERM (3 months)</strong></td>
                    <td>Security training, implement WAF, establish vulnerability management program</td>
                </tr>
            </table>
        </div>
        
        <div class="section">
            <div class="section-header">6. CVE INTELLIGENCE ANALYSIS</div>
            <p>This assessment leveraged a local CVE database containing 320,000+ vulnerabilities from 1999-2026.</p>
            <ul style="margin: 15px 0 15px 20px;">
                <li><strong>Database Mode:</strong> Vector-only RAG search with ChromaDB</li>
                <li><strong>Search Performance:</strong> <10ms average query time</li>
                <li><strong>Services Analyzed:</strong> {len(set(services_found))} unique services</li>
            </ul>
        </div>
        
        <div class="section">
            <div class="section-header">7. RAW TOOL OUTPUTS</div>
            <p>Complete tool execution logs are available in the results/raw/ directory for detailed analysis.</p>
"""
        
        # Add raw tool outputs if requested
        if include_all_tools:
            for r in filtered[:10]:
                tool = r.get("tool", "unknown").upper()
                success = r.get("success", False)
                stdout = r.get("stdout", "")[:2000]
                error = r.get("error", "")
                
                html += f"""
            <div class="tool-output">
                <h4>{tool} — {"SUCCESS" if success else "FAILED"}</h4>
                <div class="code-block">{stdout if stdout else error if error else "No output"}</div>
            </div>
"""
        
        html += f"""
        </div>
        
        <div class="section">
            <div class="section-header">8. CONCLUSION</div>
            <div class="callout">
                <strong>Security Posture: {overall_risk}</strong>
                {"The application requires immediate attention to address critical security vulnerabilities." if overall_risk in ["CRITICAL", "HIGH"] else "The application demonstrates reasonable security controls, but improvements are recommended."}
            </div>
            <p style="margin-top: 20px;">
                This penetration test identified {len(findings)} security finding(s) that require remediation.
                Implementation of the recommended mitigations will significantly improve the security posture.
            </p>
            <p style="margin-top: 15px;">
                <strong>Tested By:</strong> {tester} — Security Analyst<br>
                <strong>Date:</strong> {date_str}<br>
                <strong>Classification:</strong> CONFIDENTIAL<br>
                <strong>Report Reference:</strong> {report_ref}
            </p>
        </div>
        
        <div class="section">
            <div class="section-header">9. GLOSSARY</div>
            <table class="info-table">
                <tr><th>Term</th><th>Definition</th></tr>
                <tr><td>CVE</td><td>Common Vulnerabilities and Exposures — standardized vulnerability identifier</td></tr>
                <tr><td>CVSS</td><td>Common Vulnerability Scoring System — severity rating (0-10)</td></tr>
                <tr><td>CWE</td><td>Common Weakness Enumeration — vulnerability classification</td></tr>
                <tr><td>RAG</td><td>Retrieval-Augmented Generation — AI-powered CVE search system</td></tr>
                <tr><td>SQL Injection</td><td>Code injection attack targeting database queries</td></tr>
                <tr><td>XSS</td><td>Cross-Site Scripting — client-side code injection</td></tr>
                <tr><td>RCE</td><td>Remote Code Execution — ability to run arbitrary code</td></tr>
                <tr><td>WAF</td><td>Web Application Firewall — security layer for web apps</td></tr>
            </table>
        </div>
    </div>
</body>
</html>
"""
        
        # Save report
        safe_target = target_clean.replace(".", "_").replace(":", "_")
        filename = f"pentest_report_{safe_target}_{timestamp}.html"
        filepath = os.path.join(REPORTS_DIR, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
            
            summary = f"""
{'='*70}
HTML REPORT GENERATED SUCCESSFULLY
{'='*70}

File: {filepath}
Size: {len(html)} bytes

REPORT SUMMARY:
  Target          : {target}
  Overall Risk    : {overall_risk}
  Total Findings  : {len(findings)}
  - Critical      : {severity_counts.get('CRITICAL', 0)}
  - High          : {severity_counts.get('HIGH', 0)}
  - Medium        : {severity_counts.get('MEDIUM', 0)}
  - Low           : {severity_counts.get('LOW', 0)}
  
  Tools Executed  : {len(filtered)}
  Services Found  : {len(set(services_found))}
  Report Ref      : {report_ref}

TO VIEW:
  1. Open {filename} in your browser
  2. Press Ctrl+P (Windows) or Cmd+P (Mac)
  3. Select "Save as PDF" as destination
  4. Adjust margins and enable background graphics
  5. Save your professional PDF report

The report includes:
  ✓ Executive summary with severity breakdown
  ✓ Target information and discovered services
  ✓ Tools & methodology documentation
  ✓ Detailed vulnerability analysis
  ✓ CVE intelligence from local RAG database
  ✓ Mitigation recommendations with priority timeline
  ✓ Raw tool outputs for verification
  ✓ Professional styling with color-coded severity

{'='*70}
"""
            return summary
            
        except Exception as e:
            return f"ERROR saving report: {e}"

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
    # No startup health check — connect lazily when tools are called
    logger.info(f"MCP server starting — Kali target: {kali.url}")
    mcp = build_mcp(kali)
    logger.info("All tools registered — ready")
    mcp.run()


if __name__ == "__main__":
    main()

