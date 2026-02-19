# Kali Linux MCP Server - Research Project 🛡️

AI-powered penetration testing using Claude AI + Kali Linux + MCP Protocol

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Security](https://img.shields.io/badge/security-hardened-green.svg)](SECURITY_IMPROVEMENTS.md)

---

## 📖 Overview

This project enables AI agents like Claude to control Kali Linux penetration testing tools through a secure REST API using the Model Context Protocol (MCP). Designed for research and educational purposes.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Windows Host                          │
│  ┌────────────────┐              ┌──────────────────┐  │
│  │   VS Code      │              │   Claude AI      │  │
│  │  mcp_server.py │◄────────────►│   Desktop        │  │
│  └────────┬───────┘              └──────────────────┘  │
│           │                                              │
│           │ HTTP API (Port 5000)                        │
│           │                                              │
│  ┌────────▼────────────────────────────────────────┐   │
│  │         VMware Workstation Pro                   │   │
│  │  ┌──────────────────────────────────────────┐   │   │
│  │  │        Kali Linux VM                      │   │   │
│  │  │  ┌────────────────────────────────────┐  │   │   │
│  │  │  │      kali_server.py                │  │   │   │
│  │  │  │  (Flask API Server)                │  │   │   │
│  │  │  └────────────────────────────────────┘  │   │   │
│  │  │  ┌────────────────────────────────────┐  │   │   │
│  │  │  │   Kali Tools                       │  │   │   │
│  │  │  │   nmap, ffuf, sqlmap, etc.        │  │   │   │
│  │  │  └────────────────────────────────────┘  │   │   │
│  │  └──────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## ✨ Features

### 🔧 Supported Tools (14+)
- **Network Scanning:** Nmap
- **Web Fuzzing:** FFUF, Feroxbuster, Gobuster
- **Web Scanning:** Nikto, WPScan
- **Vulnerability Testing:** SQLmap, OpenVAS
- **Exploitation:** Metasploit Framework
- **Password Cracking:** John the Ripper, Hashcat, Hydra
- **Enumeration:** Enum4linux-ng, Amass

### 🔒 Security Features
- ✅ API key authentication (default: `kali-research-project-2024`)
- ✅ Rate limiting (prevents abuse)
- ✅ Command whitelist (only approved tools)
- ✅ Path sanitization (prevents path traversal)
- ✅ Input validation (all parameters validated)
- ✅ Secure temp files (random names, auto cleanup)
- ✅ Audit logging (complete activity tracking)

**Security Score: 10/10** ✅

---

## 🚀 Quick Start

### Prerequisites
- **Kali Linux** (in VMware or VirtualBox)
- **Windows** (host machine)
- **Python 3.8+** (on both systems)
- **Claude Desktop** (optional, for AI integration)

### Part 1: Kali Linux VM Setup

```bash
# 1. Install Python packages (use apt for Kali 2023+)
sudo apt update
sudo apt install -y python3-flask python3-requests

# 2. Install penetration testing tools
sudo apt install -y nmap gobuster feroxbuster nikto sqlmap \
                    metasploit-framework hydra john wpscan \
                    ffuf amass hashcat

# 3. Install enum4linux-ng
pip3 install enum4linux-ng --break-system-packages

# 4. Clone the repository
git clone https://github.com/RISLAN-MOH-TM/PCP-project-.git
cd PCP-project-

# 5. Get your Kali VM IP address
ip addr show
# Note the IP (example: 192.168.1.100)

# 6. Start the server (allow connections from Windows)
python3 kali_server.py --ip 0.0.0.0 --port 5000
```

**Keep this terminal open!**

### Part 2: Windows Host Setup

```powershell
# 1. Install Python packages
pip install requests python-dotenv

# 2. Clone the repository
git clone https://github.com/RISLAN-MOH-TM/PCP-project-.git
cd PCP-project-

# 3. Create .env file
@"
KALI_API_KEY=kali-research-project-2024
KALI_SERVER_IP=192.168.1.100
"@ | Out-File -FilePath ".env" -Encoding UTF8

# Replace 192.168.1.100 with your Kali VM IP!

# 4. Test connection
curl http://192.168.1.100:5000/health
```

### Part 3: Claude AI Integration (Optional)

1. **Configure Claude MCP** (`C:\Users\YourName\.config\claude-mcp\config.json`):

```json
{
  "mcpServers": {
    "kali-tools": {
      "command": "python",
      "args": [
        "C:\\path\\to\\PCP-project-\\mcp_server.py",
        "--server", "http://192.168.1.100:5000"
      ],
      "env": {
        "KALI_API_KEY": "kali-research-project-2024"
      }
    }
  }
}
```

2. **Restart Claude Desktop**

3. **Test with Claude:**
```
"Check the Kali server health"
"Scan 192.168.1.1 with nmap"
"Find hidden directories on https://example.com"
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [README_FIRST.txt](README_FIRST.txt) | Quick start overview - **START HERE!** |
| [HOWTO.md](HOWTO.md) | Simple step-by-step guide |
| [PROJECT_SETUP.md](PROJECT_SETUP.md) | Complete setup for VM architecture |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common problems & solutions |

---

## 💡 Usage Examples

### With Claude AI

```
"Run an nmap scan on 192.168.1.1 to identify open ports and services"

"Use ffuf to find hidden directories on https://example.com"

"Check if https://wordpress-site.com has any WordPress vulnerabilities"

"Scan the network 192.168.1.0/24 for live hosts"
```

### Direct API Calls

```bash
# Nmap scan
curl -X POST http://192.168.1.100:5000/api/tools/nmap \
  -H "Content-Type: application/json" \
  -H "X-API-Key: kali-research-project-2026" \
  -d '{
    "target": "192.168.1.1",
    "scan_type": "-sV",
    "ports": "80,443,8080"
  }'

