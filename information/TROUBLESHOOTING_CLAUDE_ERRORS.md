# Troubleshooting Claude Retry Errors

## Common "Retry" Errors When Using Claude with MCP

When Claude suddenly shows "Retry" errors while using the Kali MCP server, it's usually one of these issues:

---

## 🔴 Issue 1: MCP Server Connection Lost

### Symptoms
- Claude shows "Retry" button
- Error message: "Failed to connect to MCP server"
- Tools suddenly stop working

### Causes
1. **MCP server process crashed**
2. **Network connection interrupted**
3. **Kali VM went to sleep/suspended**
4. **Port conflict (5000 already in use)**

### Solutions

#### Check if MCP Server is Running
```powershell
# On Windows, check if Python process is running
Get-Process python | Where-Object {$_.Path -like "*mcp_server.py*"}
```

#### Restart MCP Server
```powershell
# Navigate to project directory
cd C:\Users\User\User\Desktop\mcp

# Kill any existing process
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Restart MCP server
python mcp_server.py --server 172.20.10.11:5000
```

#### Check Kali VM Status
```bash
# On Kali VM, check if server is running
ps aux | grep kali_server.py

# Check if port 5000 is listening
netstat -tulpn | grep 5000

# Restart Kali server if needed
python3 kali_server.py --ip 0.0.0.0 --port 5000
```

---

## 🔴 Issue 2: Kali Server Timeout

### Symptoms
- Claude shows "Retry" after long wait
- Error: "Request timeout"
- Happens with heavy scans (nmap, sqlmap, hashcat)

### Causes
1. **Scan taking longer than 30 minutes (default timeout)**
2. **VM resources exhausted**
3. **Network latency**

### Solutions

#### Increase Timeout in mcp_server.py
```python
# Find this line in mcp_server.py
DEFAULT_REQUEST_TIMEOUT = 1800  # 30 minutes

# Change to longer timeout
DEFAULT_REQUEST_TIMEOUT = 3600  # 60 minutes (1 hour)
```

#### Check VM Resources
```bash
# On Kali VM
# Check CPU usage
top -bn1 | head -20

# Check memory
free -h

# Check disk space
df -h

# Kill stuck processes
pkill -9 nmap
pkill -9 sqlmap
pkill -9 hashcat
```

#### Reduce Scan Intensity
```
Instead of: "Scan entire network 192.168.1.0/24 with all ports"
Try: "Scan 192.168.1.1 on common ports only"
```

---

## 🔴 Issue 3: Rate Limit Exceeded

### Symptoms
- Claude shows "Retry" immediately
- Error: "Rate limit exceeded"
- Happens after multiple rapid requests

### Causes
1. **Too many requests too quickly**
2. **System load too high (dynamic limiting)**
3. **Concurrent scan limit reached (5 max)**

### Solutions

#### Check Current Rate Limits
```bash
curl http://172.20.10.11:5000/health
```

Look for:
```json
{
  "system_load": {
    "cpu": "85.2%",  // High load = lower limits
    "memory": "78.5%"
  },
  "dynamic_rate_limits": {
    "nmap": "5 per minute",  // Reduced from 8
    "sqlmap": "2 per minute"  // Reduced from 3
  },
  "concurrent_scans": {
    "max": 5,
    "current": 5  // At maximum!
  }
}
```

#### Wait and Retry
- Wait 60 seconds before retrying
- Check system load has decreased
- Reduce concurrent operations

#### Reduce VM Load
```bash
# On Kali VM, kill unnecessary processes
pkill -9 firefox
pkill -9 burpsuite

# Restart Kali server to clear stuck scans
sudo systemctl restart kali_server  # If using systemd
# OR
pkill -9 -f kali_server.py
python3 kali_server.py --ip 0.0.0.0 --port 5000
```

---

## 🔴 Issue 4: Network Connection Issues

### Symptoms
- Intermittent "Retry" errors
- Error: "Connection refused" or "No route to host"
- Works sometimes, fails other times

### Causes
1. **Firewall blocking connection**
2. **VM network adapter disconnected**
3. **IP address changed**
4. **Windows firewall blocking**

### Solutions

#### Verify Network Connectivity
```powershell
# On Windows, ping Kali VM
ping 172.20.10.11

# Test port 5000
Test-NetConnection -ComputerName 172.20.10.11 -Port 5000

# Test API directly
curl http://172.20.10.11:5000/health
```

