# Context Persistence Solution for Claude MCP

## The Problem

When Claude crashes or shows "Retry" error:
- ❌ Loses all conversation history
- ❌ Forgets what scans were running
- ❌ Loses partial results
- ❌ Can't resume where it left off
- ❌ You have to explain everything again

## Why This Happens

Claude's conversation context is stored in memory only:
1. MCP server crashes → Memory cleared
2. Network timeout → Connection lost
3. Rate limit hit → Context reset
4. Claude Desktop restart → Everything forgotten

## Solutions

### Solution 1: Automatic Scan Logging (Recommended)

Add persistent logging to track all operations automatically.

#### Implementation

**1. Create logging directory:**
```bash
# On Kali VM
mkdir -p /opt/scans/logs
chmod 777 /opt/scans/logs
```

**2. Add to kali_server.py:**

```python
import json
from datetime import datetime

# Add after imports
SCAN_LOG_DIR = "/opt/scans/logs"

def log_scan_request(tool_name: str, params: dict, client_ip: str) -> str:
    """Log scan request with unique ID"""
    scan_id = f"{tool_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{client_ip.replace('.', '_')}"
    log_file = f"{SCAN_LOG_DIR}/{scan_id}.json"
    
    log_data = {
        "scan_id": scan_id,
        "tool": tool_name,
        "parameters": params,
        "client_ip": client_ip,
        "start_time": datetime.now().isoformat(),
        "status": "started"
    }
    
    with open(log_file, 'w') as f:
        json.dump(log_data, f, indent=2)
    
    logger.info(f"Scan logged: {scan_id}")
    return scan_id

def log_scan_result(scan_id: str, result: dict):
    """Update scan log with results"""
    log_file = f"{SCAN_LOG_DIR}/{scan_id}.json"
    
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            log_data = json.load(f)
        
        log_data.update({
            "end_time": datetime.now().isoformat(),
            "status": "completed" if result.get("success") else "failed",
            "result": result
        })
        
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)

# Update each tool endpoint
@app.route("/api/tools/nmap", methods=["POST"])
@require_api_key
@dynamic_rate_limit("nmap")
def nmap():
    """Execute nmap scan with the provided parameters."""
    try:
        params = request.json
        
        # Log the scan request
        scan_id = log_scan_request("nmap", params, request.remote_addr)
        
        # ... existing code ...
        
        result = execute_command(command)
        
        # Log the result
        log_scan_result(scan_id, result)
        
        # Add scan_id to response
        result["scan_id"] = scan_id
        
        return jsonify(result)
    except Exception as e:
        # ... existing error handling ...
```

**3. Add scan history endpoint:**

```python
@app.route("/api/scans/history", methods=["GET"])
@require_api_key
def scan_history():
    """Get recent scan history"""
    try:
        limit = int(request.args.get('limit', 20))
        
        # Get all log files
        log_files = sorted(
            [f for f in os.listdir(SCAN_LOG_DIR) if f.endswith('.json')],
            reverse=True
        )[:limit]
        
        scans = []
        for log_file in log_files:
            with open(f"{SCAN_LOG_DIR}/{log_file}", 'r') as f:
                scans.append(json.load(f))
        
        return jsonify({
            "total": len(scans),
            "scans": scans
        })
    except Exception as e:
        logger.error(f"Error getting scan history: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/scans/<scan_id>", methods=["GET"])
@require_api_key
def get_scan(scan_id):
    """Get specific scan details"""
    try:
        log_file = f"{SCAN_LOG_DIR}/{scan_id}.json"
        
        if not os.path.exists(log_file):
            return jsonify({"error": "Scan not found"}), 404
        
        with open(log_file, 'r') as f:
            scan_data = json.load(f)
        
        return jsonify(scan_data)
    except Exception as e:
        logger.error(f"Error getting scan: {str(e)}")
        return jsonify({"error": str(e)}), 500
```

**4. Add to mcp_server.py:**

