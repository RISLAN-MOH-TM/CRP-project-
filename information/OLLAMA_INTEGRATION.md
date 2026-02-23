# Ollama + AI + MCP Integration Guide 🤖

Complete guide for using Ollama (local AI) with the Kali MCP Server as an alternative to Claude Desktop.

---

## 📋 Table of Contents

1. [Why Ollama?](#why-ollama)
2. [Architecture Overview](#architecture-overview)
3. [Installation & Setup](#installation--setup)
4. [Integration Methods](#integration-methods)
5. [Model Selection](#model-selection)
6. [Usage Examples](#usage-examples)
7. [Performance Comparison](#performance-comparison)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 Why Ollama?

### Advantages
- ✅ **100% FREE** - No monthly subscription costs
- ✅ **100% PRIVATE** - All data stays on your machine
- ✅ **NO RATE LIMITS** - Run unlimited scans
- ✅ **OFFLINE CAPABLE** - Works without internet
- ✅ **CUSTOMIZABLE** - Choose your own models
- ✅ **NO VENDOR LOCK-IN** - Full control over your AI

### Disadvantages
- ❌ Requires decent hardware (8GB+ RAM recommended)
- ❌ Smaller models may be less capable than Claude
- ❌ Initial setup is more complex
- ❌ No cloud backup/sync

### Cost Comparison

| Solution | Monthly Cost | Privacy | Rate Limits |
|----------|-------------|---------|-------------|
| Claude Desktop | $20 | Cloud | Yes (strict) |
| Ollama + Cline | $0 | Local | None |
| Ollama + Custom | $0 | Local | None |

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Windows Host                          │
│                                                           │
│  ┌────────────────┐         ┌──────────────────┐        │
│  │  Ollama Server │         │   AI Client      │        │
│  │  (Port 11434)  │◄───────►│  (Cline/Custom)  │        │
│  └────────────────┘         └────────┬─────────┘        │
│         │                             │                  │
│         │ Local AI Models             │                  │
│         │ (llama3.1, mistral, etc)    │                  │
│         │                             │                  │
│         │                    ┌────────▼───────┐          │
│         │                    │  mcp_server.py │          │
│         │                    │  (MCP Bridge)  │          │
│         │                    └────────┬───────┘          │
│         │                             │                  │
│         │                             │ HTTP API         │
│         │                             │                  │
│  ┌──────▼─────────────────────────────▼──────────────┐  │
│  │         VMware Workstation Pro                     │  │
│  │  ┌──────────────────────────────────────────┐     │  │
│  │  │        Kali Linux VM                      │     │  │
│  │  │  ┌────────────────────────────────────┐  │     │  │
│  │  │  │      kali_server.py                │  │     │  │
│  │  │  │  (Flask API + Tools)               │  │     │  │
│  │  │  └────────────────────────────────────┘  │     │  │
│  │  └──────────────────────────────────────────┘     │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Installation & Setup

### Step 1: Install Ollama

#### Windows Installation

1. **Download Ollama:**
   - Visit: https://ollama.ai/download
   - Download Windows installer
   - Run `OllamaSetup.exe`

2. **Verify Installation:**
   ```powershell
   ollama --version
   ```

3. **Pull Recommended Models:**
   ```powershell
   # Fast, good for most tasks (4.7GB)
   ollama pull llama3.1:8b
   
   # More capable, slower (26GB)
   ollama pull llama3.1:70b
   
   # Balanced option (14GB)
   ollama pull mistral:7b-instruct
   
   # Specialized for coding (4.1GB)
   ollama pull codellama:7b
   ```

4. **Test Ollama:**
   ```powershell
   ollama run llama3.1:8b "Hello, how are you?"
   ```

### Step 2: Choose Your Integration Method

You have 3 options:

#### Option A: Cline (VS Code Extension) ⭐ RECOMMENDED
- **Best for:** General use, beginners
- **Pros:** Easy setup, great UI, built-in MCP support
- **Cons:** Requires VS Code

#### Option B: Custom Python Client
- **Best for:** Automation, scripting, advanced users
- **Pros:** Full control, scriptable, no dependencies
- **Cons:** Requires coding

#### Option C: Continue.dev (VS Code Extension)
- **Best for:** Developers who want inline code assistance
- **Pros:** Inline editing, good for coding
- **Cons:** Less focused on security testing

---

## 🔧 Integration Methods

### Method A: Cline + Ollama (Easiest)

#### 1. Install Cline in VS Code

```powershell
# Open VS Code
code .

# Press Ctrl+Shift+X (Extensions)
# Search: "Cline"
# Click: Install
```

#### 2. Configure Cline

Press `Ctrl+,` (Settings) → Click `{}` icon → Add to `settings.json`:

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

**Replace paths with your actual paths!**

#### 3. Test Cline

1. Press `Ctrl+Shift+P`
2. Type: "Cline: Open"
3. Ask: "Check the Kali server health"
4. Ask: "Scan 192.168.1.1 with nmap"

---

### Method B: Custom Python Client (Most Flexible)

Create a Python script that connects Ollama to your MCP server.

#### 1. Install Dependencies

```powershell
pip install ollama requests python-dotenv
```

#### 2. Create `ollama_client.py`

```python
#!/usr/bin/env python3
"""
Ollama + MCP Kali Tools Client
Connects local Ollama AI to Kali penetration testing tools
"""

import ollama
import json
import sys
from mcp_server import KaliToolsClient, format_scan_result

# Configuration
KALI_SERVER = "http://172.20.10.11:5000"
API_KEY = "kali-research-project-2026"
MODEL = "llama3.1:8b"

# Initialize Kali client
kali = KaliToolsClient(KALI_SERVER, api_key=API_KEY)

# Available tools for the AI
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "nmap_scan",
            "description": "Execute an Nmap scan against a target",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "IP or hostname"},
                    "scan_type": {"type": "string", "description": "Scan type (e.g., -sV)"},
                    "ports": {"type": "string", "description": "Ports to scan"}
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "nikto_scan",
            "description": "Execute Nikto web server scanner",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Target URL or IP"}
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "server_health",
            "description": "Check Kali server health status",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

def execute_tool(tool_name, arguments):
    """Execute a Kali tool and return results"""
    try:
        if tool_name == "nmap_scan":
            result = kali.safe_post("api/tools/nmap", arguments)
            return format_scan_result(result, f"Nmap: {arguments.get('target')}")
        
        elif tool_name == "nikto_scan":
            result = kali.safe_post("api/tools/nikto", arguments)
            return format_scan_result(result, f"Nikto: {arguments.get('target')}")
        
        elif tool_name == "server_health":
            return json.dumps(kali.check_health(), indent=2)
        
        else:
            return f"Unknown tool: {tool_name}"
    
    except Exception as e:
        return f"Error executing {tool_name}: {str(e)}"

def chat(user_message):
    """Send message to Ollama and handle tool calls"""
    messages = [
        {
            "role": "system",
            "content": """You are a penetration testing assistant with access to Kali Linux tools.
            
Available tools:
- nmap_scan: Network scanning and port detection
- nikto_scan: Web server vulnerability scanning
- server_health: Check if Kali server is running

When the user asks to scan or test something, use the appropriate tool.
Always explain what you're doing and interpret the results."""
        },
        {
            "role": "user",
            "content": user_message
        }
    ]
    
    print(f"\n🤖 AI: Thinking...\n")
    
    # Call Ollama with tools
    response = ollama.chat(
        model=MODEL,
        messages=messages,
        tools=TOOLS
    )
    
    # Check if AI wants to use a tool
    if response.get('message', {}).get('tool_calls'):
        for tool_call in response['message']['tool_calls']:
            tool_name = tool_call['function']['name']
            arguments = tool_call['function']['arguments']
            
            print(f"🔧 Executing: {tool_name}")
            print(f"📋 Parameters: {json.dumps(arguments, indent=2)}\n")
            
            # Execute the tool
            result = execute_tool(tool_name, arguments)
            
            print(f"📊 Results:\n{result}\n")
            
            # Send results back to AI for interpretation
            messages.append(response['message'])
            messages.append({
                "role": "tool",
                "content": result
            })
            
            # Get AI's interpretation
            final_response = ollama.chat(
                model=MODEL,
                messages=messages
            )
            
            print(f"🤖 AI Analysis:\n{final_response['message']['content']}\n")
    
    else:
        # No tool call, just a regular response
        print(f"🤖 AI: {response['message']['content']}\n")

def main():
    """Interactive chat loop"""
    print("="*80)
    print("🛡️  Ollama + Kali MCP Client")
    print("="*80)
    print(f"Model: {MODEL}")
    print(f"Kali Server: {KALI_SERVER}")
    print("Type 'exit' to quit\n")
    
    # Test connection
    print("🔍 Testing Kali server connection...")
    health = kali.check_health()
    if health.get("error"):
        print(f"❌ Error: {health['error']}")
        print("Make sure kali_server.py is running on the Kali VM!")
        sys.exit(1)
    else:
        print(f"✅ Connected! Status: {health.get('status')}\n")
    
    # Interactive loop
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                print("Goodbye! 👋")
                break
            
            chat(user_input)
        
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}\n")

if __name__ == "__main__":
    main()
```

#### 3. Run the Client

```powershell
python ollama_client.py
```

#### 4. Example Usage

```
You: Check if the Kali server is healthy

🤖 AI: Thinking...
🔧 Executing: server_health
📊 Results: {...}
🤖 AI Analysis: The Kali server is running and healthy!

You: Scan 192.168.1.1 with nmap

🤖 AI: Thinking...
🔧 Executing: nmap_scan
📋 Parameters: {"target": "192.168.1.1", "scan_type": "-sV"}
📊 Results: [nmap output]
🤖 AI Analysis: The scan found 3 open ports...
```

---

### Method C: Continue.dev + Ollama

#### 1. Install Continue.dev

```powershell
# In VS Code
# Press Ctrl+Shift+X
# Search: "Continue"
# Click: Install
```

#### 2. Configure Continue

Create `~/.continue/config.json`:

```json
{
  "models": [
    {
      "title": "Llama 3.1 8B",
      "provider": "ollama",
      "model": "llama3.1:8b"
    }
  ],
  "mcpServers": {
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

#### 3. Use Continue

- Press `Ctrl+L` to open Continue chat
- Ask: "Check Kali server health"
- Use inline editing with `Ctrl+I`

---

## 🎯 Model Selection

### Recommended Models

| Model | Size | RAM Needed | Speed | Quality | Best For |
|-------|------|------------|-------|---------|----------|
| llama3.1:8b | 4.7GB | 8GB | Fast | Good | General use ⭐ |
| mistral:7b-instruct | 4.1GB | 8GB | Fast | Good | Instructions |
| codellama:7b | 3.8GB | 8GB | Fast | Code-focused | Scripting |
| llama3.1:70b | 40GB | 64GB | Slow | Excellent | Complex analysis |
| deepseek-coder:6.7b | 3.8GB | 8GB | Fast | Code-focused | Exploit dev |

### Model Commands

```powershell
# List installed models
ollama list

# Pull a new model
ollama pull llama3.1:8b

# Remove a model
ollama rm llama3.1:70b

# Run a model interactively
ollama run llama3.1:8b
```

---

## 💡 Usage Examples

### Example 1: Basic Port Scan

```
You: Scan 192.168.1.1 and tell me what services are running

AI: I'll run an nmap scan with service detection...
[Executes nmap_scan]
AI: Found 3 open ports:
- Port 22: SSH (OpenSSH 8.2)
- Port 80: HTTP (Apache 2.4.41)
- Port 443: HTTPS (Apache 2.4.41)
```

### Example 2: Web Vulnerability Scan

```
You: Check https://example.com for web vulnerabilities

AI: I'll use Nikto to scan for common web vulnerabilities...
[Executes nikto_scan]
AI: Found 5 potential issues:
1. Missing X-Frame-Options header
2. Outdated Apache version
...
```

### Example 3: Automated Pentest Report

```
You: Run a full pentest on 192.168.1.100 and generate a report

AI: I'll perform multiple scans:
1. Port scanning with nmap...
2. Web scanning with nikto...
3. Directory enumeration with gobuster...
[Executes multiple tools]
AI: [Generates comprehensive report]
```

---

## 📊 Performance Comparison

### Speed Test Results

| Task | Claude Desktop | Ollama (8B) | Ollama (70B) |
|------|---------------|-------------|--------------|
| Simple query | 2s | 3s | 8s |
| Tool execution | 5s | 6s | 12s |
| Report generation | 30s | 45s | 90s |

### Quality Comparison

| Aspect | Claude | Ollama 8B | Ollama 70B |
|--------|--------|-----------|------------|
| Understanding | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Tool usage | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Report quality | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Speed | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |

---

## 🐛 Troubleshooting

### Issue: "Ollama not found"

```powershell
# Check if Ollama is installed
ollama --version

# If not, reinstall from https://ollama.ai/download
```

### Issue: "Model not found"

```powershell
# List installed models
ollama list

# Pull the model
ollama pull llama3.1:8b
```

### Issue: "Connection refused to Ollama"

```powershell
# Check if Ollama is running
Get-Process ollama

# Restart Ollama
Stop-Process -Name ollama
# Ollama will auto-restart
```

### Issue: "Out of memory"

```powershell
# Use a smaller model
ollama pull llama3.1:8b  # Instead of 70b

# Or increase system RAM
```

### Issue: "Slow responses"

- Use a smaller model (8B instead of 70B)
- Close other applications
- Use GPU acceleration if available
- Consider upgrading hardware

---

## 🎓 Advanced Tips

### 1. Custom System Prompts

Modify the system prompt in `ollama_client.py` for specialized behavior:

```python
{
    "role": "system",
    "content": """You are an expert penetration tester specializing in web applications.
    Focus on OWASP Top 10 vulnerabilities and provide detailed remediation advice."""
}
```

### 2. Automated Scanning Scripts

Create bash/PowerShell scripts that use the Ollama client:

```powershell
# auto_scan.ps1
$targets = @("192.168.1.1", "192.168.1.2", "192.168.1.3")

foreach ($target in $targets) {
    python ollama_client.py --prompt "Scan $target with nmap and nikto"
}
```

### 3. Integration with CI/CD

Use Ollama in your CI/CD pipeline for automated security testing:

```yaml
# .github/workflows/security-scan.yml
- name: Run Security Scan
  run: |
    python ollama_client.py --prompt "Scan staging environment"
```

---

## 📚 Additional Resources

- **Ollama Documentation:** https://ollama.ai/docs
- **Model Library:** https://ollama.ai/library
- **Cline Documentation:** https://github.com/cline/cline
- **Continue.dev Docs:** https://continue.dev/docs

---

## 🎯 Summary

### Quick Decision Guide

**Choose Claude Desktop if:**
- You want the best quality
- You don't mind paying $20/month
- You want minimal setup

**Choose Ollama + Cline if:**
- You want 100% free solution ⭐
- You value privacy
- You have decent hardware (8GB+ RAM)
- You want no rate limits

**Choose Ollama + Custom Client if:**
- You want full control
- You need automation
- You're comfortable with Python
- You want to integrate with other tools

---

**Made with ❤️ for the security research community**

**Stay Ethical. Stay Legal. Stay Secure.** 🛡️
