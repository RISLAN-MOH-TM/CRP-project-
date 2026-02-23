# New Tools Installation Guide 🔧

Quick guide to install the 5 new tools on your Kali Linux VM.

---

## 📋 New Tools Added

1. **Nuclei** - Modern vulnerability scanner
2. **Masscan** - Ultra-fast port scanner
3. **Subfinder** - Passive subdomain discovery
4. **Searchsploit** - Exploit database search
5. **WhatWeb** - Web technology detection

---

## 🚀 Installation Commands

### On Kali Linux VM

```bash
# Update package list
sudo apt update

# Install all new tools at once
sudo apt install -y nuclei masscan subfinder exploitdb whatweb

# Verify installations
which nuclei
which masscan
which subfinder
which searchsploit
which whatweb
```

### Individual Installation

#### 1. Nuclei
```bash
sudo apt install -y nuclei

# Update templates
nuclei -update-templates

# Test
nuclei -version
```

#### 2. Masscan
```bash
sudo apt install -y masscan

# Test
masscan --version
```

#### 3. Subfinder
```bash
sudo apt install -y subfinder

# Test
subfinder -version
```

#### 4. Searchsploit (Exploit-DB)
```bash
sudo apt install -y exploitdb

# Update database
searchsploit -u

# Test
searchsploit --version
```

#### 5. WhatWeb
```bash
sudo apt install -y whatweb

# Test
whatweb --version
```

---

## ✅ Verification

After installation, restart your Kali server and check the health endpoint:

```bash
# Restart Kali server
sudo python3 kali_server.py --ip 0.0.0.0 --port 5000
```

You should see all 18 tools being checked:
```
2026-02-23 XX:XX:XX [INFO] Executing command: which nmap
2026-02-23 XX:XX:XX [INFO] Executing command: which masscan
2026-02-23 XX:XX:XX [INFO] Executing command: which gobuster
...
2026-02-23 XX:XX:XX [INFO] Executing command: which nuclei
2026-02-23 XX:XX:XX [INFO] Executing command: which subfinder
2026-02-23 XX:XX:XX [INFO] Executing command: which searchsploit
2026-02-23 XX:XX:XX [INFO] Executing command: which whatweb
```

Or test via API:
```bash
curl http://172.20.10.11:5000/health | jq
```

---

## 💡 Usage Examples

### Nuclei
```bash
# Scan for CVEs
nuclei -u https://example.com -t cves/ -severity critical,high

# Scan for exposed panels
nuclei -u https://example.com -t exposures/

# Full scan
nuclei -u https://example.com
```

### Masscan
```bash
# Quick scan
sudo masscan 192.168.1.0/24 -p80,443,8080 --rate=1000

# Full port scan
sudo masscan 192.168.1.100 -p1-65535 --rate=10000

# Save results
sudo masscan 192.168.1.0/24 -p1-65535 -oL scan.txt
```

### Subfinder
```bash
# Basic subdomain discovery
subfinder -d example.com

# Silent mode
subfinder -d example.com -silent

# Save results
subfinder -d example.com -o subdomains.txt
```

### Searchsploit
```bash
# Search for exploits
searchsploit apache 2.4

# Search CVE
searchsploit CVE-2021-44228

# JSON output
searchsploit wordpress --json
```

### WhatWeb
```bash
# Basic scan
whatweb https://example.com

# Aggressive scan
whatweb -a 3 https://example.com

# Verbose output
whatweb -v https://example.com
```

---

## 🎯 Usage with AI Clients

### With Claude/Cline/Ollama:

```
"Use Nuclei to scan https://example.com for critical CVEs"

"Run Masscan on 192.168.1.0/24 to find open ports quickly"

"Find subdomains for example.com using Subfinder"

"Search for Apache 2.4 exploits using Searchsploit"

"Identify the technologies used on https://example.com with WhatWeb"
```

### With Python (ollama_client.py):

```python
# All new tools are automatically available
python ollama_client.py

You: Scan https://example.com with Nuclei for CVEs
You: Find subdomains for example.com
You: What technologies does https://example.com use?
```

---

## 🐛 Troubleshooting

### Issue: "nuclei: command not found"
```bash
# Install from apt
sudo apt install -y nuclei

# Or install from GitHub
GO111MODULE=on go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest
```

### Issue: "masscan: Operation not permitted"
```bash
# Masscan requires root privileges
sudo masscan 192.168.1.0/24 -p80,443
```

### Issue: "subfinder: command not found"
```bash
# Install from apt
sudo apt install -y subfinder

# Or install from GitHub
GO111MODULE=on go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
```

### Issue: "searchsploit database outdated"
```bash
# Update exploit database
searchsploit -u
```

### Issue: "whatweb: command not found"
```bash
# Install from apt
sudo apt install -y whatweb

# Or install from GitHub
git clone https://github.com/urbanadventurer/WhatWeb.git
cd WhatWeb
sudo make install
```

---

## 📊 Tool Comparison

| Tool | Speed | Accuracy | Use Case |
|------|-------|----------|----------|
| Nuclei | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | CVE detection, misconfigurations |
| Masscan | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Fast port scanning |
| Subfinder | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Passive subdomain discovery |
| Searchsploit | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Exploit research |
| WhatWeb | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Technology fingerprinting |

---

## 🎓 Best Practices

### 1. Nuclei
- Update templates regularly: `nuclei -update-templates`
- Use severity filtering to reduce noise
- Combine with other scanners for comprehensive coverage

### 2. Masscan
- Always use with sudo (requires raw sockets)
- Start with low rate (1000) and increase gradually
- Verify results with nmap for accuracy

### 3. Subfinder
- Use silent mode for clean output
- Combine with Amass for comprehensive subdomain discovery
- Save results to file for later analysis

### 4. Searchsploit
- Update database regularly: `searchsploit -u`
- Use specific version numbers for better results
- Verify exploits before using

### 5. WhatWeb
- Start with aggression level 1 (stealthy)
- Increase aggression only if needed
- Use verbose mode for detailed information

---

## 📚 Additional Resources

- **Nuclei:** https://github.com/projectdiscovery/nuclei
- **Masscan:** https://github.com/robertdavidgraham/masscan
- **Subfinder:** https://github.com/projectdiscovery/subfinder
- **Searchsploit:** https://www.exploit-db.com/searchsploit
- **WhatWeb:** https://github.com/urbanadventurer/WhatWeb

---

**All tools are now integrated and ready to use!** 🎉

**Stay Ethical. Stay Legal. Stay Secure.** 🛡️
