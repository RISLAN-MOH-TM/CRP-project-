# Persistence Features - Never Lose Your Work Again!

## Overview

Your MCP server now has **automatic scan logging** and **result persistence** to prevent data loss when Claude crashes or restarts.

## ✅ What's Implemented

### 1. Automatic Scan Logging
- Every scan automatically logged to `/opt/scans/logs/` on Kali VM
- Logs include: scan ID, tool, parameters, timestamps, status, results
- Survives crashes, restarts, and network issues

### 2. Automatic Result Saving (JSON FORMAT!)
- **ALL scan results automatically saved** to `./results/` directory as JSON files
- **Saves for BOTH successful AND failed scans**
- **Stores RAW output** (stdout/stderr) in JSON format
- Files named: `{tool}_{target}_{timestamp}.json`
- Includes metadata: success status, return code, timestamps, scan ID
- Persists even if Claude crashes
- **Machine readable** - Easy to parse and process

### 3. Recovery Tools
- `get_scan_history()` - View recent scans
- `get_scan_details(scan_id)` - Get full scan information
- Works immediately after crash/restart

## 📄 JSON Result File Format

Results are now saved as **JSON files** with **raw output** and **metadata**:

**Filename:** `{tool}_{target}_{timestamp}.json`

**Example:** `nmap_192.168.1.100_20260223_143022.json`

```json
{
  "tool": "nmap",
  "target": "192.168.1.100",
  "timestamp": "20260223_143022",
  "datetime": "2026-02-23T14:30:22.123456",
  "success": true,
  "return_code": 0,
  "stdout": "Starting Nmap 7.98 ( https://nmap.org ) at 2026-02-23 14:30 EST\nNmap scan report for 192.168.1.100\nHost is up (0.0012s latency).\nPORT     STATE SERVICE    VERSION\n22/tcp   open  ssh        OpenSSH 8.2p1\n80/tcp   open  http       Apache httpd 2.4.41\n443/tcp  open  ssl/https  Apache httpd 2.4.41\n\nNmap done: 1 IP address (1 host up) scanned in 12.34 seconds",
  "stderr": "",
  "error": null,
  "timed_out": false,
  "partial_results": false,
  "rate_limited": false,
  "retry_after": null,
  "concurrent_limit_reached": false,
  "scan_id": "nmap_20260223_143022_192_168_1_100",
  "status_code": null,
  "parsed_output": null
}
```

### Failed Scan Example:

**Filename:** `sqlmap_example.com_20260223_143500.json`

```json
{
  "tool": "sqlmap",
  "target": "https://example.com/login",
  "timestamp": "20260223_143500",
  "datetime": "2026-02-23T14:35:00.123456",
  "success": false,
  "return_code": 1,
  "stdout": "[14:35:00] [INFO] testing connection to the target URL\n[14:35:15] [WARNING] target URL is not responding\n[14:35:30] [CRITICAL] unable to connect to the target URL",
  "stderr": "sqlmap: error: connection timeout\nCheck your network connection and target availability",
  "error": "Connection timeout after 30 seconds",
  "timed_out": false,
  "partial_results": false,
  "rate_limited": false,
  "retry_after": null,
  "concurrent_limit_reached": false,
  "scan_id": "sqlmap_20260223_143500_192_168_1_50",
  "status_code": null,
  "parsed_output": null
}
```

### Rate Limited Scan Example:

**Filename:** `nuclei_target.com_20260223_143600.json`

```json
{
  "tool": "nuclei",
  "target": "https://target.com",
  "timestamp": "20260223_143600",
  "datetime": "2026-02-23T14:36:00.123456",
  "success": false,
  "return_code": null,
  "stdout": "",
  "stderr": "",
  "error": "Rate limit exceeded. Please wait before retrying.",
  "timed_out": false,
  "partial_results": false,
  "rate_limited": true,
  "retry_after": "60 seconds",
  "concurrent_limit_reached": false,
  "scan_id": null,
  "status_code": 429,
  "parsed_output": null
}
```

