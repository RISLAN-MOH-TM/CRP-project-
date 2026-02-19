# Troubleshooting Guide

## Common Issues & Solutions

---

## ❌ Issue: ".env file not found"

### Problem:
- Created `.env` in wrong location
- File named incorrectly (like `.env.txt`)

### Solution:
```powershell
# Check current location
pwd

# Should be in project root, like:
# C:\Users\User\User\Desktop\mcp

# Create .env in correct location
@"
KALI_API_KEY=kali-research-project-2024
KALI_SERVER_IP=192.168.1.100
"@ | Out-File -FilePath ".env" -Encoding UTF8

# Verify
Get-Content .env
```

### Common Mistakes:
- ❌ `C:\Users\User\Desktop\mcp\mcp\.env` (inside virtual env folder)
- ❌ `.env.txt` (has .txt extension)
- ❌ `env` (missing the dot)
- ✅ `C:\Users\User\Desktop\mcp\.env` (CORRECT!)

---

## ❌ Issue: "Cannot connect to Kali server"

### Check 1: Is Kali server running?
**On Kali VM:**
```bash
ps aux | grep kali_server
```

If not running:
```bash
python3 kali_server.py --ip 0.0.0.0 --port 5000
```

### Check 2: Can you ping Kali VM?
**On Windows:**
```powershell
ping 192.168.1.100
```

If ping fails:
- Check VM network settings (use Bridged mode)
- Check Kali VM IP: `ip addr show`

### Check 3: Is firewall blocking?
**On Kali VM:**
```bash
sudo ufw allow 5000
sudo ufw status
```

### Check 4: Correct IP in .env?
**On Windows:**
```powershell
Get-Content .env
```

Should show your Kali VM IP, not `localhost` or `127.0.0.1`

---

## ❌ Issue: "API key required"

### Solution:
Make sure `.env` file has:
```
KALI_API_KEY=kali-research-project-2024
```

And both `kali_server.py` and `mcp_server.py` have the same default key.

---

## ❌ Issue: "Module not found: flask"

### Solution:
**On Kali VM:**
```bash
pip3 install flask requests
```

**On Windows:**
```powershell
pip install requests python-dotenv
```

---

## ❌ Issue: Claude can't see Kali tools

### Check 1: MCP config path correct?
Edit: `C:\Users\YourName\.config\claude-mcp\config.json`

Should have:
```json
{
  "mcpServers": {
    "kali-tools": {
      "command": "python",
      "args": [
        "C:\\Users\\YourName\\Desktop\\mcp\\mcp_server.py",
        "--server", "http://192.168.1.100:5000"
      ],
      "env": {
        "KALI_API_KEY": "kali-research-project-2024"
      }
    }
  }
}
```

### Check 2: Restart Claude
Close and reopen Claude Desktop after config changes.

### Check 3: Test connection manually
```powershell
python mcp_server.py --server http://192.168.1.100:5000
```

---

## ❌ Issue: "python is not recognized"

### Solution:
Install Python from: https://www.python.org/downloads/

**Important:** Check "Add Python to PATH" during installation

Or use full path:
```powershell
C:\Python39\python.exe mcp_server.py
```

---

## ❌ Issue: VMware network issues

### Solution 1: Use Bridged Network
1. VMware → VM Settings → Network Adapter
2. Select "Bridged" mode
3. Restart VM
4. Get new IP: `ip addr show`

### Solution 2: Use NAT with Port Forwarding
1. VMware → VM Settings → Network Adapter → NAT
2. Edit → Virtual Network Editor
3. NAT Settings → Port Forwarding
4. Add: Host Port 5000 → VM Port 5000

---

## ❌ Issue: "Address already in use"

### Solution:
Port 5000 is already used.

**Find what's using it:**
```bash
# On Kali
sudo lsof -i :5000

# On Windows
netstat -ano | findstr :5000
```

**Use different port:**
```bash
python3 kali_server.py --ip 0.0.0.0 --port 5001
```

Update `.env`:
```
KALI_SERVER_IP=192.168.1.100:5001
```

---

## ✅ Quick Diagnostic Commands

### On Kali VM:
```bash
# Check if server is running
ps aux | grep kali_server

# Check IP address
ip addr show

# Check port is listening
sudo netstat -tulpn | grep 5000

# Test locally
curl http://localhost:5000/health
```

### On Windows:
```powershell
# Check .env file
Get-Content .env

# Test connection
curl http://192.168.1.100:5000/health

# Check Python
python --version

# Check packages
pip list | findstr requests
```

---

## 🆘 Still Having Issues?

1. **Check logs** - Look at terminal output for errors
2. **Verify architecture** - See `PROJECT_SETUP.md` diagram
3. **Test step by step** - Follow `HOWTO.md` exactly
4. **Check firewall** - Disable temporarily to test

---

## 📞 Getting Help

When asking for help, provide:
- Error message (exact text)
- What you were trying to do
- Output of diagnostic commands above
- Your OS versions (Windows/Kali)
- Network setup (Bridged/NAT)

---

**Most issues are due to:**
1. `.env` file in wrong location (60%)
2. Wrong Kali VM IP address (20%)
3. Firewall blocking connection (10%)
4. Missing Python packages (10%)
