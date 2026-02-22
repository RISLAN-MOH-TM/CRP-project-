# Available Tools Reference

## Complete Tool List (16 Tools)

Your Kali MCP Server currently has **16 powerful penetration testing tools** available through Claude AI.

---

## 🔍 Network Scanning & Reconnaissance

### 1. **nmap_scan** - Network Mapper
**Purpose:** Port scanning, service detection, OS fingerprinting

**Parameters:**
- `target` (required): IP address or hostname
- `scan_type` (optional): Scan type (default: "-sV")
- `ports` (optional): Port range (e.g., "80,443,8080")
- `additional_args` (optional): Extra nmap arguments

**Examples:**
```
"Scan 192.168.1.100 with nmap to find open ports"
"Run nmap service version detection on 192.168.1.1"
"Scan ports 1-1000 on 10.0.0.1"
```

**Rate Limit:** 8-12 requests/minute (dynamic)

---

### 2. **amass_scan** - Subdomain Enumeration
**Purpose:** DNS enumeration, subdomain discovery, network mapping

**Parameters:**
- `domain` (required): Target domain
- `mode` (optional): enum, intel, viz, track, db (default: "enum")
- `additional_args` (optional): Extra amass arguments

**Examples:**
```
"Find all subdomains for example.com using amass"
"Enumerate DNS records for target-domain.com"
```

**Rate Limit:** 6-9 requests/minute (dynamic)

---

### 3. **enum4linux_ng_scan** - SMB/Windows Enumeration
**Purpose:** SMB share enumeration, user listing, Windows network info

**Parameters:**
- `target` (required): Target IP or hostname
- `additional_args` (optional): Extra arguments (default: "-A")

**Examples:**
```
"Enumerate SMB shares on 192.168.1.100"
"Get Windows user list from 10.0.0.50"
```

**Rate Limit:** 12-18 requests/minute (dynamic)

---

## 🌐 Web Application Testing

### 4. **gobuster_scan** - Directory/DNS Brute Forcing
**Purpose:** Directory discovery, DNS subdomain brute forcing

**Parameters:**
- `url` (required): Target URL
- `mode` (optional): dir, dns, fuzz, vhost (default: "dir")
- `wordlist` (optional): Path to wordlist
- `additional_args` (optional): Extra gobuster arguments

**Examples:**
```
"Find hidden directories on https://example.com"
"Brute force DNS subdomains for example.com"
```

**Rate Limit:** 10-15 requests/minute (dynamic)

---

### 5. **feroxbuster_scan** - Fast Web Fuzzer
**Purpose:** Fast directory/file discovery with recursion

**Parameters:**
- `url` (required): Target URL
- `wordlist` (optional): Path to wordlist
- `threads` (optional): Number of threads (default: 50)
- `max_results` (optional): Limit results (default: 200)
- `additional_args` (optional): Extra arguments

**Examples:**
```
"Use feroxbuster to find hidden files on https://example.com"
"Scan https://target.com with 100 threads"
```

**Rate Limit:** 8-12 requests/minute (dynamic)

---

### 6. **ffuf_scan** - Fast Web Fuzzer
**Purpose:** Web fuzzing, parameter discovery, virtual host discovery

**Parameters:**
- `url` (required): Target URL (use FUZZ keyword)
- `wordlist` (optional): Path to wordlist
- `mode` (optional): dir, param, vhost (default: "dir")
- `max_results` (optional): Limit results (default: 100)
- `additional_args` (optional): Extra ffuf arguments

**Examples:**
```
"Fuzz directories on https://example.com/FUZZ"
"Find hidden parameters on https://api.example.com"
```

**Rate Limit:** 8-12 requests/minute (dynamic)

---

### 7. **nikto_scan** - Web Server Scanner
**Purpose:** Web server vulnerability scanning, misconfiguration detection

**Parameters:**
- `target` (required): Target URL or IP
- `additional_args` (optional): Extra nikto arguments

**Examples:**
```
"Scan https://example.com with nikto"
"Check web server vulnerabilities on 192.168.1.100"
```

**Rate Limit:** 10-15 requests/minute (dynamic)

---

