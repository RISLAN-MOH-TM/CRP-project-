# Kali MCP Server - Setup Guide

## 📋 Prerequisites

### System Requirements
- Kali Linux (or any Linux with penetration testing tools)
- Python 3.8 or higher
- 2GB RAM minimum (4GB recommended)
- Network connectivity

### Required Python Packages
```bash
pip3 install flask requests mcp
```

### Required Tools
Install the penetration testing tools:
```bash
# Update package list
sudo apt update

# Essential tools
sudo apt install -y nmap gobuster nikto sqlmap metasploit-framework \
                    hydra john wpscan

# Modern tools
sudo apt install -y feroxbuster ffuf amass hashcat

# Enum4linux-ng (Python-based)
pip3 install enum4linux-ng

# OpenVAS (optional, requires additional setup)
sudo apt install -y gvm
```

---

## 🔐 Security Setup

### 1. Generate API Key
```bash
# Generate a secure random key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Save it to your environment
echo 'export KALI_API_KEY="YOUR_GENERATED_KEY_HERE"' >> ~/.bashrc
source ~/.bashrc
```

### 2. Configure Allowed Directories
Edit `kali_server.py` if you need custom wordlist locations:
```python
ALLOWED_WORDLIST_DIRS = [
    "/usr/share/wordlists",
    "/usr/share/seclists",
    "/opt/wordlists",
    "/your/custom/path"  # Add your paths here
]
```

---

## 🚀 Installation

### Option 1: Local Setup (Recommended for Testing)

```bash
# Clone or download the files
cd /opt
mkdir kali-mcp-server
cd kali-mcp-server

# Copy your files
cp /path/to/kali_server.py .
cp /path/to/mcp_server.py .

# Make executable
chmod +x kali_server.py mcp_server.py

# Set API key
export KALI_API_KEY="your-secure-key"

# Start Kali API server (Terminal 1)
python3 kali_server.py --ip 127.0.0.1 --port 5000

# Start MCP server (Terminal 2)
python3 mcp_server.py --server http://localhost:5000
```

### Option 2: Network Setup (For Remote Access)

```bash
# On Kali Linux machine
export KALI_API_KEY="your-secure-key"
python3 kali_server.py --ip 0.0.0.0 --port 5000

# On client machine (where AI agent runs)
export KALI_API_KEY="your-secure-key"
python3 mcp_server.py --server http://KALI_IP:5000
```

### Option 3: Systemd Service (Production)

Create `/etc/systemd/system/kali-api-server.service`:
```ini
[Unit]
Description=Kali Linux Tools API Server
After=network.target

[Service]
Type=simple
User=kali
WorkingDirectory=/opt/kali-mcp-server
Environment="KALI_API_KEY=your-secure-key"
Environment="API_PORT=5000"
ExecStart=/usr/bin/python3 /opt/kali-mcp-server/kali_server.py --ip 127.0.0.1 --port 5000
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable kali-api-server
sudo systemctl start kali-api-server
sudo systemctl status kali-api-server
```

---

## 🧪 Testing

### 1. Check Server Health
```bash
curl http://localhost:5000/health
```

Expected response:
```json
{
  "status": "healthy",
  "message": "Kali Linux Tools API Server is running",
  "tools_status": {
    "nmap": true,
    "gobuster": true,
    ...
  },
  "security": {
    "authentication": "enabled",
    "rate_limiting": "enabled",
    "command_validation": "enabled"
  }
}
```

### 2. Test Authentication
```bash
# Without API key (should fail)
curl -X POST http://localhost:5000/api/tools/nmap \
  -H "Content-Type: application/json" \
  -d '{"target": "127.0.0.1"}'

# With API key (should succeed)
curl -X POST http://localhost:5000/api/tools/nmap \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secure-key" \
  -d '{"target": "127.0.0.1", "scan_type": "-sV", "ports": "80,443"}'
```

### 3. Test Rate Limiting
```bash
# Run this multiple times quickly
for i in {1..15}; do
  curl -X POST http://localhost:5000/api/tools/nmap \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your-secure-key" \
    -d '{"target": "127.0.0.1"}'
  echo "Request $i"
done
```

You should see rate limit errors after 10 requests.

---

## 🔧 Configuration Options

