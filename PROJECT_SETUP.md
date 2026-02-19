# Project Setup - Kali VM + Windows + Claude

## 🏗️ Your Architecture

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

## 📋 Setup Steps

### Part 1: Kali Linux VM Setup

#### Step 1: Install Tools on Kali
```bash
# Update system
sudo apt update

# Install Python packages
pip3 install flask requests

# Install penetration testing tools
sudo apt install -y nmap gobuster feroxbuster nikto sqlmap \
                    metasploit-framework hydra john wpscan \
                    ffuf amass hashcat
pip3 install enum4linux-ng
```

#### Step 2: Copy kali_server.py to Kali VM
Transfer `kali_server.py` to your Kali VM (use shared folder or SCP).

#### Step 3: Set Default API Key on Kali
```bash
# Edit kali_server.py and set a default key
nano kali_server.py
```

Find this line (around line 30):
```python
API_KEY = os.environ.get("KALI_API_KEY")
```

Change it to:
```python
API_KEY = os.environ.get("KALI_API_KEY", "my-research-project-key-2024")
```

This sets a default key so you don't need to generate one each time.

#### Step 4: Get Kali VM IP Address
```bash
ip addr show
# Look for something like: 192.168.xxx.xxx
```

#### Step 5: Start Kali Server
```bash
# Allow connections from Windows host
python3 kali_server.py --ip 0.0.0.0 --port 5000
```

Keep this terminal open!

---

### Part 2: Windows Host Setup

#### Step 1: Install Python Packages
```powershell
pip install requests python-dotenv
```

#### Step 2: Create .env File

**Using PowerShell (Recommended):**
```powershell
# Navigate to project folder
cd C:\Users\User\User\Desktop\mcp

# Create .env file
@"
KALI_API_KEY=kali-research-project-2024
KALI_SERVER_IP=192.168.xxx.xxx
"@ | Out-File -FilePath ".env" -Encoding UTF8

# Verify
Get-Content .env
```

**Using Notepad:**
1. Open Notepad
2. Type:
```
KALI_API_KEY=kali-research-project-2024
KALI_SERVER_IP=192.168.xxx.xxx
```
3. Save As → Navigate to project folder
4. File name: `.env` (with dot!)
5. Save as type: **All Files**
6. Click Save

**Important:**
- File must be `.env` (with dot at start)
- Must be in project root folder
- NOT inside `mcp\mcp\` or virtual environment folder
- Replace `192.168.xxx.xxx` with your Kali VM IP from Part 1, Step 4

#### Step 3: Update mcp_server.py
Edit `mcp_server.py` to use the IP from .env:

Find the line (around line 23):
```python
DEFAULT_KALI_SERVER = "http://localhost:5000"
```

Change to:
```python
DEFAULT_KALI_SERVER = f"http://{os.getenv('KALI_SERVER_IP', 'localhost')}:5000"
```

#### Step 4: Test Connection
```powershell
# Test if you can reach Kali server
curl http://192.168.xxx.xxx:5000/health
```

You should see JSON response.

---

### Part 3: Claude AI Integration

#### Step 1: Find Claude Config
Location: `C:\Users\YourName\.config\claude-mcp\config.json`

#### Step 2: Add MCP Server Config
```json
{
  "mcpServers": {
    "kali-tools": {
      "command": "python",
      "args": [
        "C:\\Users\\YourName\\Desktop\\mcp\\mcp_server.py",
        "--server", "http://192.168.xxx.xxx:5000"
      ],
      "env": {
        "KALI_API_KEY": "my-research-project-key-2024"
      }
    }
  }
}
```

Replace:
- `C:\\Users\\YourName\\Desktop\\mcp\\` with your actual path
- `192.168.xxx.xxx` with your Kali VM IP

#### Step 3: Restart Claude Desktop

#### Step 4: Test with Claude
Ask Claude:
```
Can you check the health of the Kali server?
```

---

## 🎯 Daily Usage

### Starting Your Project

**On Kali VM:**
```bash
python3 kali_server.py --ip 0.0.0.0 --port 5000
```

**On Windows:**
Just open Claude Desktop - it will automatically connect!

Or test manually:
```powershell
python mcp_server.py --server http://192.168.xxx.xxx:5000
```

---

## 🔧 Simplified Files

For your research project, you only need:

### On Kali Linux:
- ✅ `kali_server.py` (with default API key)

### On Windows:
- ✅ `mcp_server.py`
- ✅ `.env` (with API key and Kali IP)

### Documentation (Optional):
- ✅ `README.md` - Project overview
- ✅ `PROJECT_SETUP.md` - This file
- ✅ `SECURITY_IMPROVEMENTS.md` - Security details

---

## 🐛 Troubleshooting

### Can't connect to Kali VM
**Check:**
1. Kali server is running: `ps aux | grep kali_server`
2. Firewall allows port 5000: `sudo ufw allow 5000`
3. VM network is in bridged mode (not NAT)
4. Ping Kali from Windows: `ping 192.168.xxx.xxx`

### Claude can't see tools
**Check:**
1. Claude config has correct path to `mcp_server.py`
2. API key matches in both `.env` and `kali_server.py`
3. Restart Claude Desktop after config changes

### "Connection refused"
**Check:**
1. Kali server is running with `--ip 0.0.0.0` (not 127.0.0.1)
2. Using correct Kali VM IP address
3. Port 5000 is not blocked by firewall

---

## 📝 Example Usage with Claude

Once connected, ask Claude:

```
"Scan 192.168.1.1 with nmap to find open ports"

"Find hidden directories on https://example.com using ffuf"

"Check if this WordPress site has vulnerabilities"

"Run a basic security scan on 10.0.0.1"
```

---

## 🎓 For Your Research Project

This setup allows you to:
- ✅ Run penetration testing tools from Claude AI
- ✅ Keep Kali tools isolated in VM
- ✅ Control everything from Windows
- ✅ Document AI-assisted security testing
- ✅ Demonstrate MCP integration

---

**Your project is ready!** 🎉