### 8. **wpscan_analyze** - WordPress Scanner
**Purpose:** WordPress vulnerability scanning, plugin/theme detection

**Parameters:**
- `url` (required): WordPress site URL
- `additional_args` (optional): Extra wpscan arguments

**Examples:**
```
"Scan https://wordpress-site.com for vulnerabilities"
"Check WordPress plugins on https://blog.example.com"
```

**Rate Limit:** 10-15 requests/minute (dynamic)

---

### 9. **sqlmap_scan** - SQL Injection Testing
**Purpose:** Automated SQL injection detection and exploitation

**Parameters:**
- `url` (required): Target URL
- `data` (optional): POST data
- `additional_args` (optional): Extra sqlmap arguments

**Examples:**
```
"Test https://example.com/login.php for SQL injection"
"Check if https://api.example.com/user?id=1 is vulnerable to SQLi"
```

**Rate Limit:** 3-5 requests/minute (dynamic)
**Warning:** Very resource-intensive

---

## 🔓 Exploitation & Attack Tools

### 10. **metasploit_run** - Metasploit Framework
**Purpose:** Exploit execution, vulnerability scanning, post-exploitation

**Parameters:**
- `module` (required): Metasploit module path
- `options` (optional): Dictionary of module options

**Examples:**
```
"Use Metasploit to check if 192.168.1.100 is vulnerable to EternalBlue"
"Run Metasploit SMB version scanner on 192.168.1.0/24"
"Scan for MS17-010 vulnerability using Metasploit"
```

**Common Modules:**
- `auxiliary/scanner/smb/smb_version` - SMB version detection
- `auxiliary/scanner/smb/smb_ms17_010` - EternalBlue scanner
- `auxiliary/scanner/ssh/ssh_version` - SSH version detection
- `auxiliary/scanner/http/http_version` - HTTP server detection

**Rate Limit:** 3-5 requests/minute (dynamic)
**Warning:** Use only on authorized systems

---

### 11. **hydra_attack** - Password Brute Forcing
**Purpose:** Network service password brute forcing

**Parameters:**
- `target` (required): Target IP or hostname
- `service` (required): Service type (ssh, ftp, http, etc.)
- `username` (optional): Single username
- `username_file` (optional): Username wordlist
- `password` (optional): Single password
- `password_file` (optional): Password wordlist
- `additional_args` (optional): Extra hydra arguments

**Examples:**
```
"Brute force SSH on 192.168.1.100 with username admin"
"Test FTP login on 10.0.0.50 with common passwords"
```

**Rate Limit:** 4-6 requests/minute (dynamic)
**Warning:** Use only on authorized systems

---

## 🔐 Password Cracking

### 12. **john_crack** - John the Ripper
**Purpose:** Password hash cracking (offline)

**Parameters:**
- `hash_file` (required): Path to hash file
- `wordlist` (optional): Path to wordlist
- `format` (optional): Hash format type
- `additional_args` (optional): Extra john arguments

**Examples:**
```
"Crack hashes in /tmp/hashes.txt using john"
"Use john to crack MD5 hashes with rockyou wordlist"
```

**Rate Limit:** 3-5 requests/minute (dynamic)
**Warning:** Very CPU-intensive

---

### 13. **hashcat_crack** - Hashcat
**Purpose:** GPU-accelerated password hash cracking

**Parameters:**
- `hash_file` (required): Path to hash file
- `wordlist` (optional): Path to wordlist
- `hash_type` (optional): Hash type number
- `attack_mode` (optional): Attack mode (0-9, default: 0)
- `additional_args` (optional): Extra hashcat arguments

**Examples:**
```
"Crack hashes in /tmp/hashes.txt using hashcat"
"Use hashcat with GPU acceleration on MD5 hashes"
```

**Rate Limit:** 2-3 requests/minute (dynamic)
**Warning:** Extremely resource-intensive (requires GPU)

---

## 🛡️ Vulnerability Scanning

### 14. **openvas_scan** - OpenVAS Vulnerability Scanner
**Purpose:** Comprehensive vulnerability assessment

**Parameters:**
- `target` (required): Target IP or hostname
- `scan_config` (optional): Scan configuration (default: "Full and fast")
- `additional_args` (optional): Extra arguments

