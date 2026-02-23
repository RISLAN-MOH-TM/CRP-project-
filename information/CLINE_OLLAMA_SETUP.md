# Complete Cline + Ollama Setup Guide 🚀

Detailed step-by-step guide for setting up Cline with Ollama as a free alternative to Claude Desktop.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Installation Steps](#installation-steps)
4. [Configuration](#configuration)
5. [Testing](#testing)
6. [Usage Guide](#usage-guide)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Configuration](#advanced-configuration)

---

## 🎯 Overview

This guide will help you set up:
- **Ollama**: Local AI model server
- **Cline**: VS Code extension for AI assistance
- **MCP Integration**: Connect to Kali penetration testing tools

**Total Setup Time:** 10-15 minutes  
**Cost:** $0 (completely free!)  
**Privacy:** 100% local (no cloud)

---

## 💻 System Requirements

### Minimum Requirements
- **OS:** Windows 10/11, macOS, or Linux
- **RAM:** 8GB (16GB recommended)
- **Disk Space:** 10GB free
- **CPU:** Modern multi-core processor
- **Software:** VS Code installed

### Recommended Requirements
- **RAM:** 16GB+
- **Disk Space:** 20GB+ (for multiple models)
- **GPU:** NVIDIA GPU with CUDA support (optional, for faster inference)

### Model Size vs RAM

| Model | Size | Min RAM | Recommended RAM |
|-------|------|---------|-----------------|
| llama3.1:8b | 4.7GB | 8GB | 12GB |
| mistral:7b | 4.1GB | 8GB | 12GB |
| codellama:7b | 3.8GB | 8GB | 12GB |
| llama3.1:70b | 40GB | 64GB | 80GB |

---

## 🚀 Installation Steps

### Step 1: Install Ollama

#### Windows

1. **Download Ollama:**
   ```
   https://ollama.ai/download
   ```

2. **Run the installer:**
   - Double-click `OllamaSetup.exe`
   - Follow installation wizard
   - Ollama will start automatically

3. **Verify installation:**
   ```powershell
   ollama --version
   ```
   
   Expected output: `ollama version 0.x.x`

#### macOS

```bash
# Using Homebrew
brew install ollama

# Or download from https://ollama.ai/download
```

#### Linux

```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### Step 2: Pull AI Models

```powershell
# Recommended: Fast and capable (4.7GB)
ollama pull llama3.1:8b

# Alternative: Good for coding (3.8GB)
ollama pull codellama:7b

# Alternative: Balanced performance (4.1GB)
ollama pull mistral:7b-instruct
```

**Wait for download to complete** (2-5 minutes depending on internet speed)

### Step 3: Test Ollama

```powershell
# Test the model
ollama run llama3.1:8b "Hello, how are you?"

# Should respond with a greeting
# Press Ctrl+D to exit
```

### Step 4: Install Cline in VS Code

1. **Open VS Code**

2. **Open Extensions:**
   - Press `Ctrl+Shift+X` (Windows/Linux)
   - Press `Cmd+Shift+X` (macOS)

3. **Search for Cline:**
   - Type "Cline" in search box
   - Find "Cline" by Cline
   - Click "Install"

4. **Wait for installation** (30 seconds)

5. **Verify installation:**
   - Press `Ctrl+Shift+P` (Windows/Linux)
   - Press `Cmd+Shift+P` (macOS)
   - Type "Cline"
   - Should see "Cline: Open" option

---

## ⚙️ Configuration

### Step 1: Open VS Code Settings

**Method 1: Keyboard Shortcut**
```
Ctrl+, (Windows/Linux)
Cmd+, (macOS)
```

**Method 2: Menu**
```
File → Preferences → Settings
```

### Step 2: Open settings.json

1. Click the `{}` icon in the top-right corner
2. This opens `settings.json` file

### Step 3: Add Cline Configuration

Add this configuration to `settings.json`:

```json
{
  "cline.apiProvider": "ollama",
  "cline.ollamaModelId": "llama3.1:8b",
  "cline.ollamaBaseUrl": "http://localhost:11434",
  "cline.mcpServers": {
    "kali-tools": {
      "command": "python",
      "args": [
        "C:\\Users\\User\\Desktop\\mcp\\mcp_server.py",
        "--server", "http://172.20.10.11:5000"
      ],
      "env": {
        "KALI_API_KEY": "kali-research-project-2026"
      }
    }
  }
}
```

### Step 4: Customize Paths

**⚠️ IMPORTANT:** Update these values for your system:

1. **Project Path:**
   ```json
   "C:\\Users\\User\\Desktop\\mcp\\mcp_server.py"
   ```
   Replace with YOUR actual project path.
   
   **How to find it:**
   ```powershell
   # In your project directory
   cd C:\path\to\your\project
   pwd
   ```

2. **Kali VM IP:**
   ```json
   "http://172.20.10.11:5000"
   ```
   Replace with YOUR Kali VM IP address.
   
   **How to find it:**
   ```bash
   # On Kali VM
   ip addr show
   # Look for: inet 192.168.x.x or 172.x.x.x
   ```

3. **API Key:**
   ```json
   "KALI_API_KEY": "kali-research-project-2026"
   ```
   Should match the key in your `.env` file.

### Step 5: Save Configuration

1. Press `Ctrl+S` (Windows/Linux) or `Cmd+S` (macOS)
2. Close `settings.json`
3. Restart VS Code (recommended)

---

## 🧪 Testing

### Test 1: Verify Ollama is Running

```powershell
# List installed models
ollama list

# Should show llama3.1:8b
```

### Test 2: Verify Kali Server is Running

```bash
# On Kali VM
python3 kali_server.py --ip 0.0.0.0 --port 5000

# Should show: "Starting Kali Linux Tools API Server"
```

### Test 3: Test Cline Connection

1. **Open Cline:**
   - Press `Ctrl+Shift+P` (Windows/Linux)
   - Press `Cmd+Shift+P` (macOS)
   - Type: "Cline: Open"
   - Press Enter

2. **Test basic functionality:**
   ```
   Hello! Can you introduce yourself?
   ```
   
   Should get a response from the AI.

3. **Test MCP connection:**
   ```
   Check the Kali server health
   ```
   
   Should execute the health check and show results.

### Test 4: Test a Scan

```
Scan 192.168.1.1 with nmap to find open ports
```

Expected behavior:
1. Cline acknowledges the request
2. Executes nmap scan
3. Shows scan results
4. Provides analysis

---

## 📖 Usage Guide

### Basic Commands

#### 1. Server Health Check
```
Check if the Kali server is healthy
```

#### 2. Port Scanning
```
Scan 192.168.1.1 with nmap
Scan 192.168.1.0/24 for live hosts
Find open ports on 192.168.1.100
```

#### 3. Web Vulnerability Scanning
```
Use nikto to scan https://example.com
Check https://example.com for web vulnerabilities
Scan https://wordpress-site.com for WordPress issues
```

#### 4. Directory Enumeration
```
Find hidden directories on https://example.com
Use gobuster to enumerate https://example.com
Discover hidden files on https://target.com
```

#### 5. SQL Injection Testing
```
Test https://example.com/page?id=1 for SQL injection
Use sqlmap on https://example.com/login
Check if https://site.com/search?q=test is vulnerable to SQLi
```

### Advanced Commands

#### 1. Multi-Tool Scanning
```
Run nmap and nikto on 192.168.1.100
Perform a complete web scan on https://example.com using nikto, gobuster, and sqlmap
```

#### 2. Report Generation
```
Scan 192.168.1.100 and generate a professional penetration testing report
Run a full pentest on https://example.com and create a detailed report
```

#### 3. Scan History
```
Show me recent scan history
What scans have been run today?
Retrieve the last nmap scan results
```

### Tips for Better Results

1. **Be specific:**
   ```
   ✅ "Scan 192.168.1.1 ports 80,443,8080 with nmap"
   ❌ "Scan something"
   ```

2. **Provide context:**
   ```
   ✅ "I need to test a WordPress site at https://example.com for vulnerabilities"
   ❌ "Test this site"
   ```

3. **Ask for explanations:**
   ```
   "Scan 192.168.1.1 and explain what each open port means"
   ```

4. **Request specific formats:**
   ```
   "Generate a report in markdown format"
   "Create a summary table of findings"
   ```

---

## 🐛 Troubleshooting

### Issue 1: "Ollama not found"

**Symptoms:**
- Error: "ollama: command not found"
- Cline can't connect to Ollama

**Solutions:**

1. **Restart terminal/PowerShell:**
   ```powershell
   # Close and reopen PowerShell
   ollama --version
   ```

2. **Check if Ollama is running:**
   ```powershell
   # Windows
   Get-Process ollama
   
   # If not running, start it
   ollama serve
   ```

3. **Reinstall Ollama:**
   - Download from https://ollama.ai/download
   - Run installer again

### Issue 2: "Model not found"

**Symptoms:**
- Error: "model 'llama3.1:8b' not found"

**Solutions:**

1. **List installed models:**
   ```powershell
   ollama list
   ```

2. **Pull the model:**
   ```powershell
   ollama pull llama3.1:8b
   ```

3. **Update settings.json:**
   - Make sure `ollamaModelId` matches an installed model

### Issue 3: "Cannot connect to Kali server"

**Symptoms:**
- Error: "Connection refused"
- Health check fails

**Solutions:**

1. **Check Kali server is running:**
   ```bash
   # On Kali VM
   ps aux | grep kali_server
   ```

2. **Start Kali server:**
   ```bash
   python3 kali_server.py --ip 0.0.0.0 --port 5000
   ```

3. **Verify IP address:**
   ```bash
   # On Kali VM
   ip addr show
   ```
   
   Update `settings.json` with correct IP.

4. **Check firewall:**
   ```bash
   # On Kali VM
   sudo ufw allow 5000
   ```

5. **Test connection from Windows:**
   ```powershell
   curl http://172.20.10.11:5000/health
   ```

### Issue 4: "Cline not responding"

**Symptoms:**
- Cline panel is blank
- No response to commands

**Solutions:**

1. **Restart VS Code:**
   - Close VS Code completely
   - Reopen

2. **Check Ollama is running:**
   ```powershell
   ollama list
   ```

3. **Check settings.json syntax:**
   - Look for missing commas
   - Verify JSON is valid
   - Use a JSON validator

4. **Check VS Code output:**
   - View → Output
   - Select "Cline" from dropdown
   - Look for error messages

### Issue 5: "Slow responses"

**Symptoms:**
- Takes 30+ seconds to respond
- System becomes sluggish

**Solutions:**

1. **Use a smaller model:**
   ```powershell
   # Instead of 70b, use 8b
   ollama pull llama3.1:8b
   ```
   
   Update `settings.json`:
   ```json
   "cline.ollamaModelId": "llama3.1:8b"
   ```

2. **Close other applications:**
   - Free up RAM
   - Close browser tabs
   - Stop unnecessary processes

3. **Increase system resources:**
   - Add more RAM
   - Use SSD instead of HDD
   - Enable GPU acceleration (if available)

4. **Optimize Ollama:**
   ```powershell
   # Set environment variables
   $env:OLLAMA_NUM_PARALLEL=1
   $env:OLLAMA_MAX_LOADED_MODELS=1
   ```

### Issue 6: "Rate limit errors"

**Symptoms:**
- Error: "Rate limit exceeded"
- Scans fail after multiple attempts

**Solutions:**

1. **Wait before retrying:**
   - Rate limits reset after 60 seconds
   - Space out your scans

2. **Check rate limit settings:**
   - See `information/RATE_LIMIT_GUIDE.md`
   - Adjust limits in `kali_server.py` if needed

3. **Use scan history:**
   ```
   Show me recent scan history
   ```
   - Retrieve previous results instead of re-scanning

---

## 🔧 Advanced Configuration

### Custom System Prompts

Modify Cline's behavior by adding custom instructions:

```json
{
  "cline.customInstructions": "You are a penetration testing expert specializing in web application security. Focus on OWASP Top 10 vulnerabilities and provide detailed remediation advice."
}
```

### Multiple Models

Configure multiple models for different tasks:

```json
{
  "cline.ollamaModelId": "llama3.1:8b",
  "cline.ollamaAlternativeModels": [
    "codellama:7b",
    "mistral:7b-instruct"
  ]
}
```

### GPU Acceleration

Enable GPU support for faster inference:

```powershell
# Check if GPU is available
ollama run llama3.1:8b --verbose

# Should show: "Using GPU: NVIDIA GeForce..."
```

### Custom MCP Server Settings

Add timeout and retry settings:

```json
{
  "cline.mcpServers": {
    "kali-tools": {
      "command": "python",
      "args": [
        "C:\\path\\to\\mcp_server.py",
        "--server", "http://172.20.10.11:5000",
        "--timeout", "1800"
      ],
      "env": {
        "KALI_API_KEY": "kali-research-project-2026"
      },
      "timeout": 1800000
    }
  }
}
```

### Keyboard Shortcuts

Add custom keyboard shortcuts for Cline:

1. **Open Keyboard Shortcuts:**
   - Press `Ctrl+K Ctrl+S` (Windows/Linux)
   - Press `Cmd+K Cmd+S` (macOS)

2. **Search for "Cline"**

3. **Add shortcuts:**
   - `Ctrl+Alt+C`: Open Cline
   - `Ctrl+Alt+H`: Check server health
   - `Ctrl+Alt+S`: Show scan history

---

## 📚 Additional Resources

### Documentation
- **Ollama Docs:** https://ollama.ai/docs
- **Cline GitHub:** https://github.com/cline/cline
- **MCP Protocol:** https://modelcontextprotocol.io

### Model Library
- **Ollama Models:** https://ollama.ai/library
- **Hugging Face:** https://huggingface.co/models

### Community
- **Ollama Discord:** https://discord.gg/ollama
- **Cline Discussions:** https://github.com/cline/cline/discussions

---

## 🎯 Next Steps

1. **Explore different models:**
   ```powershell
   ollama pull mistral:7b-instruct
   ollama pull codellama:7b
   ```

2. **Try the custom Python client:**
   ```powershell
   python ollama_client.py
   ```

3. **Read advanced guides:**
   - `information/OLLAMA_INTEGRATION.md`
   - `information/RATE_LIMIT_GUIDE.md`
   - `information/METASPLOIT_GUIDE.md`

4. **Automate your workflow:**
   - Create custom scripts
   - Set up CI/CD integration
   - Build automated scanning pipelines

---

## ✅ Checklist

- [ ] Ollama installed and tested
- [ ] Model downloaded (llama3.1:8b)
- [ ] Cline extension installed
- [ ] settings.json configured
- [ ] Paths updated correctly
- [ ] Kali server running
- [ ] Connection test successful
- [ ] First scan completed
- [ ] Scan history working

---

**Congratulations! You now have a fully functional, free, and private AI-powered penetration testing setup!** 🎉

**Stay Ethical. Stay Legal. Stay Secure.** 🛡️