```python
@mcp.tool(name="get_scan_history")
def get_scan_history(limit: int = 20) -> str:
    """
    Get recent scan history to recover context after crash.
    
    Args:
        limit: Number of recent scans to retrieve (default: 20)
        
    Returns:
        Formatted list of recent scans with results
    """
    result = kali_client.safe_get("api/scans/history", {"limit": limit})
    
    if result.get("error"):
        return f"Error: {result['error']}"
    
    scans = result.get("scans", [])
    
    if not scans:
        return "No scan history found."
    
    report = f"\n{'='*80}\nRECENT SCAN HISTORY ({len(scans)} scans)\n{'='*80}\n\n"
    
    for scan in scans:
        report += f"Scan ID: {scan['scan_id']}\n"
        report += f"Tool: {scan['tool']}\n"
        report += f"Started: {scan['start_time']}\n"
        report += f"Status: {scan['status']}\n"
        
        if scan.get('parameters'):
            report += f"Parameters: {json.dumps(scan['parameters'], indent=2)}\n"
        
        if scan.get('result') and scan['status'] == 'completed':
            result_data = scan['result']
            if result_data.get('stdout'):
                preview = result_data['stdout'][:200]
                report += f"Result Preview: {preview}...\n"
        
        report += f"{'-'*80}\n\n"
    
    return report

@mcp.tool(name="get_scan_details")
def get_scan_details(scan_id: str) -> str:
    """
    Get full details of a specific scan.
    
    Args:
        scan_id: The scan ID to retrieve
        
    Returns:
        Complete scan details including full results
    """
    result = kali_client.safe_get(f"api/scans/{scan_id}")
    
    if result.get("error"):
        return f"Error: {result['error']}"
    
    report = f"\n{'='*80}\nSCAN DETAILS: {scan_id}\n{'='*80}\n\n"
    report += f"Tool: {result['tool']}\n"
    report += f"Started: {result['start_time']}\n"
    report += f"Status: {result['status']}\n"
    
    if result.get('end_time'):
        report += f"Completed: {result['end_time']}\n"
    
    if result.get('parameters'):
        report += f"\nParameters:\n{json.dumps(result['parameters'], indent=2)}\n"
    
    if result.get('result'):
        scan_result = result['result']
        report += f"\n{'='*80}\nRESULTS\n{'='*80}\n\n"
        
        if scan_result.get('stdout'):
            report += f"Output:\n{scan_result['stdout']}\n"
        
        if scan_result.get('stderr'):
            report += f"\nErrors/Warnings:\n{scan_result['stderr']}\n"
        
        report += f"\nReturn Code: {scan_result.get('return_code', 'N/A')}\n"
        report += f"Success: {scan_result.get('success', False)}\n"
    
    return report
```

---

### Solution 2: Session State File

Create a state file that persists across crashes.

**Create state_manager.py:**

```python
import json
import os
from datetime import datetime
from typing import Dict, Any, List

STATE_FILE = "/opt/scans/session_state.json"

class SessionState:
    def __init__(self):
        self.state = self.load_state()
    
    def load_state(self) -> Dict:
        """Load state from file"""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
            except:
                return self.default_state()
        return self.default_state()
    
    def default_state(self) -> Dict:
        """Default state structure"""
        return {
            "current_target": None,
            "active_scans": [],
            "completed_scans": [],
            "pending_tasks": [],
            "last_update": None
        }
    
    def save_state(self):
        """Save state to file"""
        self.state["last_update"] = datetime.now().isoformat()
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def add_scan(self, scan_id: str, tool: str, target: str):
        """Add active scan"""
        self.state["active_scans"].append({
            "scan_id": scan_id,
            "tool": tool,
            "target": target,
            "started": datetime.now().isoformat()
        })
        self.state["current_target"] = target
        self.save_state()
    
    def complete_scan(self, scan_id: str, success: bool):
        """Move scan to completed"""
        for scan in self.state["active_scans"]:
            if scan["scan_id"] == scan_id:
                scan["completed"] = datetime.now().isoformat()
                scan["success"] = success
                self.state["completed_scans"].append(scan)
                self.state["active_scans"].remove(scan)
                break
        self.save_state()
    
    def get_context_summary(self) -> str:
        """Get summary of current session state"""
        summary = "SESSION STATE RECOVERY\n" + "="*80 + "\n\n"
        
        if self.state["current_target"]:
            summary += f"Current Target: {self.state['current_target']}\n\n"
        
        if self.state["active_scans"]:
            summary += f"Active Scans ({len(self.state['active_scans'])}):\n"
            for scan in self.state["active_scans"]:
                summary += f"  - {scan['tool']} on {scan['target']} (started: {scan['started']})\n"
            summary += "\n"
        
        if self.state["completed_scans"]:
            summary += f"Recently Completed ({len(self.state['completed_scans'][-5:])}):\n"
            for scan in self.state["completed_scans"][-5:]:
                status = "✓" if scan.get("success") else "✗"
                summary += f"  {status} {scan['tool']} on {scan['target']}\n"
            summary += "\n"
        
        if self.state["pending_tasks"]:
            summary += f"Pending Tasks ({len(self.state['pending_tasks'])}):\n"
            for task in self.state["pending_tasks"]:
                summary += f"  - {task}\n"
        
        return summary

# Global instance
session_state = SessionState()
```

**Add to mcp_server.py:**

