# How To Run - Simple Steps

## Your Setup
- Kali Linux in VMware
- Windows host with VS Code
- Claude AI Desktop

---

## Step 1: On Kali Linux VM

```bash
# Install Python packages using apt (Kali's package manager)
sudo apt update
sudo apt install -y python3-flask python3-requests

# Install penetration testing tools
sudo apt install -y nmap gobuster feroxbuster nikto sqlmap \
                    metasploit-framework hydra john wpscan \
                    ffuf amass hashcat

# Install enum4linux-ng (not in apt repository)
pip3 install enum4linux-ng --break-system-packages

# Start server (allow connections from Windows)
python3 kali_server.py --ip 0.0.0.0 --port 5000
```

**Keep this terminal open!**

---

## Step 2: Get Kali VM IP

```bash
ip addr show
# Note the IP (example: 192.168.1.100)
```

---

## Step 3: On Windows - Create .env File

### Option A: Using PowerShell (Recommended)
```powershell
# Navigate to your project folder
cd C:\Users\User\User\Desktop\mcp

# Create .env file
@"
KALI_API_KEY=kali-research-project-2024
KALI_SERVER_IP=192.168.1.100
"@ | Out-File -FilePath ".env" -Encoding UTF8

# Verify it was created
Get-Content .env
```

### Option B: Using Notepad
1. Open Notepad
2. Type exactly this:
```
KALI_API_KEY=kali-research-project-2024
KALI_SERVER_IP=192.168.1.100
```
3. Click File → Save As
4. Navigate to: `C:\Users\User\User\Desktop\mcp`
5. File name: `.env` (include the dot!)
6. Save as type: **All Files** (NOT Text Documents)
7. Click Save

**Important:** 
- File must be named `.env` (with dot at start)
- Must be in project root folder, NOT inside `mcp\mcp\` subfolder
- Replace `192.168.1.100` with your actual Kali VM IP from Step 2

---

## Step 4: Configure Claude

Edit: `C:\Users\YourName\.config\claude-mcp\config.json`

```json
{
  "mcpServers": {
    "kali-tools": {
      "command": "python",
      "args": [
        "C:\\path\\to\\mcp_server.py",
        "--server", "http://192.168.1.100:5000"
      ],
      "env": {
        "KALI_API_KEY": "kali-research-project-2024"
      }
    }
  }
}
```

---

## Step 5: Restart Claude & Test

Ask Claude:
```
"Check the Kali server health"
```

---

## Done! 🎉

For detailed setup, see `PROJECT_SETUP.md`