**Examples:**
```
"Run OpenVAS vulnerability scan on 192.168.1.100"
"Perform full security assessment on 10.0.0.0/24"
```

**Rate Limit:** 3-5 requests/minute (dynamic)
**Warning:** Very resource-intensive, requires GVM setup

---

## 🔧 System Tools

### 15. **server_health** - Health Check
**Purpose:** Check Kali server status, system load, and rate limits

**Parameters:** None

**Examples:**
```
"Check Kali server health"
"Show current system load and rate limits"
"What tools are available?"
```

**Rate Limit:** Unlimited

**Returns:**
- Server status
- Tool availability
- System load (CPU, Memory, I/O)
- Current dynamic rate limits
- Concurrent scan count
- Security features status

---

### 16. **execute_command** - Generic Command Execution
**Purpose:** Execute whitelisted commands directly

**Parameters:**
- `command` (required): Command to execute

**Examples:**
```
"Run command: which nmap"
"Execute: nmap --version"
```

**Rate Limit:** 15-22 requests/minute (dynamic)
**Warning:** Only whitelisted commands allowed

**Allowed Commands:**
- nmap, gobuster, feroxbuster, nikto, sqlmap
- msfconsole, hydra, john, wpscan, enum4linux-ng
- ffuf, amass, hashcat, gvm-cli, which

---

## 📊 Tool Categories Summary

### By Resource Usage

**Very Heavy (2-3 req/min):**
- hashcat_crack
- sqlmap_scan
- metasploit_run
- john_crack
- openvas_scan

**Heavy (6-8 req/min):**
- nmap_scan
- feroxbuster_scan
- ffuf_scan
- amass_scan

**Medium (10-12 req/min):**
- gobuster_scan
- nikto_scan
- wpscan_analyze
- enum4linux_ng_scan

**Light (15+ req/min):**
- execute_command
- server_health

### By Purpose

**Reconnaissance:**
- nmap_scan
- amass_scan
- enum4linux_ng_scan
- server_health

**Web Testing:**
- gobuster_scan
- feroxbuster_scan
- ffuf_scan
- nikto_scan
- wpscan_analyze
- sqlmap_scan

**Exploitation:**
- metasploit_run
- hydra_attack

**Password Cracking:**
- john_crack
- hashcat_crack

**Vulnerability Assessment:**
- openvas_scan
- nikto_scan
- wpscan_analyze

---

## 🚀 Quick Start Examples

### Basic Network Scan
```
"Scan 192.168.1.100 with nmap"
```

### Web Application Testing
```
"Find hidden directories on https://example.com using gobuster"
```

### WordPress Security Check
```
"Scan https://wordpress-site.com for vulnerabilities"
```

### Subdomain Discovery
```
"Find all subdomains for example.com"
```

### Metasploit Scanning
```
"Use Metasploit to check if 192.168.1.100 has SMB vulnerabilities"
```

### Password Testing
```
"Test SSH login on 192.168.1.100 with common passwords"
```

---

## ⚠️ Important Notes

### Rate Limiting
All tools have **dynamic rate limiting** that adjusts based on:
- System CPU load
- Memory usage
- I/O activity
- Tool resource profile

### Concurrent Scans
- Maximum **5 concurrent scans** at once
- Additional requests queued automatically

### Security
- All tools require **API key authentication**
- Commands are **validated and sanitized**
- Paths are **checked for traversal attacks**
- All activity is **logged**

### Legal Warning
⚠️ **Only use these tools on systems you own or have explicit written permission to test!**

Unauthorized access is illegal in most jurisdictions.

---

## 📚 Documentation

For detailed guides on specific tools:
- [Metasploit Guide](information/METASPLOIT_GUIDE.md)
- [Security Features](information/SECURITY.md)
- [Dynamic Rate Limiting](information/DYNAMIC_RATE_LIMITING.md)
- [Rate Limit Guide](information/RATE_LIMIT_GUIDE.md)

---

**Total Tools: 16**
**Total Categories: 6**
**Security Level: Hardened**
**Rate Limiting: Dynamic & Adaptive**