# Directory fuzzing with FFUF
curl -X POST http://192.168.1.100:5000/api/tools/ffuf \
  -H "Content-Type: application/json" \
  -H "X-API-Key: kali-research-project-2026" \
  -d '{
    "url": "https://example.com/FUZZ",
    "wordlist": "/usr/share/wordlists/dirb/common.txt",
    "max_results": 100
  }'
```

---

## 🔧 Configuration

### Default Settings
- **API Key:** `kali-research-project-2024` (for research use)
- **Port:** 5000
- **Timeout:** 180 seconds (3 minutes)
- **Rate Limit:** 10 requests/minute per endpoint

### Environment Variables (.env file)
```bash
KALI_API_KEY=kali-research-project-2026
KALI_SERVER_IP=192.168.1.100
API_PORT=5000
DEBUG_MODE=0
MAX_CONCURRENT_SCANS=5
```

---

## 🐛 Troubleshooting

### Common Issues

**"externally-managed-environment" error on Kali:**
```bash
# Use apt instead of pip3
sudo apt install python3-flask python3-requests
```

**"Cannot connect to Kali server":**
```bash
# Check Kali server is running
ps aux | grep kali_server

# Check firewall
sudo ufw allow 5000

# Verify IP address
ip addr show
```

**".env file not found":**
```powershell
# Create in project root (not inside mcp\mcp\ folder)
cd C:\path\to\PCP-project-
notepad .env
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more solutions.

---

## 📊 API Endpoints

### Health Check
```
GET /health
```

### Tool Endpoints
```
POST /api/tools/nmap
POST /api/tools/gobuster
POST /api/tools/feroxbuster
POST /api/tools/ffuf
POST /api/tools/nikto
POST /api/tools/sqlmap
POST /api/tools/wpscan
POST /api/tools/metasploit
POST /api/tools/hydra
POST /api/tools/john
POST /api/tools/hashcat
POST /api/tools/amass
POST /api/tools/enum4linux-ng
POST /api/tools/openvas
POST /api/command (restricted)
```

All endpoints require `X-API-Key` header.

---

## ⚠️ Legal Disclaimer

**IMPORTANT:** This tool is designed for authorized security testing and research purposes only.

- ✅ Only use on systems you own or have explicit written permission to test
- ✅ Comply with all applicable laws and regulations
- ✅ Respect rate limits and terms of service
- ❌ Never use for unauthorized access or malicious purposes

**You are solely responsible for your actions when using this tool.**

Unauthorized access to computer systems is illegal and may result in criminal prosecution.

---

## 🎓 Research & Educational Use

This project is designed for:
- Security research and analysis
- Educational demonstrations
- Penetration testing training
- AI-assisted security testing research
- Academic projects and papers

---

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

For security issues, please email instead of creating public issues.

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Inspired by [project_astro](https://github.com/whit3rabbit0/project_astro)
- Built with [FastMCP](https://github.com/jlowin/fastmcp)
- Powered by [Kali Linux](https://www.kali.org/)
- Designed for [Claude MCP](https://www.anthropic.com/)

---

## 📞 Support

- 📖 **Documentation:** See docs folder
- 🐛 **Issues:** [GitHub Issues](https://github.com/RISLAN-MOH-TM/PCP-project-/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/RISLAN-MOH-TM/PCP-project-/discussions)

---

## 🎯 Project Stats

- **Security Score:** 10/10 ✅
- **Supported Tools:** 14+
- **Architecture:** Kali VM + Windows + Claude
- **Purpose:** Research & Education
- **Status:** Active Development

---

**Made for research and educational purposes** 🎓

**Stay Ethical. Stay Legal. Stay Secure.** 🛡️

---

## Quick Links

- 📖 [Quick Start Guide](README_FIRST.txt)
- 🔧 [Setup Instructions](HOWTO.md)
- 🏗️ [Architecture Details](PROJECT_SETUP.md)
- 🐛 [Troubleshooting](TROUBLESHOOTING.md)

**Version:** 1.0.0  
**Last Updated:** 2024  
**Repository:** https://github.com/RISLAN-MOH-TM/PCP-project-