### Benefits of JSON Format:

1. ✅ **Easy to parse** - Use `json.load()` in Python
2. ✅ **Machine readable** - Import into other tools
3. ✅ **Structured data** - All fields clearly labeled
4. ✅ **Query with jq** - `jq '.stdout' file.json`
5. ✅ **Database import** - Load into MongoDB, PostgreSQL, etc.
6. ✅ **Automation friendly** - Process with scripts
7. ✅ **Version control** - Git diffs work well with JSON

## 🚀 Setup Instructions

### On Kali VM:

```bash
# 1. Create logs directory
sudo mkdir -p /opt/scans/logs
sudo chmod 777 /opt/scans/logs

# 2. Restart Kali server
python3 kali_server.py --ip 0.0.0.0 --port 5000
```

### On Windows:

```powershell
# 1. Results directory created automatically
# Located at: C:\Users\User\User\Desktop\mcp\results\

# 2. Restart Claude Desktop
# Close completely and reopen
```

## 📖 Usage Examples

### Parse JSON Results with Python:

```python
import json

# Read a scan result
with open('results/nmap_192.168.1.100_20260223_143022.json', 'r') as f:
    scan = json.load(f)

# Access data
print(f"Tool: {scan['tool']}")
print(f"Target: {scan['target']}")
print(f"Success: {scan['success']}")
print(f"Output:\n{scan['stdout']}")

# Check if scan failed
if not scan['success']:
    print(f"Error: {scan['error']}")
    print(f"Stderr: {scan['stderr']}")
```

### Query with jq (Linux/Mac):

```bash
# Get stdout from all nmap scans
jq '.stdout' results/nmap_*.json

# Find all failed scans
jq 'select(.success == false)' results/*.json

# Get all targets scanned
jq '.target' results/*.json

# Find rate-limited scans
jq 'select(.rate_limited == true)' results/*.json

# Extract specific fields
jq '{tool: .tool, target: .target, success: .success}' results/*.json
```

### Process Multiple Results:

```python
import json
import glob

# Load all scan results
results = []
for filepath in glob.glob('results/*.json'):
    with open(filepath, 'r') as f:
        results.append(json.load(f))

# Find all successful scans
successful = [r for r in results if r['success']]
print(f"Successful scans: {len(successful)}")

# Find all failed scans
failed = [r for r in results if not r['success']]
print(f"Failed scans: {len(failed)}")

# Group by tool
from collections import defaultdict
by_tool = defaultdict(list)
for r in results:
    by_tool[r['tool']].append(r)

for tool, scans in by_tool.items():
    print(f"{tool}: {len(scans)} scans")
```

### After Claude Crashes:

**1. Check what you were working on:**
```
"Show me the recent scan history"
```

**2. Parse results programmatically:**
```powershell
# On Windows with PowerShell
Get-ChildItem results\*.json | ForEach-Object {
    $data = Get-Content $_.FullName | ConvertFrom-Json
    [PSCustomObject]@{
        Tool = $data.tool
        Target = $data.target
        Success = $data.success
        Timestamp = $data.datetime
    }
} | Format-Table
```

## 🔍 How It Works

### Scan Logging Flow:

```
1. User requests scan via Claude
   ↓
2. MCP server sends request to Kali API
   ↓
3. Kali server logs request to /opt/scans/logs/{scan_id}.json
   ↓
4. Scan executes
   ↓
5. Kali server updates log with results
   ↓
6. MCP server receives results (success OR failure)
   ↓
7. MCP server saves RAW JSON to ./results/{tool}_{target}_{timestamp}.json
   ↓
8. Claude displays results with file location and scan ID
```

## 💾 Storage Locations

### Kali VM (Logs):
```
/opt/scans/logs/
├── nmap_20260223_143022_192_168_1_100.json
├── gobuster_20260223_143300_192_168_1_100.json
├── sqlmap_20260223_143600_192_168_1_100.json
└── ...
```

