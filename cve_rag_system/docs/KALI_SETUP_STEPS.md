# Kali VM Setup Steps for CVE RAG Integration

## 🐧 What Runs on Kali VM

- **Kali API Server** (`kali_server.py`)
- **18 Penetration Testing Tools** (nmap, nikto, sqlmap, metasploit, etc.)
- **Scan Execution** (all security tools run here)

## 🎯 The Good News

**NO CHANGES NEEDED ON KALI VM!** 🎉

The CVE RAG integration runs entirely on Windows. Your Kali VM continues to work exactly as before.

## 📋 What Stays the Same

### 1. Kali API Server
```bash
# Start the server (same as before)
python3 kali_server.py

# Or with custom settings
python3 kali_server.py --host 0.0.0.0 --port 5000
```

### 2. All 18 Tools Work Unchanged
- nmap
- nikto
- sqlmap
- metasploit
- gobuster
- feroxbuster
- hydra
- john
- wpscan
- enum4linux-ng
- ffuf
- amass
- hashcat
- nuclei
- masscan
- subfinder
- searchsploit
- whatweb

### 3. API Endpoints Unchanged
All existing endpoints continue to work:
- `/api/tools/nmap`
- `/api/tools/nikto`
- `/api/tools/sqlmap`
- etc.

## 🔍 How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    WINDOWS MACHINE                           │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Claude AI                                          │    │
│  └────────────────┬───────────────────────────────────┘    │
│                   │                                          │
│                   ▼                                          │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Enhanced MCP Server                                │    │
│  │  • 18 Kali tools (via API)                         │    │
│  │  • 5 CVE tools (local search)                      │    │
│  └────────────────┬───────────────────────────────────┘    │
│                   │                                          │
│                   │ HTTP API Calls (no changes)             │
└───────────────────┼──────────────────────────────────────────┘
                    │
                    │ Network (10.190.250.244:5000)
                    │
┌───────────────────▼──────────────────────────────────────────┐
│                    KALI VM                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Kali API Server (kali_server.py)                  │    │
│  │  • Receives scan requests                          │    │
│  │  • Executes tools                                  │    │
│  │  • Returns results                                 │    │
│  └────────────────┬───────────────────────────────────┘    │
│                   │                                          │
│                   ▼                                          │
│  ┌────────────────────────────────────────────────────┐    │
│  │  18 Penetration Testing Tools                      │    │
│  │  (nmap, nikto, sqlmap, metasploit, etc.)          │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## ✅ Verification Steps (Optional)

### 1. Check Kali Server is Running
```bash
# On Kali VM
curl http://localhost:5000/health
```

### 2. Test from Windows
```bash
# On Windows
curl http://10.190.250.244:5000/health
```

### 3. Test a Tool
```python
# In Claude
nmap_scan("192.168.1.1", scan_type="-sV")
# This still works exactly as before!
```

## 📊 Resource Usage

### Current Setup (Recommended)
```
Windows:
- MCP Server: 200 MB RAM
- CVE RAG: 2-3 GB RAM
- Vector DB: 3-6 GB disk
- Total: ~3 GB RAM, 6 GB disk

Kali VM:
- API Server: 100 MB RAM
- Tools: 500 MB RAM (during scans)
- Total: ~600 MB RAM
```

## 🎯 Summary

### What Changes on Kali VM?
**NOTHING!** ✅

### What Changes on Windows?
- ✅ Install RAG dependencies
- ✅ Add CVE data
- ✅ Build vector database
- ✅ Use enhanced MCP server (optional)

### What Stays the Same?
- ✅ Kali API server
- ✅ All 18 tools
- ✅ All API endpoints
- ✅ Network configuration
- ✅ Authentication
- ✅ Everything else!

## 🚀 Quick Verification

```bash
# On Kali VM - Check server is running
python3 kali_server.py

# On Windows - Test connection
curl http://10.190.250.244:5000/health

# In Claude - Test a tool
nmap_scan("192.168.1.1")

# In Claude - Test CVE RAG (new!)
search_cve_database("SQL injection")
```

## ✅ Checklist for Kali VM

- [ ] Kali API server running (`python3 kali_server.py`)
- [ ] Server accessible from Windows
- [ ] All 18 tools installed and working
- [ ] Firewall allows port 5000
- [ ] IP address is 10.190.250.244

**That's it! No other changes needed on Kali VM.**

## 🎉 You're Done!

Your Kali VM:
- ✅ Continues to work exactly as before
- ✅ No new dependencies needed
- ✅ No configuration changes
- ✅ All 18 tools still available
- ✅ API server unchanged

**All the CVE RAG magic happens on Windows!** 🪟✨
