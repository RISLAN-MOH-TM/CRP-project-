#!/usr/bin/env python3
"""
Kali Linux Tools API Server — async job queue edition.

Every tool POST returns {job_id, status:"queued"} immediately (HTTP 202).
Claude then polls:  GET /api/jobs/<job_id>
Or streams live:    GET /api/jobs/<job_id>/stream  (SSE, real-time stdout)

Improvements over v1:
  - Non-blocking: all tools run in background threads
  - Real token-bucket rate limiter (no Redis needed)
  - API-key guard on ALL endpoints
  - 10 MB output cap prevents OOM on large nmap XML
  - SSE stream gives Claude live scan progress

Run on Kali:
    python kali_server.py --ip 0.0.0.0 --port 5000
"""

import argparse
import json
import logging
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from datetime import datetime
from functools import wraps
from typing import Any, Dict, Optional

from flask import Flask, Response, jsonify, request, stream_with_context

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Suppress watchdog/inotify debug spam when running with --debug
logging.getLogger("watchdog").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

# ── Config ────────────────────────────────────────────────────────────────────
API_PORT     = int(os.environ.get("API_PORT", 5000))
API_KEY      = os.environ.get("KALI_API_KEY", "kali-research-project-2026")
DEBUG_MODE   = os.environ.get("DEBUG_MODE", "0").lower() in ("1", "true", "yes")
SCAN_LOG_DIR = os.environ.get("SCAN_LOG_DIR", "/opt/scans/logs")
MAX_OUTPUT   = 10 * 1024 * 1024   # 10 MB hard cap per job
MAX_WORKERS  = 5                   # max concurrent background jobs
CMD_TIMEOUT  = 1800                # 30 min default per job

try:
    os.makedirs(SCAN_LOG_DIR, exist_ok=True)
except PermissionError:
    SCAN_LOG_DIR = os.path.expanduser("~/scans/logs")
    os.makedirs(SCAN_LOG_DIR, exist_ok=True)