```python
from state_manager import session_state

@mcp.tool(name="recover_context")
def recover_context() -> str:
    """
    Recover session context after crash or restart.
    Shows what was being worked on before the interruption.
    
    Returns:
        Summary of active scans, completed tasks, and pending work
    """
    return session_state.get_context_summary()
```

---

### Solution 3: Automatic Context Recovery Prompt

Add a startup message that Claude can use to recover context.

**Create recovery_prompt.txt:**

```
CONTEXT RECOVERY INSTRUCTIONS
==============================

If you see this message, it means the MCP connection was interrupted.

To recover your previous work:

1. Get recent scan history:
   "Show me the recent scan history"

2. Check for active scans:
   "What scans are currently running?"

3. Review last target:
   "What was I working on before the crash?"

4. Get specific scan details:
   "Show me details for scan ID: [scan_id]"

Available recovery commands:
- get_scan_history(limit=20) - Get last 20 scans
- get_scan_details(scan_id) - Get full scan results
- recover_context() - Get session state summary
- server_health() - Check current system status

Common scenarios:

Scenario 1: Scan was running when crashed
→ Check scan history to see if it completed
→ Get scan details to see results
→ Resume from where you left off

Scenario 2: Multiple targets being scanned
→ Check session state to see current target
→ Review completed scans
→ Continue with next target

Scenario 3: Rate limit caused crash
→ Check server health for current limits
→ Wait for rate limit to reset
→ Resume with reduced intensity
```

---

### Solution 4: Export Results to File

Always save results to files that persist.

**Add to each tool in mcp_server.py:**

```python
import os
from datetime import datetime

RESULTS_DIR = "C:\\Users\\User\\User\\Desktop\\mcp\\results"

def save_result_to_file(tool_name: str, target: str, result: str) -> str:
    """Save scan result to persistent file"""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{tool_name}_{target.replace('/', '_')}_{timestamp}.txt"
    filepath = os.path.join(RESULTS_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(result)
    
    return filepath

# Update nmap_scan example:
@mcp.tool(name="nmap_scan")
def nmap_scan(target: str, scan_type: str = "-sV", ports: str = "", additional_args: str = "") -> str:
    """Execute an Nmap scan against a target."""
    data = {
        "target": target,
        "scan_type": scan_type,
        "ports": ports,
        "additional_args": additional_args
    }
    result = kali_client.safe_post("api/tools/nmap", data)
    formatted = format_scan_result(result, f"Nmap Scan: {target}")
    
    # Save to file
    filepath = save_result_to_file("nmap", target, formatted)
    
    # Add file location to result
    formatted += f"\n\nResults saved to: {filepath}\n"
    formatted += "You can review this file even if the connection is lost.\n"
    
    return formatted
```

---

## Usage After Crash

### Immediate Recovery Steps:

**1. Check what was running:**
```
"Show me the recent scan history"
```

**2. Get session state:**
```
"Recover my previous context"
```

**3. Get specific results:**
```
"Show me details for the last nmap scan"
```

**4. Check saved files:**
```powershell
# On Windows
Get-ChildItem C:\Users\User\User\Desktop\mcp\results | Sort-Object LastWriteTime -Descending | Select-Object -First 10
```

### Example Recovery Conversation:

```
User: "Show me the recent scan history"

Claude: "Here are your last 10 scans:

1. nmap_20240220_143022 - 192.168.1.100 - Completed ✓
2. gobuster_20240220_143145 - https://example.com - Completed ✓
3. sqlmap_20240220_143300 - https://example.com/login - Failed ✗
4. nmap_20240220_143445 - 192.168.1.101 - In Progress...

Would you like details on any of these?"

User: "Show me details for the sqlmap scan"

Claude: "Here are the full results from the SQLmap scan that failed..."
```

---

## Prevention Tips

**1. Save results incrementally:**
```
"Scan these 10 targets and save results after each one"
```

**2. Use smaller batches:**
```
Instead of: "Scan 192.168.1.0/24"
Use: "Scan 192.168.1.1-10, then I'll ask for the next batch"
```

**3. Document progress:**
```
"After each scan, summarize what we found so far"
```

**4. Use checkpoints:**
```
"We've scanned 5 targets. Let me know the summary before continuing."
```

---

## Summary

**Without persistence:**
- ❌ Crash = lose everything
- ❌ Have to start over
- ❌ Waste time and resources

**With persistence:**
- ✅ Crash = recover from logs
- ✅ Resume where you left off
- ✅ Never lose scan results
- ✅ Track all activity

**Recommended approach:**
1. Implement automatic scan logging (Solution 1)
2. Add recovery commands to MCP
3. Save results to files automatically
4. Use recovery commands after any crash

This way, even if Claude crashes, you can always recover your work!