#### Check Kali VM Network
```bash
# On Kali VM, check IP address
ip addr show

# Check if server is listening on all interfaces
netstat -tulpn | grep 5000
# Should show: 0.0.0.0:5000 (not 127.0.0.1:5000)

# Test locally
curl http://localhost:5000/health
```

#### Fix Firewall Issues
```bash
# On Kali VM, allow port 5000
sudo ufw allow 5000/tcp
sudo ufw reload

# Or disable firewall temporarily for testing
sudo ufw disable
```

```powershell
# On Windows, allow port 5000
New-NetFirewallRule -DisplayName "Kali MCP" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
```

#### Update .env File if IP Changed
```bash
# Check current Kali IP
ip addr show

# Update .env on Windows
KALI_SERVER_IP=172.20.10.11  # Update this if changed
```

---

## 🔴 Issue 5: Claude Desktop MCP Configuration Issue

### Symptoms
- Claude shows "Retry" on first request
- Error: "MCP server not configured"
- Tools not appearing in Claude

### Causes
1. **MCP configuration file incorrect**
2. **Claude Desktop not restarted after config change**
3. **Python path incorrect**

### Solutions

#### Check MCP Configuration
```powershell
# Open Claude Desktop config
notepad "$env:APPDATA\Claude\claude_desktop_config.json"
```

Should look like:
```json
{
  "mcpServers": {
    "kali-tools": {
      "command": "python",
      "args": [
        "C:\\Users\\User\\User\\Desktop\\mcp\\mcp_server.py",
        "--server",
        "172.20.10.11:5000"
      ],
      "env": {
        "KALI_API_KEY": "kali-research-project-2026"
      }
    }
  }
}
```

#### Verify Python Path
```powershell
# Check Python is in PATH
python --version

# If not found, use full path
"C:\\Python311\\python.exe"
```

#### Restart Claude Desktop
1. Close Claude Desktop completely
2. End process in Task Manager if needed
3. Reopen Claude Desktop
4. Wait for MCP to initialize (check bottom status bar)

---

## 🔴 Issue 6: API Key Authentication Failed

### Symptoms
- Claude shows "Retry" with "401 Unauthorized"
- Error: "Invalid API key"

### Causes
1. **API key mismatch between MCP and Kali server**
2. **API key not set in environment**

### Solutions

#### Verify API Keys Match
```bash
# On Kali VM, check API key
cat .env
# Should show: KALI_API_KEY=kali-research-project-2026

# Check what server is using
grep "DEFAULT_API_KEY" kali_server.py
```

```powershell
# On Windows, check MCP config
Get-Content "$env:APPDATA\Claude\claude_desktop_config.json" | Select-String "KALI_API_KEY"
```

#### Update API Key
```bash
# On Kali VM
echo "KALI_API_KEY=kali-research-project-2026" > .env

# Restart server
python3 kali_server.py --ip 0.0.0.0 --port 5000
```

---

## 🔴 Issue 7: Memory/Resource Exhaustion

### Symptoms
- Claude shows "Retry" after starting heavy scan
- VM becomes unresponsive
- Error: "Service unavailable"

### Causes
1. **VM running out of RAM**
2. **Too many concurrent scans**
3. **Swap space exhausted**

### Solutions

#### Check VM Resources
```bash
# Memory usage
free -h

# Disk usage
df -h

# Running processes
ps aux --sort=-%mem | head -20
```

#### Increase VM Resources
1. Shut down Kali VM
2. In VMware/VirtualBox settings:
   - Increase RAM (recommend 4GB minimum, 8GB better)
   - Increase CPU cores (2-4 cores)
3. Start VM and test

#### Reduce Concurrent Scans
```bash
# Edit kali_server.py
MAX_CONCURRENT_SCANS = 3  # Reduce from 5 to 3
```

#### Add Swap Space
```bash
# On Kali VM, add 4GB swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 🔴 Issue 8: Tool Execution Failed

### Symptoms
- Claude shows "Retry" with specific tool
- Error: "Command failed" or "Tool not found"

### Causes
1. **Tool not installed on Kali VM**
2. **Tool path not in PATH**
3. **Tool requires additional setup**

### Solutions

#### Verify Tool Installation
```bash
# On Kali VM, check if tool exists
which nmap
which sqlmap
which metasploit

