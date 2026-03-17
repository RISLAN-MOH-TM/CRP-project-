# System Workflow - Automated Penetration Testing System

## Overview

This document provides a complete end-to-end workflow of how the automated penetration testing system operates, from user input to final report generation.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERACTION                            │
│                                                                     │
│  User: "Scan http://testphp.vulnweb.com and generate a report"    │
│                              ↓                                      │
│                    ┌─────────────────┐                             │
│                    │  Claude Desktop │                             │
│                    │   (AI Client)   │                             │
│                    └────────┬────────┘                             │
└─────────────────────────────┼──────────────────────────────────────┘
                              │ MCP Protocol
                              │ (stdio/JSON-RPC)
┌─────────────────────────────▼──────────────────────────────────────┐
│                      WINDOWS HOST (MCP Server)                      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  mcp_server.py - Model Context Protocol Server               │  │
│  │  • 30+ MCP tools exposed to Claude                           │  │
│  │  • Kali API client (HTTP requests)                           │  │
│  │  • CVE RAG engine integration                                │  │
│  │  • Result persistence (results/raw/*.json)                   │  │
│  └──────────────┬───────────────────────────┬───────────────────┘  │
│                 │                           │                       │
│                 │ HTTP REST                 │ Local                 │
│                 │ (Port 5000)               │ Function Call         │
│                 │                           │                       │
│  ┌──────────────▼──────────┐   ┌───────────▼──────────────────┐   │
│  │  Kali API Client        │   │  CVE RAG Engine (rag.py)     │   │
│  │  • POST /api/tools/*    │   │  • Vector search (ChromaDB)  │   │
│  │  • GET /api/jobs/*      │   │  • 320k CVEs                 │   │
│  │  • Job polling          │   │  • Lazy model loading        │   │
│  └─────────────────────────┘   └──────────────────────────────┘   │
└─────────────────┼──────────────────────────────────────────────────┘
                  │ HTTP REST API
                  │ (Network: 192.168.x.x:5000)
┌─────────────────▼──────────────────────────────────────────────────┐
│                    KALI LINUX VM (Tool Execution)                   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  kali_server.py - Flask API Server                           │  │
│  │  • Async job queue (5 concurrent max)                        │  │
│  │  • Rate limiting (token bucket)                              │  │
│  │  • SSE streaming (/api/jobs/<id>/stream)                     │  │
│  │  • API key authentication                                    │  │
│  └──────────────┬───────────────────────────────────────────────┘  │
│                 │                                                   │
│                 │ subprocess.Popen()                                │
│                 │                                                   │
│  ┌──────────────▼───────────────────────────────────────────────┐  │
│  │  Security Tools (18+ Kali Linux tools)                       │  │
│  │  nmap | nikto | sqlmap | gobuster | nuclei | hydra | ...    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---


## Detailed Workflow: Complete Penetration Test

### Phase 1: Initialization & Connection

```
┌──────────────┐
│ User starts  │
│ Claude       │
│ Desktop      │
└──────┬───────┘
       │
       │ 1. Load MCP config (claude_mcp_config.json)
       │
       ▼
┌──────────────────────────────────────────┐
│ Spawn mcp_server.py process              │
│ • Parse --server arg (Kali IP)           │
│ • Load KALI_API_KEY from env             │
│ • Initialize KaliClient (no health check)│
│ • Register 30+ MCP tools                 │
│ • Ready in <1 second                     │
└──────┬───────────────────────────────────┘
       │
       │ 2. MCP handshake (stdio JSON-RPC)
       │
       ▼
┌──────────────────────────────────────────┐
│ Claude Desktop connected                 │
│ • MCP tools available                    │
│ • User can send messages                 │
└──────────────────────────────────────────┘
```

**Key Points:**
- No blocking operations on startup
- Kali connection is lazy (happens on first tool call)
- RAG model loads on first CVE search

---

### Phase 2: User Request Processing

```
User Input: "Scan http://testphp.vulnweb.com and generate a report"
       │
       ▼
┌──────────────────────────────────────────┐
│ Claude AI analyzes request               │
│ • Identifies target URL                  │
│ • Plans tool execution sequence          │
│ • Decides: recon → scan → exploit → CVE │
└──────┬───────────────────────────────────┘
       │
       │ 3. Call MCP tool: server_health()
       │
       ▼
┌──────────────────────────────────────────┐
│ mcp_server.py: server_health()           │
│ • GET http://192.168.x.x:5000/health     │
│ • 5 second timeout                       │
│ • Returns tool availability              │
└──────┬───────────────────────────────────┘
       │
       │ 4. Health check response
       │
       ▼
┌──────────────────────────────────────────┐
│ Claude receives Kali status              │
│ • All tools available: ✓                 │
│ • Proceeds with scan plan                │
└──────────────────────────────────────────┘
```

---

### Phase 3: Reconnaissance

```
┌──────────────────────────────────────────┐
│ Claude: Call whatweb_scan()              │
│ target="http://testphp.vulnweb.com"      │
└──────┬───────────────────────────────────┘
       │
       │ 5. MCP tool invocation
       │
       ▼
┌──────────────────────────────────────────┐
│ mcp_server.py: whatweb_scan()            │
│ • POST /api/tools/whatweb                │
│ • Body: {"target": "http://..."}         │
│ • Headers: X-API-Key                     │
└──────┬───────────────────────────────────┘
       │
       │ 6. HTTP request to Kali
       │
       ▼
┌──────────────────────────────────────────┐
│ kali_server.py: /api/tools/whatweb       │
│ • Validate API key                       │
│ • Check rate limit (token bucket)        │
│ • Create Job object (UUID)               │
│ • Return 202 Accepted + job_id           │
└──────┬───────────────────────────────────┘
       │
       │ 7. Job queued (HTTP 202)
       │
       ▼
┌──────────────────────────────────────────┐
│ mcp_server.py: wait_for_job()            │
│ • Poll GET /api/jobs/<job_id>            │
│ • Every 5 seconds                        │
│ • Until status = "done" or "failed"      │
└──────┬───────────────────────────────────┘
       │
       │ (Meanwhile on Kali...)
       │
       ▼
┌──────────────────────────────────────────┐
│ kali_server.py: JobQueue._run()          │
│ • Acquire semaphore (max 5 concurrent)   │
│ • subprocess.Popen("whatweb ...")        │
│ • Stream stdout line-by-line             │
│ • Apply 10 MB output cap                 │
│ • Set status = "done"                    │
│ • Persist to /opt/scans/logs/*.json      │
└──────┬───────────────────────────────────┘
       │
       │ 8. Job complete
       │
       ▼
┌──────────────────────────────────────────┐
│ mcp_server.py receives result            │
│ • stdout: WhatWeb output                 │
│ • Parse: Apache 2.4.7, PHP 5.5.9         │
│ • Save to results/raw/whatweb_*.json     │
│ • Return formatted string to Claude      │
└──────┬───────────────────────────────────┘
       │
       │ 9. Result to Claude
       │
       ▼
┌──────────────────────────────────────────┐
│ Claude analyzes WhatWeb output           │
│ • Detected: Apache 2.4.7, PHP 5.5.9      │
│ • Decision: Run nmap for ports           │
└──────────────────────────────────────────┘
```

---


### Phase 4: Vulnerability Scanning

```
┌──────────────────────────────────────────┐
│ Claude: Call nmap_scan()                 │
│ target="testphp.vulnweb.com"             │
│ scan_type="-sCV"                         │
│ ports="22,80,443,8080"                   │
└──────┬───────────────────────────────────┘
       │
       │ (Same async job flow as Phase 3)
       │
       ▼
┌──────────────────────────────────────────┐
│ Nmap scan completes                      │
│ • Open ports: 80/tcp, 443/tcp            │
│ • Services: Apache httpd 2.4.7           │
│ • OS: Linux 3.x                          │
└──────┬───────────────────────────────────┘
       │
       │ 10. Parallel tool execution
       │
       ├─────────────────┬─────────────────┬──────────────────┐
       │                 │                 │                  │
       ▼                 ▼                 ▼                  ▼
┌──────────┐    ┌──────────┐    ┌──────────┐      ┌──────────┐
│  nikto   │    │  nuclei  │    │ gobuster │      │  sqlmap  │
│  scan    │    │  scan    │    │  scan    │      │  scan    │
└──────┬───┘    └──────┬───┘    └──────┬───┘      └──────┬───┘
       │               │               │                  │
       │ (All jobs queued on Kali, max 5 concurrent)     │
       │               │               │                  │
       └───────────────┴───────────────┴──────────────────┘
                              │
                              │ 11. All scans complete
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ Claude receives all results                              │
│ • Nikto: 12 vulnerabilities found                        │
│ • Nuclei: CVE-2021-41773 (Apache path traversal)         │
│ • Gobuster: /admin, /backup, /config.php                 │
│ • SQLmap: SQL injection in artists.php?artist=1          │
└──────┬───────────────────────────────────────────────────┘
       │
       │ 12. Decision: Enrich with CVE data
       │
       ▼
```

---

### Phase 5: CVE Intelligence Enrichment

```
┌──────────────────────────────────────────┐
│ Claude: Call cve_enrich_services()       │
│ services="apache 2.4.7, php 5.5.9"       │
│ limit_per=5                              │
└──────┬───────────────────────────────────┘
       │
       │ 13. Local RAG query (no network call)
       │
       ▼
┌──────────────────────────────────────────┐
│ mcp_server.py: cve_enrich_services()     │
│ • Call _init_rag() (lazy load)           │
│ • _rag.batch_search(["apache 2.4.7", ...])│
└──────┬───────────────────────────────────┘
       │
       │ 14. First CVE search triggers model load
       │
       ▼
┌──────────────────────────────────────────┐
│ rag.py: RAGEngine.search()               │
│ • _ensure_model() loads SentenceTransformer│
│ • Takes 2-3 seconds (one-time)           │
│ • Model cached in memory                 │
└──────┬───────────────────────────────────┘
       │
       │ 15. Vector search
       │
       ▼
┌──────────────────────────────────────────┐
│ rag.py: Vector search flow               │
│ 1. Expand aliases: "apache" →            │
│    ["apache", "httpd", "apache_http_..."]│
│ 2. Encode query with all-MiniLM-L6-v2    │
│ 3. ChromaDB HNSW search (top 50)         │
│ 4. Fetch metadata from SQLite            │
│ 5. Boost by CVSS score                   │
│ 6. Return top 5 results                  │
└──────┬───────────────────────────────────┘
       │
       │ 16. CVE results (<10ms)
       │
       ▼
┌──────────────────────────────────────────┐
│ Results returned to Claude               │
│ • CVE-2021-41773 (CRITICAL, CVSS 9.8)    │
│ • CVE-2021-42013 (CRITICAL, CVSS 9.8)    │
│ • CVE-2017-15715 (HIGH, CVSS 8.1)        │
│ • CVE-2019-0211 (HIGH, CVSS 7.8)         │
│ • CVE-2017-9798 (MEDIUM, CVSS 5.9)       │
└──────┬───────────────────────────────────┘
       │
       │ 17. Repeat for PHP 5.5.9
       │
       ▼
┌──────────────────────────────────────────┐
│ Claude has complete CVE context          │
│ • 10 CVEs for Apache 2.4.7               │
│ • 8 CVEs for PHP 5.5.9                   │
│ • Ready to generate report               │
└──────────────────────────────────────────┘
```

---


### Phase 6: Report Generation

```
┌──────────────────────────────────────────┐
│ Claude: Analyze all findings             │
│ • Correlate scan results                 │
│ • Calculate CVSS scores                  │
│ • Generate risk narratives               │
│ • Create mitigation strategies           │
└──────┬───────────────────────────────────┘
       │
       │ 18. Generate HTML report
       │
       ▼
┌──────────────────────────────────────────┐
│ Claude: Create HTML structure            │
│ • Header with metadata                   │
│ • Executive summary                      │
│ • Findings (severity-coded)              │
│ • CVE intelligence sections              │
│ • Mitigations (24h/1week/1month)         │
│ • Embedded CSS (no external files)       │
└──────┬───────────────────────────────────┘
       │
       │ 19. Save report
       │
       ▼
┌──────────────────────────────────────────┐
│ mcp_server.py: Save HTML file            │
│ • Path: results/reports/                 │
│ • Filename: pentest_testphp_20260317.html│
│ • Return success message                 │
└──────┬───────────────────────────────────┘
       │
       │ 20. Report complete
       │
       ▼
┌──────────────────────────────────────────┐
│ Claude: Display summary to user          │
│ • Total findings: 15                     │
│ • Critical: 2, High: 5, Medium: 6, Low: 2│
│ • Report saved: results/reports/...      │
│ • Instructions: Open in browser, Ctrl+P  │
└──────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW                                   │
└─────────────────────────────────────────────────────────────────────┘

User Input (Natural Language)
       │
       ▼
┌──────────────────────────────────────────┐
│ Claude AI (LLM)                          │
│ • Intent recognition                     │
│ • Tool selection                         │
│ • Parameter extraction                   │
└──────┬───────────────────────────────────┘
       │
       │ MCP Tool Call (JSON-RPC)
       │ {"method": "tools/call", "params": {...}}
       │
       ▼
┌──────────────────────────────────────────┐
│ mcp_server.py (Python)                   │
│ • Validate parameters                    │
│ • Route to handler function              │
└──────┬───────────────────────────────────┘
       │
       ├─────────────────┬─────────────────┐
       │                 │                 │
       │ HTTP REST       │ Local           │
       │                 │ Function        │
       ▼                 ▼                 │
┌──────────┐    ┌──────────────┐          │
│  Kali    │    │  CVE RAG     │          │
│  Server  │    │  Engine      │          │
└──────┬───┘    └──────┬───────┘          │
       │               │                  │
       │ Tool Output   │ CVE Data         │
       │ (JSON)        │ (JSON)           │
       │               │                  │
       └───────────────┴──────────────────┘
                       │
                       │ Formatted Result (String)
                       │
                       ▼
┌──────────────────────────────────────────┐
│ Claude AI receives result                │
│ • Parse structured data                  │
│ • Continue workflow                      │
│ • Generate response                      │
└──────┬───────────────────────────────────┘
       │
       │ Natural Language Response
       │
       ▼
┌──────────────────────────────────────────┐
│ User sees formatted output               │
│ • Scan results                           │
│ • CVE intelligence                       │
│ • Report generation status               │
└──────────────────────────────────────────┘
```

---


## Async Job Queue Flow (Kali Server)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    KALI SERVER JOB QUEUE                            │
└─────────────────────────────────────────────────────────────────────┘

HTTP POST /api/tools/nmap
       │
       │ 1. API key validation
       │
       ▼
┌──────────────────────────────────────────┐
│ Rate limiter check (token bucket)        │
│ • nmap: 3 burst, 1 per 20s               │
│ • If exhausted: return HTTP 429          │
└──────┬───────────────────────────────────┘
       │
       │ 2. Token consumed
       │
       ▼
┌──────────────────────────────────────────┐
│ Create Job object                        │
│ • job_id: UUID                           │
│ • tool: "nmap"                           │
│ • command: "nmap -sCV ..."               │
│ • status: "queued"                       │
│ • timeout: 1800s                         │
└──────┬───────────────────────────────────┘
       │
       │ 3. Return HTTP 202 Accepted
       │    {"job_id": "abc123...", "status": "queued"}
       │
       ▼
┌──────────────────────────────────────────┐
│ Background thread spawned                │
│ • Acquire semaphore (max 5 concurrent)   │
│ • Wait if 5 jobs already running         │
└──────┬───────────────────────────────────┘
       │
       │ 4. Semaphore acquired
       │
       ▼
┌──────────────────────────────────────────┐
│ Job status: "running"                    │
│ • subprocess.Popen(command, shell=True)  │
│ • stdout=PIPE, stderr=PIPE               │
└──────┬───────────────────────────────────┘
       │
       │ 5. Stream output line-by-line
       │
       ▼
┌──────────────────────────────────────────┐
│ Output processing                        │
│ • Read stdout line by line               │
│ • Append to job.stdout buffer            │
│ • Push to SSE queue (live streaming)     │
│ • Check 10 MB cap                        │
│ • Check timeout (1800s)                  │
└──────┬───────────────────────────────────┘
       │
       │ 6. Process completes or times out
       │
       ▼
┌──────────────────────────────────────────┐
│ Job finalization                         │
│ • status: "done" or "failed"             │
│ • return_code: 0 or -1                   │
│ • finished: timestamp                    │
│ • Release semaphore                      │
│ • Persist to /opt/scans/logs/*.json      │
└──────┬───────────────────────────────────┘
       │
       │ 7. Job available for polling
       │
       ▼
┌──────────────────────────────────────────┐
│ GET /api/jobs/<job_id>                   │
│ • Returns full job object                │
│ • stdout, stderr, return_code            │
└──────────────────────────────────────────┘
```

---

## CVE RAG Search Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CVE RAG SEARCH FLOW                              │
└─────────────────────────────────────────────────────────────────────┘

User query: "apache 2.4.7 vulnerabilities"
       │
       ▼
┌──────────────────────────────────────────┐
│ rag.py: RAGEngine.search()               │
│ • Check if model loaded                  │
│ • If not: _ensure_model() (2-3s)         │
└──────┬───────────────────────────────────┘
       │
       │ 1. Alias expansion
       │
       ▼
┌──────────────────────────────────────────┐
│ resolve_aliases("apache 2.4.7")          │
│ • Input: ["apache", "2.4.7"]             │
│ • Expand: ["apache", "httpd",            │
│            "apache_http_server", "2.4.7"]│
│ • Output: "apache httpd apache_http_...  │
│           server 2.4.7"                  │
└──────┬───────────────────────────────────┘
       │
       │ 2. Encode query
       │
       ▼
┌──────────────────────────────────────────┐
│ SentenceTransformer.encode()             │
│ • Model: all-MiniLM-L6-v2                │
│ • Input: expanded query string           │
│ • Output: 384-dim vector                 │
│ • Time: ~5ms                             │
└──────┬───────────────────────────────────┘
       │
       │ 3. Vector search
       │
       ▼
┌──────────────────────────────────────────┐
│ ChromaDB.query()                         │
│ • HNSW index search                      │
│ • Cosine similarity                      │
│ • Top 50 results                         │
│ • Time: ~5ms                             │
└──────┬───────────────────────────────────┘
       │
       │ 4. Fetch metadata
       │
       ▼
┌──────────────────────────────────────────┐
│ SQLite queries (batch)                   │
│ • SELECT * FROM cves WHERE cve_id IN (...)│
│ • Deserialize JSON fields                │
│ • Time: ~2ms                             │
└──────┬───────────────────────────────────┘
       │
       │ 5. CVSS boosting
       │
       ▼
┌──────────────────────────────────────────┐
│ Score adjustment                         │
│ • score = vector_score + (cvss/10)*0.1   │
│ • Sort by adjusted score DESC            │
│ • Return top 20                          │
└──────┬───────────────────────────────────┘
       │
       │ 6. Format results
       │
       ▼
┌──────────────────────────────────────────┐
│ Results returned                         │
│ • CVE-2021-41773 (CRITICAL, CVSS 9.8)    │
│ • CVE-2021-42013 (CRITICAL, CVSS 9.8)    │
│ • CVE-2017-15715 (HIGH, CVSS 8.1)        │
│ • ...                                    │
│ • Total time: <10ms                      │
└──────────────────────────────────────────┘
```

---


## Error Handling & Recovery

### Scenario 1: Kali Server Unreachable

```
Claude calls nmap_scan()
       │
       ▼
mcp_server.py: POST http://192.168.x.x:5000/api/tools/nmap
       │
       │ Connection timeout (30s)
       │
       ▼
┌──────────────────────────────────────────┐
│ Error returned to Claude                 │
│ {"error": "Cannot connect to Kali..."}   │
└──────┬───────────────────────────────────┘
       │
       ▼
Claude: "Kali server is unreachable. Please check:
         1. Is kali_server.py running?
         2. Is the IP correct in .env?
         3. Can you ping the Kali machine?"
```

### Scenario 2: Tool Times Out

```
Nmap scan running for 30 minutes (timeout: 1800s)
       │
       ▼
┌──────────────────────────────────────────┐
│ kali_server.py: Timeout reached          │
│ • proc.terminate()                       │
│ • job.timed_out = True                   │
│ • job.status = "done"                    │
│ • Partial stdout saved                   │
└──────┬───────────────────────────────────┘
       │
       ▼
Claude receives partial results
       │
       ▼
Claude: "Nmap scan timed out after 30 minutes.
         Partial results available. Consider:
         - Reducing port range
         - Using faster scan (-T4)
         - Splitting into multiple scans"
```

### Scenario 3: Rate Limit Exceeded

```
User: "Scan 10 targets with nmap"
       │
       ▼
Claude calls nmap_scan() 10 times rapidly
       │
       │ First 3 succeed (burst capacity)
       │ 4th request hits rate limit
       │
       ▼
┌──────────────────────────────────────────┐
│ kali_server.py: HTTP 429 Too Many Requests│
│ {"error": "Rate limit exceeded",         │
│  "retry_after": "30s"}                   │
└──────┬───────────────────────────────────┘
       │
       ▼
Claude: "Rate limit reached for nmap.
         Waiting 30 seconds before retrying..."
       │
       │ (Wait 30s)
       │
       ▼
Retry remaining scans
```

### Scenario 4: CVE Database Not Built

```
Claude calls cve_search("apache rce")
       │
       ▼
mcp_server.py: _init_rag()
       │
       ▼
rag.py: RAGEngine.__init__()
       │
       │ Check if cve_rag.db exists
       │ Check if cve_chroma/ exists
       │
       ▼
┌──────────────────────────────────────────┐
│ Database not found                       │
│ _rag.ready = False                       │
└──────┬───────────────────────────────────┘
       │
       ▼
_rag_check() returns error string
       │
       ▼
Claude: "CVE database not built.
         Run: python rag.py --build-vectors
         This will take 20-40 minutes."
```

---

## Performance Characteristics

### Latency Breakdown (Typical Scan)

| Operation | Time | Notes |
|-----------|------|-------|
| MCP server startup | <1s | No blocking operations |
| First CVE search | 2-3s | One-time model load |
| Subsequent CVE searches | <10ms | Model cached |
| Kali health check | <100ms | 5s timeout |
| Tool submission (HTTP POST) | <50ms | Returns job_id immediately |
| Job polling interval | 5s | Configurable |
| Nmap scan (typical) | 2-5 min | Depends on target |
| Nikto scan | 5-10 min | Full web scan |
| SQLmap scan | 10-30 min | Depends on injection points |
| Report generation | <5s | HTML creation |

### Throughput Limits

| Resource | Limit | Reason |
|----------|-------|--------|
| Concurrent Kali jobs | 5 | Semaphore in JobQueue |
| Nmap rate limit | 1 per 20s | Token bucket |
| Masscan rate limit | 1 per 30s | Token bucket |
| Metasploit rate limit | 1 per 60s | Token bucket |
| Tool output cap | 10 MB | Prevents OOM |
| Context window | 80k tokens | Claude limit |

---


## State Management

### Job State Transitions (Kali Server)

```
┌─────────┐
│ queued  │ ← Initial state when job created
└────┬────┘
     │
     │ Semaphore acquired
     │
     ▼
┌─────────┐
│ running │ ← Tool executing
└────┬────┘
     │
     ├─────────────┬──────────────┐
     │             │              │
     │ Success     │ Timeout      │ Error
     │             │              │
     ▼             ▼              ▼
┌─────────┐   ┌─────────┐   ┌─────────┐
│  done   │   │  done   │   │ failed  │
│ rc=0    │   │ timeout │   │ rc!=0   │
└─────────┘   └─────────┘   └─────────┘
```

### RAG Engine State

```
┌──────────────────┐
│ Not initialized  │ ← Before first CVE search
└────────┬─────────┘
         │
         │ First cve_search() call
         │
         ▼
┌──────────────────┐
│ Loading model    │ ← 2-3 seconds
└────────┬─────────┘
         │
         │ Model loaded
         │
         ▼
┌──────────────────┐
│ Ready            │ ← All subsequent searches <10ms
└──────────────────┘
```

### MCP Connection State

```
┌──────────────────┐
│ Disconnected     │ ← Claude Desktop closed
└────────┬─────────┘
         │
         │ User opens Claude Desktop
         │
         ▼
┌──────────────────┐
│ Spawning         │ ← mcp_server.py starting
└────────┬─────────┘
         │
         │ <1 second
         │
         ▼
┌──────────────────┐
│ Connected        │ ← Ready for tool calls
└────────┬─────────┘
         │
         │ User closes Claude Desktop
         │
         ▼
┌──────────────────┐
│ Disconnected     │ ← Process terminated
└──────────────────┘
```

---

## File System Layout

```
automated-pentest-system/
│
├── Windows Host (MCP Server)
│   ├── mcp_server.py          ← MCP protocol server
│   ├── rag.py                 ← CVE RAG engine
│   ├── .env                   ← Configuration
│   ├── requirements.txt       ← Python dependencies
│   │
│   ├── cves/                  ← CVE JSON files (337k files)
│   │   ├── 1999/
│   │   ├── 2000/
│   │   └── ... (through 2026)
│   │
│   ├── cve_rag.db             ← SQLite metadata (267 MB)
│   │
│   ├── cve_chroma/            ← ChromaDB vector store (1.3 GB)
│   │   ├── chroma.sqlite3
│   │   └── [HNSW index files]
│   │
│   └── results/
│       ├── raw/               ← Tool JSON outputs
│       │   ├── nmap_testphp_20260317_143022.json
│       │   ├── nikto_testphp_20260317_143145.json
│       │   └── ...
│       │
│       └── reports/           ← Generated HTML reports
│           └── pentest_testphp_20260317.html
│
└── Kali Linux VM (Tool Execution)
    ├── kali_server.py         ← Flask API server
    │
    └── /opt/scans/logs/       ← Job persistence
        ├── abc123-uuid.json   ← Job metadata + output
        └── ...
```

---

## Security Considerations

### Authentication Flow

```
┌──────────────────────────────────────────┐
│ Every HTTP request to Kali               │
└──────┬───────────────────────────────────┘
       │
       │ Header: X-API-Key: kali-research-project-2026
       │
       ▼
┌──────────────────────────────────────────┐
│ kali_server.py: @require_api_key         │
│ • Compare header with API_KEY env var    │
│ • If mismatch: HTTP 401 Unauthorized     │
│ • If match: proceed to handler           │
└──────────────────────────────────────────┘
```

### Input Sanitization

```
User input: target="example.com; rm -rf /"
       │
       ▼
┌──────────────────────────────────────────┐
│ kali_server.py: sanitize()               │
│ • Strip: ; & | ` $ ( ) < > \n \r         │
│ • Output: "example.com rm -rf "          │
└──────┬───────────────────────────────────┘
       │
       ▼
Command: "nmap example.com rm -rf "
       │
       │ (Shell injection prevented)
       │
       ▼
Nmap fails gracefully (invalid target)
```

### Network Isolation

```
┌─────────────────────────────────────────────────────────────┐
│                    Network Topology                         │
└─────────────────────────────────────────────────────────────┘

Internet
    │
    │ (Firewall)
    │
    ▼
┌─────────────────────────────────────────┐
│ Local Network (192.168.x.x/24)          │
│                                         │
│  ┌──────────────┐    ┌──────────────┐  │
│  │ Windows Host │◄──►│  Kali Linux  │  │
│  │ 192.168.x.10 │    │ 192.168.x.11 │  │
│  └──────────────┘    └──────────────┘  │
│         │                    │          │
│         │                    │          │
│         │ Port 5000          │          │
│         │ (API only)         │          │
│         │                    │          │
│         └────────────────────┘          │
│                                         │
└─────────────────────────────────────────┘

Recommendations:
• Keep Kali on isolated network segment
• Use firewall rules to restrict port 5000 to Windows host only
• Never expose Kali API to internet
• Use VPN if Windows and Kali are on different networks
```

---

## Troubleshooting Decision Tree

```
Problem: "Taking longer than usual" on Claude Desktop startup
       │
       ▼
Is mcp_server.py blocking on startup?
       │
       ├─ YES → Check:
       │        • Kali health check removed? (should be lazy)
       │        • RAG model loading removed? (should be lazy)
       │        • Any other blocking network calls?
       │
       └─ NO → Check:
                • Is Python process hanging?
                • Check Claude Desktop logs
                • Restart Claude Desktop
```

```
Problem: CVE search returns "not found"
       │
       ▼
Is cve_rag.db present?
       │
       ├─ NO → Run: python rag.py --build-vectors
       │
       └─ YES → Is cve_chroma/ directory present?
                │
                ├─ NO → Run: python rag.py --build-vectors
                │
                └─ YES → Check:
                         • Is query too specific?
                         • Try broader terms
                         • Check stats: python rag.py --stats
```

```
Problem: Kali tools not executing
       │
       ▼
Can you reach Kali server?
       │
       ├─ NO → Check:
       │        • Is kali_server.py running?
       │        • Ping Kali IP from Windows
       │        • Check firewall rules
       │        • Verify .env KALI_SERVER_URL
       │
       └─ YES → Check:
                • API key correct in .env?
                • Tool installed on Kali? (which nmap)
                • Check Kali server logs
                • Try: curl http://KALI_IP:5000/health
```

---

## Summary

This system workflow demonstrates:

1. **Lazy initialization** — No blocking on startup
2. **Async execution** — Tools run in background, non-blocking
3. **Real-time intelligence** — CVE enrichment during scan
4. **Graceful degradation** — Continues even if some tools fail
5. **Professional output** — Structured HTML reports

**Total time from user input to report**: 20-30 minutes for comprehensive scan.

**Key optimization**: MCP server starts in <1 second, enabling instant Claude Desktop connection.