app = Flask(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Auth — API key guard
# ══════════════════════════════════════════════════════════════════════════════

def require_api_key(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.headers.get("X-API-Key") != API_KEY:
            logger.warning(f"Bad API key from {request.remote_addr}")
            return jsonify({"error": "Invalid or missing API key"}), 401
        return f(*args, **kwargs)
    return wrapper


# ══════════════════════════════════════════════════════════════════════════════
# Rate limiter — token bucket, pure Python, no Redis
# ══════════════════════════════════════════════════════════════════════════════

# (capacity, refill_per_second)  →  burst size, sustained rate
RATE_LIMITS: Dict[str, tuple] = {
    "nmap":       (3, 0.05),    # 3 burst, 1 per 20 s
    "masscan":    (2, 0.033),   # 2 burst, 1 per 30 s
    "metasploit": (1, 0.016),   # 1 burst, 1 per 60 s
    "hydra":      (2, 0.033),
    "sqlmap":     (3, 0.05),
    "nuclei":     (3, 0.05),
    "default":    (5, 0.1),     # 5 burst, 1 per 10 s
}


class _Bucket:
    def __init__(self, cap: float, rate: float):
        self.cap    = cap
        self.tokens = float(cap)
        self.rate   = rate
        self.ts     = time.monotonic()
        self._lock  = threading.Lock()

    def consume(self) -> bool:
        with self._lock:
            now = time.monotonic()
            self.tokens = min(self.cap, self.tokens + (now - self.ts) * self.rate)
            self.ts = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


_buckets: Dict[str, _Bucket] = {}
_bl = threading.Lock()


def _get_bucket(tool: str) -> _Bucket:
    with _bl:
        if tool not in _buckets:
            cap, rate = RATE_LIMITS.get(tool, RATE_LIMITS["default"])
            _buckets[tool] = _Bucket(cap, rate)
        return _buckets[tool]


def rate_limit(tool: str):
    """Decorator — returns HTTP 429 if token bucket is empty."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not _get_bucket(tool).consume():
                return jsonify({
                    "error": f"Rate limit exceeded for {tool}. Wait and retry.",
                    "rate_limited": True,
                    "retry_after": "30s"
                }), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ══════════════════════════════════════════════════════════════════════════════
# Async job queue — background thread pool
# ══════════════════════════════════════════════════════════════════════════════

class Job:
    """Represents one background scan job."""

    def __init__(self, job_id: str, tool: str, command: str, timeout: int = CMD_TIMEOUT):
        self.job_id    = job_id
        self.tool      = tool
        self.command   = command
        self.timeout   = timeout
        self.status    = "queued"   # queued | running | done | failed
        self.stdout    = ""
        self.stderr    = ""
        self.rc: Optional[int] = None
        self.timed_out = False
        self.created   = datetime.now().isoformat()
        self.started: Optional[str]  = None
        self.finished: Optional[str] = None
        self._q        = queue.Queue()   # live stdout lines → SSE
        self.done      = threading.Event()

    def to_dict(self) -> dict:
        return {
            "job_id":      self.job_id,
            "tool":        self.tool,
            "status":      self.status,
            "created":     self.created,
            "started":     self.started,
            "finished":    self.finished,
            "timed_out":   self.timed_out,
            "return_code": self.rc,
            "success":     (self.rc == 0) or (self.timed_out and bool(self.stdout)),
            "stdout":      self.stdout,
            "stderr":      self.stderr,
        }


class JobQueue:
    def __init__(self, max_workers: int = MAX_WORKERS):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._sem  = threading.Semaphore(max_workers)

    def submit(self, tool: str, command: str, timeout: int = CMD_TIMEOUT) -> Job:
        job = Job(str(uuid.uuid4()), tool, command, timeout)
        with self._lock:
            self._jobs[job.job_id] = job
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        logger.info(f"Job {job.job_id[:8]} queued: {tool}")
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_recent(self, limit: int = 20):
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)[:limit]
        return [j.to_dict() for j in jobs]

    def _run(self, job: Job):
        if not self._sem.acquire(timeout=5):
            job.status = "failed"
            job.stderr = "Max concurrent jobs reached. Try again shortly."
            job._q.put(None)
            job.done.set()
            return

        job.status  = "running"
        job.started = datetime.now().isoformat()
        logger.info(f"Job {job.job_id[:8]} running: {job.command[:80]}")

        try:
            proc = subprocess.Popen(
                job.command, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1
            )

            out_buf, err_buf, total = [], [], 0

            def _read_stderr():
                for ln in iter(proc.stderr.readline, ""):
                    err_buf.append(ln)

            threading.Thread(target=_read_stderr, daemon=True).start()

            deadline = time.monotonic() + job.timeout
            for line in iter(proc.stdout.readline, ""):
                total += len(line)
                if total > MAX_OUTPUT:
                    job._q.put("[OUTPUT CAP 10 MB REACHED — truncated]\n")
                    proc.terminate()
                    job.timed_out = True
                    break
                out_buf.append(line)
                job._q.put(line)                  # live feed → SSE clients
                if time.monotonic() > deadline:
                    proc.terminate()
                    job.timed_out = True
                    break

            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

            job.rc       = proc.returncode if not job.timed_out else -1
            job.stdout   = "".join(out_buf)
            job.stderr   = "".join(err_buf)
            job.status   = "done"
            job.finished = datetime.now().isoformat()

        except Exception as e:
            job.status   = "failed"
            job.stderr   = f"{e}\n{traceback.format_exc()}"
            job.finished = datetime.now().isoformat()
        finally:
            job._q.put(None)       # sentinel — SSE generator exits
            job.done.set()
            self._sem.release()
            _persist(job)
            logger.info(f"Job {job.job_id[:8]} {job.status} rc={job.rc}")


_jq = JobQueue()


def _persist(job: Job):
    try:
        path = os.path.join(SCAN_LOG_DIR, f"{job.job_id}.json")
        with open(path, "w") as f:
            json.dump(job.to_dict(), f, indent=2)
    except Exception as e:
        logger.warning(f"Persist failed for {job.job_id[:8]}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def sanitize(arg: Any) -> str:
    """Strip shell-injection characters from a single argument."""
    s = str(arg)
    for ch in [";", "&", "|", "`", "$", "(", ")", "<", ">", "\n", "\r"]:
        s = s.replace(ch, "")
    return s


def _submit(tool: str, command: str, timeout: int = CMD_TIMEOUT) -> Response:
    """Submit job and return HTTP 202 with job_id + poll/stream URLs."""
    job = _jq.submit(tool, command, timeout)
    return jsonify({
        "job_id":     job.job_id,
        "status":     "queued",
        "tool":       tool,
        "message":    f"Job queued. Poll or stream for results.",
        "poll_url":   f"/api/jobs/{job.job_id}",
        "stream_url": f"/api/jobs/{job.job_id}/stream",
    }), 202


# ══════════════════════════════════════════════════════════════════════════════
# Job endpoints
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/jobs/<job_id>", methods=["GET"])
@require_api_key
def job_status(job_id: str):
    """Poll job status. Returns full stdout/stderr when done."""
    job = _jq.get(job_id)
    if not job:
        # Try persisted log
        path = os.path.join(SCAN_LOG_DIR, f"{job_id}.json")
        if os.path.exists(path):
            with open(path) as f:
                return jsonify(json.load(f))
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job.to_dict())


@app.route("/api/jobs/<job_id>/stream", methods=["GET"])
@require_api_key
def job_stream(job_id: str):
    """
    SSE stream — sends stdout lines in real time as the tool runs.
    Allows Claude to show live scan progress instead of waiting.

    Event format:
        data: <stdout line>\\n\\n
        data: [DONE] status=done rc=0\\n\\n   ← final event
    """
    job = _jq.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    @stream_with_context
    def generate():
        while True:
            try:
                line = job._q.get(timeout=30)
            except queue.Empty:
                yield "data: [KEEPALIVE]\n\n"
                continue
            if line is None:
                yield f"data: [DONE] status={job.status} rc={job.rc}\n\n"
                break
            yield f"data: {line.rstrip()}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.route("/api/jobs", methods=["GET"])
@require_api_key
def list_jobs():
    """List recent jobs with status."""
    limit = int(request.args.get("limit", 20))
    return jsonify({"jobs": _jq.list_recent(limit)})


# ══════════════════════════════════════════════════════════════════════════════
# Tool endpoints — all async, all auth-guarded, all rate-limited
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/tools/nmap", methods=["POST"])
@require_api_key
@rate_limit("nmap")
def nmap():
    p = request.json or {}
    target = sanitize(p.get("target", ""))
    if not target:
        return jsonify({"error": "target required"}), 400
    scan_type = sanitize(p.get("scan_type", "-sCV"))
    ports     = sanitize(p.get("ports", ""))
    extra     = sanitize(p.get("additional_args", "-T4 -Pn"))
    cmd = f"nmap {scan_type}"
    if ports:  cmd += f" -p {ports}"
    if extra:  cmd += f" {extra}"
    cmd += f" {target}"
    return _submit("nmap", cmd, timeout=1800)


@app.route("/api/tools/masscan", methods=["POST"])
@require_api_key
@rate_limit("masscan")
def masscan():
    p = request.json or {}
    target = sanitize(p.get("target", ""))
    if not target:
        return jsonify({"error": "target required"}), 400
    ports = sanitize(p.get("ports", "1-65535"))
    rate  = min(int(p.get("rate", 1000)), 10000)
    extra = sanitize(p.get("additional_args", ""))
    cmd = f"masscan {target} -p{ports} --rate={rate}"
    if extra: cmd += f" {extra}"
    return _submit("masscan", cmd, timeout=600)


@app.route("/api/tools/nikto", methods=["POST"])
@require_api_key
@rate_limit("nikto")
def nikto():
    p = request.json or {}
    target = sanitize(p.get("target", ""))
    if not target:
        return jsonify({"error": "target required"}), 400
    extra = sanitize(p.get("additional_args", ""))
    cmd = f"nikto -h {target}"
    if extra: cmd += f" {extra}"
    return _submit("nikto", cmd, timeout=900)


@app.route("/api/tools/whatweb", methods=["POST"])
@require_api_key
@rate_limit("default")
def whatweb():
    p = request.json or {}
    target = sanitize(p.get("target", ""))
    if not target:
        return jsonify({"error": "target required"}), 400
    agg   = min(int(p.get("aggression", 1)), 4)
    extra = sanitize(p.get("additional_args", ""))
    cmd = f"whatweb -a {agg} {target}"
    if extra: cmd += f" {extra}"
    return _submit("whatweb", cmd, timeout=120)


@app.route("/api/tools/gobuster", methods=["POST"])
@require_api_key
@rate_limit("default")
def gobuster():
    p = request.json or {}
    url = sanitize(p.get("url", ""))
    if not url:
        return jsonify({"error": "url required"}), 400
    mode = p.get("mode", "dir")
    if mode not in ("dir", "dns", "fuzz", "vhost"):
        return jsonify({"error": "invalid mode"}), 400
    wl    = sanitize(p.get("wordlist", "/usr/share/wordlists/dirb/common.txt"))
    extra = sanitize(p.get("additional_args", ""))
    cmd = f"gobuster {mode} -u {url} -w {wl}"
    if extra: cmd += f" {extra}"
    return _submit("gobuster", cmd, timeout=600)


@app.route("/api/tools/ffuf", methods=["POST"])
@require_api_key
@rate_limit("default")
def ffuf():
    p = request.json or {}
    url = sanitize(p.get("url", ""))
    if not url:
        return jsonify({"error": "url required"}), 400
    wl    = sanitize(p.get("wordlist", "/usr/share/wordlists/dirb/common.txt"))
    extra = sanitize(p.get("additional_args", ""))
    if "FUZZ" not in url:
        url += "/FUZZ" if url.endswith("/") else "/FUZZ"
    cmd = f"ffuf -u {url} -w {wl} -fc 404 -rate 100"
    if extra: cmd += f" {extra}"
    return _submit("ffuf", cmd, timeout=600)


@app.route("/api/tools/feroxbuster", methods=["POST"])
@require_api_key
@rate_limit("default")
def feroxbuster():
    p = request.json or {}
    url = sanitize(p.get("url", ""))
    if not url:
        return jsonify({"error": "url required"}), 400
    wl      = sanitize(p.get("wordlist", "/usr/share/wordlists/dirb/common.txt"))
    threads = min(int(p.get("threads", 50)), 200)
    extra   = sanitize(p.get("additional_args", ""))
    cmd = f"feroxbuster -u {url} -w {wl} -t {threads} -C 404"
    if extra: cmd += f" {extra}"
    return _submit("feroxbuster", cmd, timeout=600)


@app.route("/api/tools/sqlmap", methods=["POST"])
@require_api_key
@rate_limit("sqlmap")
def sqlmap():
    p = request.json or {}
    url = sanitize(p.get("url", ""))
    if not url:
        return jsonify({"error": "url required"}), 400
    data  = sanitize(p.get("data", ""))
    extra = sanitize(p.get("additional_args", ""))
    cmd = f"sqlmap -u {url} --batch"
    if data:  cmd += f' --data="{data}"'
    if extra: cmd += f" {extra}"
    return _submit("sqlmap", cmd, timeout=1800)


@app.route("/api/tools/nuclei", methods=["POST"])
@require_api_key
@rate_limit("nuclei")
def nuclei():
    p = request.json or {}
    target = sanitize(p.get("target", ""))
    if not target:
        return jsonify({"error": "target required"}), 400
    templates = sanitize(p.get("templates", ""))
    severity  = sanitize(p.get("severity", "critical,high,medium"))
    extra     = sanitize(p.get("additional_args", ""))
    cmd = f"nuclei -u {target} -severity {severity} -json -silent"
    if templates: cmd += f" -t {templates}"
    if extra:     cmd += f" {extra}"
    return _submit("nuclei", cmd, timeout=900)


@app.route("/api/tools/hydra", methods=["POST"])
@require_api_key
@rate_limit("hydra")
def hydra():
    p = request.json or {}
    target  = sanitize(p.get("target", ""))
    service = sanitize(p.get("service", ""))
    if not target or not service:
        return jsonify({"error": "target and service required"}), 400
    cmd = "hydra -t 4"
    u  = sanitize(p.get("username", ""))
    uf = sanitize(p.get("username_file", ""))
    pw = sanitize(p.get("password", ""))
    pf = sanitize(p.get("password_file", ""))
    if u:   cmd += f" -l {u}"
    elif uf: cmd += f" -L {uf}"
    if pw:  cmd += f" -p {pw}"
    elif pf: cmd += f" -P {pf}"
    cmd += f" {target} {service}"
    extra = sanitize(p.get("additional_args", ""))
    if extra: cmd += f" {extra}"
    return _submit("hydra", cmd, timeout=1800)


@app.route("/api/tools/wpscan", methods=["POST"])
@require_api_key
@rate_limit("default")
def wpscan():
    p = request.json or {}
    url = sanitize(p.get("url", ""))
    if not url:
        return jsonify({"error": "url required"}), 400
    extra = sanitize(p.get("additional_args", ""))
    cmd = f"wpscan --url {url}"
    if extra: cmd += f" {extra}"
    return _submit("wpscan", cmd, timeout=600)


@app.route("/api/tools/metasploit", methods=["POST"])
@require_api_key
@rate_limit("metasploit")
def metasploit():
    p = request.json or {}
    module  = sanitize(p.get("module", ""))
    options = p.get("options", {})
    if not module:
        return jsonify({"error": "module required"}), 400
    with tempfile.NamedTemporaryFile(mode="w", suffix=".rc", delete=False, dir="/tmp") as f:
        rc_path = f.name
        f.write(f"use {module}\n")
        for k, v in options.items():
            f.write(f"set {sanitize(str(k))} {sanitize(str(v))}\n")
        f.write("run\nexit\n")
    cmd = f"msfconsole -q -r {rc_path}; rm -f {rc_path}"
    return _submit("metasploit", cmd, timeout=1800)


@app.route("/api/tools/john", methods=["POST"])
@require_api_key
@rate_limit("default")
def john():
    p = request.json or {}
    hf = sanitize(p.get("hash_file", ""))
    if not hf:
        return jsonify({"error": "hash_file required"}), 400
    wl    = sanitize(p.get("wordlist", "/usr/share/wordlists/rockyou.txt"))
    fmt   = sanitize(p.get("format", ""))
    extra = sanitize(p.get("additional_args", ""))
    cmd = "john"
    if fmt:  cmd += f" --format={fmt}"
    cmd += f" --wordlist={wl}"
    if extra: cmd += f" {extra}"
    cmd += f" {hf}"
    return _submit("john", cmd, timeout=3600)


@app.route("/api/tools/hashcat", methods=["POST"])
@require_api_key
@rate_limit("default")
def hashcat():
    p = request.json or {}
    hf = sanitize(p.get("hash_file", ""))
    if not hf:
        return jsonify({"error": "hash_file required"}), 400
    wl    = sanitize(p.get("wordlist", "/usr/share/wordlists/rockyou.txt"))
    ht    = sanitize(p.get("hash_type", ""))
    mode  = int(p.get("attack_mode", 0))
    extra = sanitize(p.get("additional_args", ""))
    cmd = f"hashcat -a {mode}"
    if ht: cmd += f" -m {ht}"
    cmd += f" {hf} {wl}"
    if extra: cmd += f" {extra}"
    return _submit("hashcat", cmd, timeout=3600)


@app.route("/api/tools/enum4linux-ng", methods=["POST"])
@require_api_key
@rate_limit("default")
def enum4linux_ng():
    p = request.json or {}
    target = sanitize(p.get("target", ""))
    if not target:
        return jsonify({"error": "target required"}), 400
    extra = sanitize(p.get("additional_args", "-A"))
    cmd = f"enum4linux-ng {extra} {target}"
    return _submit("enum4linux-ng", cmd, timeout=600)


@app.route("/api/tools/amass", methods=["POST"])
@require_api_key
@rate_limit("default")
def amass():
    p = request.json or {}
    domain = sanitize(p.get("domain", ""))
    if not domain:
        return jsonify({"error": "domain required"}), 400
    mode = p.get("mode", "enum")
    if mode not in ("enum", "intel", "viz", "track", "db"):
        return jsonify({"error": "invalid mode"}), 400
    extra = sanitize(p.get("additional_args", ""))
    cmd = f"amass {mode} -d {domain}"
    if extra: cmd += f" {extra}"
    return _submit("amass", cmd, timeout=900)


@app.route("/api/tools/subfinder", methods=["POST"])
@require_api_key
@rate_limit("default")
def subfinder():
    p = request.json or {}
    domain = sanitize(p.get("domain", ""))
    if not domain:
        return jsonify({"error": "domain required"}), 400
    extra = sanitize(p.get("additional_args", "-silent"))
    cmd = f"subfinder -d {domain} {extra}"
    return _submit("subfinder", cmd, timeout=300)


@app.route("/api/tools/searchsploit", methods=["POST"])
@require_api_key
@rate_limit("default")
def searchsploit():
    p = request.json or {}
    query = sanitize(p.get("query", ""))
    if not query:
        return jsonify({"error": "query required"}), 400
    extra = sanitize(p.get("additional_args", ""))
    cmd = f"searchsploit {query}"
    if extra: cmd += f" {extra}"
    return _submit("searchsploit", cmd, timeout=60)


@app.route("/api/command", methods=["POST"])
@require_api_key
def generic_command():
    p = request.json or {}
    cmd = p.get("command", "")
    if not cmd:
        return jsonify({"error": "command required"}), 400
    return _submit("command", cmd, timeout=300)


# ══════════════════════════════════════════════════════════════════════════════
# Health + scan history
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health_check():
    tools = [
        "nmap", "masscan", "gobuster", "feroxbuster", "nikto", "sqlmap",
        "msfconsole", "hydra", "john", "wpscan", "enum4linux-ng", "ffuf",
        "amass", "hashcat", "nuclei", "subfinder", "searchsploit", "whatweb"
    ]
    status = {}
    for t in tools:
        try:
            r = subprocess.run(f"which {t}", shell=True, capture_output=True, timeout=3)
            status[t] = r.returncode == 0
        except Exception:
            status[t] = False
    return jsonify({
        "status": "healthy",
        "tools_status": status,
        "all_essential_tools_available": all(status.values()),
        "async_mode": True,
        "max_concurrent_jobs": MAX_WORKERS,
        "active_jobs": sum(1 for j in _jq._jobs.values() if j.status == "running"),
    })


@app.route("/api/scans/history", methods=["GET"])
@require_api_key
def scan_history():
    limit = int(request.args.get("limit", 20))
    return jsonify({"scans": _jq.list_recent(limit), "total": len(_jq._jobs)})


@app.route("/api/scans/<scan_id>", methods=["GET"])
@require_api_key
def get_scan(scan_id: str):
    job = _jq.get(scan_id)
    if job:
        return jsonify(job.to_dict())
    path = os.path.join(SCAN_LOG_DIR, f"{scan_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            return jsonify(json.load(f))
    return jsonify({"error": "Scan not found"}), 404


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kali Tools API Server (async)")
    parser.add_argument("--ip",    default="0.0.0.0",
                        help="Bind IP (default: 0.0.0.0 — all interfaces)")
    parser.add_argument("--port",  type=int, default=API_PORT)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    bind_ip = args.ip
    port    = args.port

    # Detect the real outbound network IP — avoids 127.0.1.1 loopback alias
    import socket as _sock
    try:
        s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))          # doesn't send traffic, just routes
        real_ip = s.getsockname()[0]
        s.close()
    except Exception:
        real_ip = "127.0.0.1"

    logger.info(f"Starting async Kali API on {bind_ip}:{port}")
    logger.info(f"Max concurrent jobs: {MAX_WORKERS} | Output cap: {MAX_OUTPUT//1024//1024} MB")

    print(f"\n{'='*55}")
    print(f"  Kali Pentest API — RUNNING")
    print(f"{'='*55}")
    print(f"  Local   : http://127.0.0.1:{port}")
    print(f"  Network : http://{real_ip}:{port}")
    print(f"  API Key : {API_KEY}")
    print(f"  Jobs    : max {MAX_WORKERS} concurrent | {MAX_OUTPUT//1024//1024} MB cap")
    print(f"  Debug   : {args.debug}")
    print(f"{'='*55}")
    print(f"\n  Use this in claude_mcp_config.json:")
    print(f"  \"--server\", \"http://{real_ip}:{port}\"")
    print(f"{'='*55}\n")

    # use_reloader=False stops double-startup and keeps logs clean
    app.run(host=bind_ip, port=port, debug=args.debug,
            threaded=True, use_reloader=False)