### Kali Server Options
```bash
python3 kali_server.py --help

Options:
  --debug          Enable debug mode
  --port PORT      Port for the API server (default: 5000)
  --ip IP          IP address to bind (default: 127.0.0.1)
```

### MCP Server Options
```bash
python3 mcp_server.py --help

Options:
  --server URL     Kali API server URL (default: http://localhost:5000)
  --timeout SEC    Request timeout in seconds (default: 1800)
  --debug          Enable debug logging
```

### Environment Variables
```bash
# Kali Server
export KALI_API_KEY="your-key"        # Required for security
export API_PORT=5000                   # Server port
export DEBUG_MODE=0                    # Debug mode (0 or 1)
export MAX_CONCURRENT_SCANS=5          # Max concurrent operations

# MCP Server
export KALI_API_KEY="your-key"        # Must match server key
```

---

## 🌐 Network Configuration

### Firewall Rules (UFW)
```bash
# Allow from specific IP only
sudo ufw allow from 192.168.1.100 to any port 5000

# Or allow from subnet
sudo ufw allow from 192.168.1.0/24 to any port 5000

# Enable firewall
sudo ufw enable
```

### Reverse Proxy with Nginx (Recommended for Production)

Install nginx:
```bash
sudo apt install nginx
```

Create `/etc/nginx/sites-available/kali-api`:
```nginx
server {
    listen 443 ssl;
    server_name kali-api.yourdomain.com;

    ssl_certificate /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 1800s;
    }
}
```

Enable:
```bash
sudo ln -s /etc/nginx/sites-available/kali-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 📊 Monitoring

### View Logs
```bash
# Real-time logs
tail -f /var/log/kali-server.log

# With systemd
journalctl -u kali-api-server -f

# Filter for errors
journalctl -u kali-api-server -p err
```

### Monitor Performance
```bash
# Check process
ps aux | grep kali_server.py

# Check port
netstat -tulpn | grep 5000

# Check connections
ss -tn | grep 5000
```

---

## 🐛 Troubleshooting

### Issue: "API key required" error
**Solution:** Set the `KALI_API_KEY` environment variable on both server and client.

### Issue: "Command not allowed" error
**Solution:** The tool is not in the `ALLOWED_COMMANDS` whitelist. Add it to `kali_server.py`.

### Issue: "Invalid wordlist path" error
**Solution:** The wordlist is not in an allowed directory. Add the directory to `ALLOWED_WORDLIST_DIRS`.

### Issue: Rate limit exceeded
**Solution:** Wait 60 seconds or adjust rate limits in the code.

### Issue: Connection refused
**Solution:** 
- Check if server is running: `systemctl status kali-api-server`
- Check firewall: `sudo ufw status`
- Verify IP/port: `netstat -tulpn | grep 5000`

### Issue: Tool not found
**Solution:** Install the missing tool:
```bash
sudo apt install <tool-name>
```

---

## 🔄 Updating

```bash
# Stop services
sudo systemctl stop kali-api-server

# Backup current version
cp kali_server.py kali_server.py.backup
cp mcp_server.py mcp_server.py.backup

# Update files
# ... copy new versions ...

# Test
python3 kali_server.py --debug

# Restart services
sudo systemctl start kali-api-server
```

---

## 📚 Example Usage

### Nmap Scan
```python
# Via MCP
nmap_scan(
    target="192.168.1.1",
    scan_type="-sV",
    ports="80,443,8080",
    additional_args="-T4 -Pn"
)
```

### Directory Fuzzing with FFUF
```python
ffuf_scan(
    url="https://example.com/FUZZ",
    wordlist="/usr/share/wordlists/dirb/common.txt",
    max_results=100,
    additional_args="-mc 200,301,302 -fc 404"
)
```

### Password Cracking with Hashcat
```python
hashcat_crack(
    hash_file="/tmp/hashes.txt",
    wordlist="/usr/share/wordlists/rockyou.txt",
    hash_type="1000",  # NTLM
    attack_mode=0
)
```

---

## 🆘 Getting Help

- Check logs for detailed error messages
- Review `SECURITY_IMPROVEMENTS.md` for security details
- Ensure all prerequisites are installed
- Verify network connectivity
- Check firewall rules

---

**Happy Hacking! 🎯**
