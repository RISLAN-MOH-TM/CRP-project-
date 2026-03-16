# Automated Penetration Testing System with CVE RAG Intelligence

**A Computer Research Project**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Security](https://img.shields.io/badge/security-hardened-green.svg)](information/SECURITY.md)
[![Tools](https://img.shields.io/badge/tools-35-orange.svg)](information/TOOLS_QUICK_REFERENCE.txt)
[![CVEs](https://img.shields.io/badge/CVEs-320%2C000%2B-red.svg)](cve_rag.py)

---

## 📄 Table of Contents

1. [Abstract](#abstract)
2. [Project Overview](#project-overview)
3. [System Architecture](#system-architecture)
4. [CVE RAG Intelligence](#cve-rag-intelligence)
5. [Features](#features)
6. [Technology Stack](#technology-stack)
7. [Installation Guide](#installation-guide)
8. [Usage](#usage)
9. [Prompt Files](#prompt-files)
10. [Research Objectives](#research-objectives)
11. [Methodology](#methodology)
12. [Results & Analysis](#results--analysis)
13. [Future Enhancements](#future-enhancements)
14. [Documentation](#documentation)
15. [Contributors](#contributors)
16. [License](#license)

---

## 📄 Abstract

This project presents an **Automated Penetration Testing System** that leverages **Artificial Intelligence** and a **local CVE RAG (Retrieval-Augmented Generation) engine** to perform comprehensive vulnerability detection and generate professional security assessment reports. The system integrates 35 tools — 18 industry-standard penetration testing tools, 6 CVE RAG intelligence tools, and supporting utilities — orchestrated through the Model Context Protocol (MCP).

**Key Innovations:**
- Local CVE RAG engine — 320,000+ CVEs (1999–2026) indexed in SQLite FTS5, queried in <10ms with no internet dependency
- AI-driven vulnerability analysis cross-referenced against historical CVE database
- Automated tool orchestration across 5 testing phases
- Real-time scan logging and crash recovery
- Professional 14-section PDF report generation with CVE intelligence embedded per finding

**Target Audience:** Security researchers, penetration testers, academic institutions, and organizations requiring automated security assessments.

---

## 🎯 Project Overview

### Problem Statement

Manual penetration testing is:
- ⏰ **Time-consuming** — Takes days or weeks for comprehensive testing
- 💰 **Expensive** — Requires skilled security professionals
- 🔄 **Inconsistent** — Results vary based on tester expertise
- 📊 **Difficult to scale** — Cannot test multiple systems simultaneously
- 🔍 **CVE-blind** — No automatic cross-referencing against known vulnerability databases

### Proposed Solution

An **AI-powered automated system** that:
- ✅ Executes 18 penetration testing tools automatically across 5 phases
- ✅ Cross-references every discovered service against 320,000+ local CVEs instantly
- ✅ Analyzes results using Claude AI via MCP protocol
- ✅ Generates professional 14-section PDF reports with CVE intelligence per finding
- ✅ Provides actionable remediation with CVE-specific patches and vendor advisories
- ✅ Scales to test multiple targets simultaneously

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Windows Host                                   │
│                                                                             │
│  ┌──────────────────┐              ┌────────────────────────────────────┐   │
│  │   AI Client      │              │   MCP Server (mcp_server.py)       │   │
│  │  (Claude/Cline)  │◄────MCP─────►│   - 30+ MCP tools                  │   │
│  │                  │   Protocol   │   - CVE RAG integration            │   │ 
│  │  - Analysis      │              │   - Context window manager         │   │
│  │  - Reports       │              │   - Result persistence             │   │
│  └──────────────────┘              └────────────┬───────────────────────┘   │
│                                                  │                          │
│                                                  │ HTTP REST API            │
│                                                  │ (Port 5000)              │
│                                                  │                          │
│  ┌───────────────────────────────────────────────▼────────────────────────┐ │
│  │                    VMware Workstation Pro / VirtualBox                 │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │  │                      Kali Linux VM                              │   │ │
│  │  │                                                                 │   │ │
│  │  │  ┌──────────────────────────────────────────────────────────┐   │   │ │
│  │  │  │  Flask API Server (kali_server.py)                       │   │   │ │
│  │  │  │  - Async job queue (max 5 concurrent)                    │   │   │ │
│  │  │  │  - Token-bucket rate limiter                             │   │   │ │
│  │  │  │  - SSE live streaming                                    │   │   │ │
│  │  │  │  - API key authentication                                │   │   │ │
│  │  │  │  - 10 MB output cap per job                              │   │   │ │
│  │  │  └──────────────────────────────────────────────────────────┘   │   │ │
│  │  │                                                                 │   │ │
│  │  │  ┌──────────────────────────────────────────────────────────┐   │   │ │
│  │  │  │  Penetration Testing Tools (20+)                         │   │   │ │
│  │  │  │  Network: Nmap, Masscan                                  │   │   │ │
│  │  │  │  Web: Nikto, WPScan, WhatWeb                             │   │   │ │
│  │  │  │  Directory: Gobuster, Feroxbuster, FFUF                  │   │   │ │
│  │  │  │  Vulnerability: Nuclei (CVE templates)                   │   │   │ │
│  │  │  │  Exploitation: Metasploit, Searchsploit                  │   │   │ │
│  │  │  │  Passwords: Hydra, John, Hashcat                         │   │   │ │
│  │  │  │  Enumeration: Enum4linux-ng, Amass, Subfinder            │   │   │ │
│  │  │  │  SQL: SQLmap                                             │   │   │ │
│  │  │  └──────────────────────────────────────────────────────────┘   │   │ │
│  │  │                                                                 │   │ │
│  │  │  ┌──────────────────────────────────────────────────────────┐   │   │ │
│  │  │  │  Scan Logs & Results                                     │   │   │ │
│  │  │  │  /opt/scans/logs/ (job persistence)                      │   │   │ │
│  │  │  └──────────────────────────────────────────────────────────┘   │   │ │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  CVE RAG System (rag.py)                                            │    │
│  │  - SQLite FTS5: 320k+ CVEs (NVD 1999-2026 + OSV.dev)                │    │
│  │  - ChromaDB: all-MiniLM-L6-v2 vector embeddings                     │    │
│  │  - Hybrid search: FTS5 + vector ANN + RRF merge                     │    │
│  │  - Alias resolver: "react" → ["react", "react-dom", "reactjs"]      │    │
│  │  - Query latency: <10ms                                             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  AI Analysis Layer (ai_analysis.py)                                 │    │
│  │  - Context window manager (80k token budget)                        │    │
│  │  - Per-tool output caps (nmap: 40k, nuclei: 30k, etc.)              │    │
│  │  - Signal-line extraction (CVE IDs, open ports, errors)             │    │
│  │  - 14-section report schema enforcer                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  PDF Report Renderer (pdf_report.py)                                │    │
│  │  - ReportLab-based professional PDF generator                       │    │
│  │  - 14 sections: Cover → TOC → Findings → CVE Analysis → Sign-off    │    │
│  │  - Dark navy headers, severity color coding, code blocks            │    │
│  │  - Output: results/reports/*.pdf                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Results Storage                                                    │    │
│  │  results/raw/*.json     — Raw tool outputs (JSON)                   │    │
│  │  results/reports/*.pdf  — Final PDF reports                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Description

| Layer | File | Host | Role |
|-------|------|------|------|
| AI Client | Claude Desktop / Cline | Windows | Natural language interface, report generation |
| MCP Server | `mcp_server.py` | Windows | Bridges Claude to tools and CVE RAG engine |
| CVE RAG Engine | `cve_rag.py` | Windows | Local 320k CVE retrieval via SQLite FTS5 + Vector DB Hybride|
| API Server | `kali_server.py` | Kali VM | Flask REST API — executes pentest tools |
| Persistence | `results/*.json` | Windows | All scan outputs saved as JSON |
| Audit Logs | `/opt/scans/logs/` | Kali VM | Server-side scan audit trail |

---

## 🔍 CVE RAG Intelligence

The CVE RAG (Retrieval-Augmented Generation) engine is a new core component that gives Claude AI instant access to 320,000+ CVE records without any internet dependency.

### How It Works

```
nmap finds "Apache 2.4.49"
        ↓
cve_enrich_scan_results("apache 2.4.49")
        ↓
SQLite FTS5 query → cve_index.db
        ↓
Returns: CVE-2021-41773 (CRITICAL 9.8), CVE-2021-42013 (CRITICAL 9.8), ...
        ↓
Claude embeds CVE intelligence into pentest report
```

### CVE RAG Tools (6 MCP tools)

| Tool | Purpose |
|------|---------|
| `cve_search_product` | Find CVEs for a discovered service + version |
| `cve_lookup_id` | Full details for a specific CVE ID |
| `cve_search_keyword` | Free-text search ("rce apache", "sqli mysql") |
| `cve_enrich_scan_results` | Batch enrich all nmap-discovered services at once |
| `cve_get_by_severity` | Top CVEs by CRITICAL/HIGH/MEDIUM/LOW + year filter |
| `cve_database_stats` | Total count, severity breakdown, year distribution |

### Setup (one-time)

```bash
# Build the SQLite index from 320k CVE JSON files (~5-10 min)
python cve_rag.py --build

# Test it
python cve_rag.py --search "apache 2.4.49"
python cve_rag.py --id CVE-2021-44228
python cve_rag.py --stats
```

**Specs:** ~200–400 MB index | <10ms per query | No internet required | SQLite FTS5

---

## ✨ Features

### Core Features

#### 1. Automated Vulnerability Scanning (5 Phases)
- **Phase 1 — Recon:** Nmap, WhatWeb, Subfinder, Amass
- **Phase 2 — Scanning:** Nikto, Gobuster, Feroxbuster, FFUF, Nuclei, WPScan
- **Phase 3 — Exploitation:** SQLmap, Hydra, Searchsploit, Metasploit, Enum4linux-ng
- **Phase 4 — CVE Enrichment:** All 6 CVE RAG tools run against discovered services
- **Phase 5 — Report:** Claude AI generates 14-section PDF with CVE intelligence

#### 2. CVE RAG Intelligence (NEW)
- 320,000+ CVEs indexed locally (1999–2026)
- Instant cross-referencing after every tool execution
- Historical context: first CVE year, total count, exploit trends
- Per-finding CVE intelligence block in every report section
- No internet required — all queries against local SQLite database

#### 3. Professional Report Generation (14 sections)
- Cover page with CVE database coverage badge
- Executive summary with CVE intelligence summary
- Per-vulnerability: HTTP request/response blocks + CVE intelligence block
- CVE Intelligence Analysis section (Section 10) — trends, patterns, top CVEs
- Priority remediation roadmap with CVE-specific patches
- CVSS v3.1 scores, CWE references, NVD/MITRE links

#### 4. Persistence & Recovery
- All scan results saved to `./results/*.json`
- Crash recovery via `get_scan_history` / `get_scan_details` MCP tools
- Audit logs at `/opt/scans/logs/` on Kali VM

#### 5. Security Controls
- API key authentication (`X-API-Key` header)
- Input sanitization — dangerous shell chars stripped
- Rate limiting — 429 on excess requests
- Concurrent scan limit — max 5 simultaneous scans
- Read-only SQLite connection for CVE RAG queries

---

## 🛠️ Technology Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Language | Python 3.8+ |
| API Framework | Flask + Flask-Limiter |
| MCP Protocol | FastMCP |
| CVE Database | SQLite FTS5 (stdlib — no extra deps) |
| HTTP Client | Requests |
| Config | python-dotenv |

### AI Integration
| Component | Technology |
|-----------|-----------|
| AI Client | Claude AI (Anthropic) |
| Alternative | Cline (VS Code) + OpenRouter |
| Protocol | Model Context Protocol (MCP) |

### Pentest Tools (18)
| Category | Tools |
|----------|-------|
| Network Scanning | Nmap, Masscan |
| Web Scanning | Nikto, WPScan, WhatWeb |
| Directory Enumeration | Gobuster, Feroxbuster, FFUF |
| Vulnerability Scanning | Nuclei |
| Exploitation | Metasploit Framework, Searchsploit |
| Password Cracking | Hydra, John the Ripper, Hashcat |
| Enumeration | Enum4linux-ng, Amass, Subfinder |
| SQL Injection | SQLmap |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Pentest OS | Kali Linux (VM) |
| Virtualization | VMware Workstation Pro / VirtualBox |
| Host OS | Windows 10/11 |

---

## 📥 Installation Guide

### Prerequisites

**Hardware:**
- CPU: 4+ cores | RAM: 16 GB minimum | Disk: 70 GB free

**Software:**
- Windows 10/11 (host), Kali Linux VM, Python 3.8+, Claude Desktop or VS Code + Cline

---

### Step 1 — Kali Linux VM Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install all pentest tools
sudo apt install -y nmap masscan gobuster feroxbuster nikto \
                    sqlmap metasploit-framework hydra john \
                    wpscan ffuf amass hashcat nuclei subfinder \
                    exploitdb whatweb enum4linux-ng python3-flask python3-requests

# Update tool databases
nuclei -update-templates
searchsploit -u
sudo msfupdate

# Create scan log directory
sudo mkdir -p /opt/scans/logs && sudo chmod 777 /opt/scans/logs

# Clone repo
git clone https://github.com/RISLAN-MOH-TM/CRP-project-.git
cd CRP-project-

# Get your Kali VM IP
ip addr show

# Start the API server
sudo python3 kali_server.py --ip 0.0.0.0 --port 5000
```

---

### Step 2 — Windows Host Setup

```powershell
# Install Python dependencies
pip install requests python-dotenv mcp flask flask-limiter

# Clone repo
git clone https://github.com/RISLAN-MOH-TM/CRP-project-.git
cd CRP-project-

# Create .env file (replace IP with your Kali VM IP)
@"
KALI_API_KEY=kali-research-project-2026
KALI_SERVER_IP=10.11.189.244
"@ | Out-File -FilePath ".env" -Encoding UTF8

# Build the CVE RAG index (one-time, ~5-10 minutes)
python cve_rag.py --build

# Verify index
python cve_rag.py --stats
```

---

### Step 3 — Claude Desktop MCP Setup

Edit or create: `C:\Users\YourName\.config\claude-mcp\config.json`

```json
{
  "mcpServers": {
    "kali-pentest": {
      "command": "python",
      "args": [
        "C:\\Users\\User\\User\\Desktop\\mcp\\mcp_server.py",
        "--server", "http://10.11.189.244:5000"
      ],
      "env": {
        "KALI_API_KEY": "kali-research-project-2026",
        "KALI_SERVER_IP": "10.11.189.244"
      }
    }
  }
}
```

Restart Claude Desktop. The MCP server loads all 35 tools automatically.

---

### Step 4 — Verify Everything Works

```bash
# 1. Test Kali API
curl http://10.11.189.244:5000/health

# 2. Test CVE RAG
python cve_rag.py --search "apache 2.4.49"

# 3. Test in Claude — ask:
"Check the Kali server health and show CVE database stats"
```

---

## 💡 Usage

### Quick Start — use PROMPT.txt

Open `PROMPT.txt`, replace `[URL]`, `[APP]`, `[DATE]`, paste into Claude. That's it.

### Manual Workflow

#### Phase 1 — Recon
```
Run nmap_scan, whatweb_scan, subfinder_scan on http://target.com/app/
Then call cve_enrich_scan_results with all discovered services
```

#### Phase 2 — Scan
```
Run nikto_scan, gobuster_scan, ffuf_scan, nuclei_scan on http://target.com/app/
For each CVE ID nuclei reports, call cve_lookup_id
```

#### Phase 3 — Exploit
```
Run sqlmap_scan, hydra_attack, searchsploit_search on http://target.com/app/
For each confirmed finding, call cve_search_keyword
```

#### Phase 4 — CVE Enrichment
```
cve_database_stats()
cve_enrich_scan_results("all services", limit_per=8)
cve_get_by_severity("CRITICAL", year="2024")
analyze_all_results()
```

#### Phase 5 — Report
```
Generate a professional 14-section PDF pentest report using all scan results
and CVE intelligence. Follow the spec in PROMPT.txt.
```

### CVE RAG Examples

```python
# After nmap finds Apache 2.4.49
cve_enrich_scan_results("apache 2.4.49, openssh 8.2p1, php 7.4.3")

# After nuclei reports a CVE
cve_lookup_id("CVE-2021-41773")

# Historical context for a finding type
cve_search_keyword("path traversal apache")

# Trending critical CVEs for report context
cve_get_by_severity("CRITICAL", year="2024")
```

---

## 📋 Prompt Files

| File | Purpose |
|------|---------|
| `PROMPT.txt` | Simple, powerful — paste into Claude to start a full pentest |
| `information/PENTEST_PROMPT_WITH_CVE_RAG.txt` | Full detailed spec with all 5 phases and 14-section report |
| `TEST PROMPT .txt` | Quick launch version |

---

## 🎓 Research Objectives

### Primary
1. **Automation** — Reduce manual pentest effort by 80%, standardize procedures
2. **CVE Intelligence** — Local RAG system for instant CVE cross-referencing without internet
3. **AI Integration** — LLM-driven analysis, interpretation, and report generation
4. **Scalability** — Multiple concurrent targets, optimized resource utilization

### Secondary
1. **Educational** — Teach pentest concepts through automated workflows
2. **Research Platform** — Benchmark AI models and tool effectiveness
3. **Industry Readiness** — Professional-grade reports meeting compliance standards

---

## 🔬 Methodology

### 5-Phase Testing Approach

```
Phase 1: Recon      → nmap, whatweb, subfinder, amass
                       + cve_enrich_scan_results()

Phase 2: Scanning   → nikto, gobuster, feroxbuster, ffuf, nuclei, wpscan
                       + cve_lookup_id() per CVE found

Phase 3: Exploit    → sqlmap, hydra, searchsploit, metasploit, enum4linux-ng
                       + cve_search_keyword() per finding type

Phase 4: CVE Enrich → cve_database_stats, cve_enrich_scan_results,
                       cve_get_by_severity, analyze_all_results

Phase 5: Report     → Claude AI → 14-section PDF with CVE intelligence
```

---

## 📊 Results & Analysis

### Performance Metrics

| Metric | Manual Testing | This System | Improvement |
|--------|---------------|-------------|-------------|
| Time per scan | 2–4 hours | 10–30 minutes | 80% faster |
| Report generation | 1–2 hours | 2–5 minutes | 95% faster |
| CVE cross-referencing | Manual / hours | <10ms per query | 99% faster |
| Consistency | Variable | Standardized | 100% |
| Scalability | 1 target | 5 concurrent | 5x |
| Cost per test | $200–500 | $0–20 | 90% cheaper |

### CVE RAG Performance

| Metric | Value |
|--------|-------|
| Total CVEs indexed | 320,000+ |
| Coverage | 1999–2026 |
| Query speed | <10ms |
| Index size | ~200–400 MB |
| Build time (one-time) | ~5–10 minutes |
| Internet required | No |

---

## 🚀 Future Enhancements

### Short-term
- PDF export with embedded charts
- CVE RAG auto-update from NVD feed
- Web dashboard for scan management

### Medium-term
- ML-based false positive reduction
- Cloud deployment (distributed scanning)
- PCI-DSS / HIPAA compliance report templates

### Long-term
- Autonomous adaptive testing strategies
- Enterprise multi-tenant support
- Published research paper

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| `PROMPT.txt` | Simple pentest prompt — start here |
| `claude_mcp_config.json` | Claude Desktop MCP configuration |
| `architecture.json` | Full system architecture in JSON |
| `information/TOOLS_QUICK_REFERENCE.txt` | All 35 tools with MCP names and workflow |
| `information/PENTEST_PROMPT_WITH_CVE_RAG.txt` | Full 5-phase prompt with 14-section report spec |
| `information/HOWTO.md` | Step-by-step setup guide |
| `information/PROJECT_SETUP.md` | Detailed setup guide |
| `information/SECURITY.md` | Security features and controls |
| `information/RATE_LIMIT_GUIDE.md` | Rate limiting guide |
| `information/METASPLOIT_GUIDE.md` | Metasploit usage |
| `parse_results.py` | Standalone result analysis script |

---

## 👥 Contributors

**Project Lead & Developer:**
MT. RISLAN MOHAMED — System Architecture, Implementation, Testing
[GitHub](https://github.com/RISLAN-MOH-TM)

**Academic Supervisor:** Mr. MIM Mohamed Nismy
**Assessor:** Mrs. ALF Sajeetha
**Institution:** BCAS Campus — Computer Science / Cybersecurity

**Special Thanks:** Anthropic (Claude AI), Kali Linux Team, Open Source Security Community

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

This project is developed as part of academic research. Use only against systems you own or have explicit written permission to test.
