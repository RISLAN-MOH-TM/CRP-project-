# Kali Linux MCP Server - Research Project 🛡️

AI-powered penetration testing using Claude AI + Kali Linux + MCP Protocol

## 🏗️ Architecture

- **Kali Linux VM** (VMware) - Runs penetration testing tools
- **Windows Host** - Runs Claude AI and MCP client
- **Claude AI** - Controls Kali tools via natural language

## 🚀 Quick Start

### On Kali Linux VM:

1. **Install dependencies:**
```bash
# Use apt for Python packages (Kali requirement)
sudo apt update
sudo apt install -y python3-flask python3-requests

# Install penetration testing tools
sudo apt install -y nmap ffuf sqlmap nikto gobuster feroxbuster \
                    metasploit-framework hydra john wpscan amass hashcat

# Install enum4linux-ng
pip3 install enum4linux-ng --break-system-packages
```

2. **Start server:**
```bash
python3 kali_server.py --ip 0.0.0.0 --port 5000
```

### On Windows Host:

1. **Install dependencies:**
```powershell
pip install requests python-dotenv
```

2. **Create .env file:**
```
KALI_API_KEY=kali-research-project-2024
KALI_SERVER_IP=192.168.xxx.xxx
```

3. **Configure Claude MCP** (see `PROJECT_SETUP.md`)

4. **Ask Claude:**
```
"Check the Kali server health"
"Scan 192.168.1.1 with nmap"
```

## 📚 Documentation

- **PROJECT_SETUP.md** - Complete setup guide for your architecture
- **SECURITY_IMPROVEMENTS.md** - Security features
- **CLAUDE_MCP_SETUP.md** - Claude integration details

## 🔧 Supported Tools

Network: Nmap | Web: FFUF, Feroxbuster, Gobuster, Nikto, WPScan | Vuln: SQLmap, OpenVAS | Exploit: Metasploit | Password: John, Hashcat, Hydra | Enum: Enum4linux-ng, Amass

## 🔒 Security

- ✅ API key authentication (default: `kali-research-project-2024`)
- ✅ Rate limiting
- ✅ Command validation
- ✅ Path sanitization
- ✅ Input validation

**Note:** Default API key is for research/development only.

## ⚠️ Legal Notice

For authorized testing only. You are responsible for compliance with all applicable laws.

## 📝 License

MIT License - See LICENSE file

---

**Made for research and educational purposes** 🎓