# Install missing tools
sudo apt update
sudo apt install -y nmap sqlmap metasploit-framework
```

#### Check Tool Availability
```bash
# Test tool directly
nmap --version
sqlmap --version
msfconsole --version
```

#### Check Health Endpoint
```bash
curl http://172.20.10.11:5000/health
```

Look for:
```json
{
  "tools_status": {
    "nmap": true,
    "sqlmap": false,  // Tool not found!
    "metasploit": true
  }
}
```

---

## 🟢 Quick Diagnostic Checklist

Run these commands to diagnose issues:

### On Windows:
```powershell
# 1. Check MCP server process
Get-Process python

# 2. Test Kali VM connectivity
ping 172.20.10.11
Test-NetConnection -ComputerName 172.20.10.11 -Port 5000

# 3. Test API
curl http://172.20.10.11:5000/health

# 4. Check Claude config
Get-Content "$env:APPDATA\Claude\claude_desktop_config.json"
```

### On Kali VM:
```bash
# 1. Check server process
ps aux | grep kali_server.py

# 2. Check port listening
netstat -tulpn | grep 5000

# 3. Check resources
free -h
df -h
top -bn1 | head -10

# 4. Check logs
tail -f /var/log/kali_server.log  # If logging to file

# 5. Test locally
curl http://localhost:5000/health
```

---

## 🔧 Complete Reset Procedure

If nothing else works, do a complete reset:

### Step 1: Stop Everything
```powershell
# On Windows
Get-Process python | Stop-Process -Force
```

```bash
# On Kali VM
pkill -9 -f kali_server.py
pkill -9 nmap
pkill -9 sqlmap
pkill -9 metasploit
```

### Step 2: Restart Kali Server
```bash
# On Kali VM
cd /path/to/project
python3 kali_server.py --ip 0.0.0.0 --port 5000
```

### Step 3: Verify Kali Server
```bash
# Should see: "Starting Kali Linux Tools API Server on 0.0.0.0:5000"
curl http://localhost:5000/health
```

### Step 4: Restart Claude Desktop
1. Close Claude Desktop
2. End process in Task Manager
3. Reopen Claude Desktop
4. Wait for MCP initialization

### Step 5: Test Connection
```
Ask Claude: "Check the Kali server health"
```

---

## 📊 Error Code Reference

| Error | Meaning | Solution |
|-------|---------|----------|
| 401 | Unauthorized | Check API key |
| 429 | Rate limit exceeded | Wait 60 seconds |
| 500 | Server error | Check Kali server logs |
| 503 | Service unavailable | Too many concurrent scans |
| Timeout | Request took too long | Increase timeout or reduce scan scope |
| Connection refused | Server not running | Start Kali server |
| No route to host | Network issue | Check VM network |

---

## 🆘 Still Having Issues?

### Enable Debug Logging

**kali_server.py:**
```bash
python3 kali_server.py --ip 0.0.0.0 --port 5000 --debug
```

**mcp_server.py:**
```python
# Add at top of file
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Logs
```bash
# On Kali VM
journalctl -u kali_server -f  # If using systemd
# OR
tail -f /var/log/syslog | grep kali
```

### Get Help
1. Check GitHub Issues: https://github.com/RISLAN-MOH-TM/CRP-project-/issues
2. Review documentation in `information/` folder
3. Test with minimal example first

---

## 💡 Prevention Tips

1. **Keep VM resources adequate** (4GB+ RAM, 2+ CPU cores)
2. **Monitor system load** regularly with health checks
3. **Don't run too many scans simultaneously**
4. **Add delays between heavy operations**
5. **Restart servers daily** to clear memory leaks
6. **Keep tools updated** on Kali VM
7. **Use appropriate scan scopes** (don't scan entire internet!)

---

## Summary

Most "Retry" errors are caused by:
1. ⚠️ **Connection issues** (50%) - Check network and servers
2. ⚠️ **Resource exhaustion** (30%) - Check VM resources
3. ⚠️ **Rate limiting** (15%) - Wait and reduce load
4. ⚠️ **Configuration issues** (5%) - Check API keys and config

**Quick Fix:** Restart both Kali server and Claude Desktop, then test with a simple command like "Check server health"