### Windows (Results):
```
C:\Users\User\User\Desktop\mcp\results\
├── nmap_192.168.1.100_20260223_143022.json
├── gobuster_example.com_20260223_143300.json
├── sqlmap_example.com_20260223_143600.json (saved even if failed!)
├── nuclei_target.com_20260223_143700.json (rate limited)
└── ...
```

## 🧹 Maintenance

### Clean Old Results:

```bash
# On Kali VM - keep last 30 days
find /opt/scans/logs -name "*.json" -mtime +30 -delete

# On Windows - keep last 100 files
Get-ChildItem C:\Users\User\User\Desktop\mcp\results\*.json | 
  Sort-Object LastWriteTime -Descending | 
  Select-Object -Skip 100 | 
  Remove-Item
```

### Check Disk Usage:

```bash
# On Kali VM
du -sh /opt/scans/logs

# On Windows
Get-ChildItem C:\Users\User\User\Desktop\mcp\results | 
  Measure-Object -Property Length -Sum | 
  Select-Object @{Name="Size(MB)";Expression={$_.Sum/1MB}}
```

### Analyze Results:

```python
import json
import glob
from datetime import datetime

# Load all results
results = []
for filepath in glob.glob('results/*.json'):
    with open(filepath, 'r') as f:
        results.append(json.load(f))

# Statistics
total = len(results)
successful = sum(1 for r in results if r['success'])
failed = sum(1 for r in results if not r['success'])
rate_limited = sum(1 for r in results if r.get('rate_limited'))

print(f"Total scans: {total}")
print(f"Successful: {successful} ({successful/total*100:.1f}%)")
print(f"Failed: {failed} ({failed/total*100:.1f}%)")
print(f"Rate limited: {rate_limited}")

# Most scanned targets
from collections import Counter
targets = Counter(r['target'] for r in results)
print("\nTop 10 targets:")
for target, count in targets.most_common(10):
    print(f"  {target}: {count} scans")
```

## 🔧 Troubleshooting

### Issue: "No scan history found"

**Cause:** Logs directory doesn't exist or is empty

**Solution:**
```bash
# On Kali VM
sudo mkdir -p /opt/scans/logs
sudo chmod 777 /opt/scans/logs
```

### Issue: Results not saving to file

**Cause:** Results directory not writable

**Solution:**
```powershell
# On Windows
New-Item -ItemType Directory -Force -Path "C:\Users\User\User\Desktop\mcp\results"
```

### Issue: JSON parsing error

**Cause:** Corrupted JSON file

**Solution:**
```python
import json

# Validate JSON file
try:
    with open('results/scan.json', 'r') as f:
        data = json.load(f)
    print("Valid JSON")
except json.JSONDecodeError as e:
    print(f"Invalid JSON: {e}")
```

## 📈 Benefits

**Before JSON Format:**
- ⏱️ Hard to parse results
- 😤 Manual text processing
- 🔄 Can't automate analysis
- 📊 No structured data

**After JSON Format:**
- ⏱️ Easy to parse with any language
- 😊 Automated processing
- 🔄 Script-friendly
- 📊 Structured, queryable data
- ✅ Database import ready
- ✅ Works with data analysis tools

## 🎉 Summary

You now have:
- ✅ Automatic logging of every scan
- ✅ Automatic saving of all results (success AND failure)
- ✅ **JSON format** for easy parsing and automation
- ✅ Raw stdout/stderr preserved
- ✅ Recovery tools to retrieve history
- ✅ Persistent storage that survives crashes
- ✅ Machine-readable structured data
- ✅ Never lose work again!

**Test it now:**
```
1. Run a scan: "Scan scanme.nmap.org with nmap"
2. Check results: dir results\*.json
3. Parse JSON: Get-Content results\nmap_*.json | ConvertFrom-Json
4. Try failed scan: "Scan invalid-host.com with nmap"
5. Verify failed scan saved: dir results\*.json
6. Process with Python/jq/PowerShell
```

Your work is now safe and machine-readable! 🛡️📊
