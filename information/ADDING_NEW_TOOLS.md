# Adding New Tools to MCP Server

## Current Status

**Available Tools:** 16 fully integrated tools
**Whitelisted Commands:** Limited set for security

## What Happens When You Request Unavailable Tools?

### Scenario 1: Tool Not Integrated (e.g., "Use Burp Suite")

**What Claude Will Do:**
1. Check available MCP tools
2. Not find "burp_suite" function
3. Try to use `execute_command` as fallback
4. Command will be rejected (not whitelisted)

**Result:** ❌ Won't work - "Command not allowed" error

**Example:**
```
User: "Scan with Burp Suite"
Claude: "I don't have Burp Suite integrated. Available tools are: nmap, gobuster..."
```

### Scenario 2: Tool Installed but Not Whitelisted (e.g., "Run aircrack-ng")

**What Happens:**
1. Claude tries `execute_command("aircrack-ng ...")`
2. Server validates command against whitelist
3. "aircrack-ng" not in whitelist
4. Command rejected

**Result:** ❌ Won't work - "Command not allowed" error

### Scenario 3: Integrated Tool (e.g., "Use nmap")

**What Happens:**
1. Claude calls `nmap_scan()` function
2. MCP server sends request to Kali API
3. Kali server validates and executes
4. Results returned formatted

**Result:** ✅ Works perfectly

## How to Add New Tools

### Method 1: Quick Add (Whitelist Only)

**Use Case:** Simple command-line tools that don't need special handling

**Steps:**

1. **Edit kali_server.py** - Find the command validation function:

```python
def validate_command(command: str) -> bool:
    """Validate that command starts with an allowed command"""
    try:
        cmd_parts = shlex.split(command)
        if not cmd_parts:
            return False
        
        base_command = cmd_parts[0].split('/')[-1]
        
        # Add your tool here
        ALLOWED_COMMANDS = {
            "nmap", "gobuster", "feroxbuster", "nikto", "sqlmap", 
            "msfconsole", "hydra", "john", "wpscan", "enum4linux-ng",
            "ffuf", "amass", "hashcat", "gvm-cli", "which",
            "aircrack-ng",  # NEW TOOL ADDED
            "masscan",      # NEW TOOL ADDED
            "dnsenum"       # NEW TOOL ADDED
        }
        
        return base_command in ALLOWED_COMMANDS
    except Exception as e:
        logger.error(f"Error validating command: {str(e)}")
        return False
```

2. **Restart Kali Server:**
```bash
python3 kali_server.py --ip 0.0.0.0 --port 5000
```

3. **Use with Claude:**
```
"Execute command: aircrack-ng --help"
```

**Limitations:**
- No formatted output
- No parameter validation
- No rate limiting per tool
- Generic error handling

---

### Method 2: Full Integration (Recommended)

**Use Case:** Tools you'll use frequently that need proper integration

**Steps:**

#### Step 1: Add API Endpoint to kali_server.py

```python
@app.route("/api/tools/aircrack", methods=["POST"])
@require_api_key
@dynamic_rate_limit("aircrack")
def aircrack():
    """Execute aircrack-ng with the provided parameters."""
    try:
        params = request.json
        capture_file = params.get("capture_file", "")
        wordlist = params.get("wordlist", "")
        additional_args = params.get("additional_args", "")
        
        if not capture_file:
            logger.warning("Aircrack called without capture_file parameter")
            return jsonify({
                "error": "Capture file parameter is required"
            }), 400
        
        # Validate file path
        safe_file = sanitize_path(capture_file, ALLOWED_FILE_DIRS)
        if not safe_file:
            return jsonify({"error": "Invalid capture file path"}), 400
        
        cmd_parts = ["-w", wordlist, safe_file]
        
        if additional_args:
            try:
                extra_args = shlex.split(additional_args)
                cmd_parts.extend(extra_args)
            except ValueError:
                return jsonify({"error": "Invalid additional arguments"}), 400
        
        command = build_safe_command("aircrack-ng", cmd_parts)
        result = execute_command(command)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in aircrack endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500
```

#### Step 2: Add Resource Profile

```python
TOOL_RESOURCE_PROFILES = {
    # ... existing tools ...
    
    "aircrack": {
        "cpu": 0.8,      # High CPU usage
        "memory": 0.6,   # Moderate memory
        "io": 0.4,       # Low I/O
        "base_limit": 5  # 5 requests/minute base
    }
}
```

#### Step 3: Add MCP Tool Function to mcp_server.py

```python
@mcp.tool(name="aircrack_crack")
def aircrack_crack(
    capture_file: str,
    wordlist: str = "/usr/share/wordlists/rockyou.txt",
    additional_args: str = ""
) -> str:
    """
    Crack WPA/WPA2 passwords using aircrack-ng.
    
    Args:
        capture_file: Path to capture file (.cap or .pcap)
        wordlist: Path to password wordlist
        additional_args: Additional aircrack-ng arguments
        
    Returns:
        Formatted crack results
        
    Examples:
        - Crack WPA: aircrack_crack("/tmp/capture.cap", "/usr/share/wordlists/rockyou.txt")
    """
    data = {
        "capture_file": capture_file,
        "wordlist": wordlist,
        "additional_args": additional_args
    }
    result = kali_client.safe_post("api/tools/aircrack", data)
    return format_scan_result(result, f"Aircrack-ng: {capture_file}")
```

#### Step 4: Update Documentation

Add to `TOOLS_REFERENCE.md`:

```markdown
### 17. **aircrack_crack** - WiFi Password Cracking

**Purpose:** Crack WPA/WPA2 passwords from capture files

**Parameters:**
- `capture_file` (required): Path to .cap/.pcap file
- `wordlist` (optional): Password wordlist path
- `additional_args` (optional): Extra arguments

**Examples:**
```
"Crack WiFi password from /tmp/capture.cap"
"Use aircrack-ng on /tmp/wpa.cap with rockyou wordlist"
```

**Rate Limit:** 5-7 requests/minute (dynamic)
```

#### Step 5: Restart Both Servers

```bash
# On Kali VM
python3 kali_server.py --ip 0.0.0.0 --port 5000

# On Windows (restart Claude Desktop to reload MCP)
# Or restart the MCP server if running manually
```

#### Step 6: Test with Claude

```
"Crack the WiFi password from /tmp/capture.cap using aircrack-ng"
```

---

## Example: Adding Masscan

### Quick Version (Whitelist Only)

**kali_server.py:**
```python
ALLOWED_COMMANDS = {
    "nmap", "gobuster", "feroxbuster", "nikto", "sqlmap", 
    "msfconsole", "hydra", "john", "wpscan", "enum4linux-ng",
    "ffuf", "amass", "hashcat", "gvm-cli", "which",
    "masscan"  # ADD THIS
}
```

**Usage:**
```
"Execute command: masscan 192.168.1.0/24 -p80,443"
```

### Full Integration Version

**kali_server.py:**
```python
@app.route("/api/tools/masscan", methods=["POST"])
@require_api_key
@dynamic_rate_limit("masscan")
def masscan():
    """Execute masscan with the provided parameters."""
    try:
        params = request.json
        target = params.get("target", "")
        ports = params.get("ports", "80,443")
        rate = params.get("rate", "1000")
        additional_args = params.get("additional_args", "")
        
        if not target:
            return jsonify({"error": "Target parameter is required"}), 400
        
        cmd_parts = [target, "-p", ports, "--rate", rate]
        
        if additional_args:
            extra_args = shlex.split(additional_args)
            cmd_parts.extend(extra_args)
        
        command = build_safe_command("masscan", cmd_parts)
        result = execute_command(command)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in masscan endpoint: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

# Add resource profile
TOOL_RESOURCE_PROFILES["masscan"] = {
    "cpu": 0.7,
    "memory": 0.5,
    "io": 0.8,
    "base_limit": 6
}
```

**mcp_server.py:**
```python
@mcp.tool(name="masscan_scan")
def masscan_scan(
    target: str,
    ports: str = "80,443",
    rate: str = "1000",
    additional_args: str = ""
) -> str:
    """
    Fast port scanner using masscan.
    
    Args:
        target: Target IP or CIDR range
        ports: Ports to scan (comma-separated)
        rate: Packets per second
        additional_args: Additional masscan arguments
        
    Returns:
        Formatted scan results
    """
    data = {
        "target": target,
        "ports": ports,
        "rate": rate,
        "additional_args": additional_args
    }
    result = kali_client.safe_post("api/tools/masscan", data)
    return format_scan_result(result, f"Masscan: {target}")
```

**Usage:**
```
"Scan 192.168.1.0/24 with masscan on ports 80,443"
```

---

## Testing New Tools

### 1. Test API Endpoint Directly

```bash
curl -X POST http://172.20.10.11:5000/api/tools/masscan \
  -H "X-API-Key: kali-research-project-2026" \
  -H "Content-Type: application/json" \
  -d '{
    "target": "scanme.nmap.org",
    "ports": "80,443"
  }'
```

### 2. Test with Claude

```
"Use masscan to scan scanme.nmap.org on ports 80 and 443"
```

### 3. Check Health Endpoint

```bash
curl http://172.20.10.11:5000/health
```

Should show your new tool in the rate limits section.

---

## Common Issues

### Issue: "Command not allowed"

**Cause:** Tool not in whitelist or not properly integrated

**Solution:**
1. Check if tool is in `ALLOWED_COMMANDS` (for execute_command)
2. Or check if API endpoint exists (for full integration)
3. Restart Kali server after changes

### Issue: "Tool not found in MCP"

**Cause:** MCP function not defined or Claude Desktop not restarted

**Solution:**
1. Verify function exists in `mcp_server.py`
2. Restart Claude Desktop to reload MCP
3. Check MCP server logs for errors

### Issue: Rate limit too restrictive

**Cause:** Tool resource profile too conservative

**Solution:**
Adjust in `TOOL_RESOURCE_PROFILES`:
```python
"your_tool": {
    "cpu": 0.5,        # Lower = less restrictive
    "memory": 0.4,
    "io": 0.3,
    "base_limit": 15   # Higher = more requests allowed
}
```

---

## Summary

**Will Work:**
- ✅ All 16 integrated tools
- ✅ Whitelisted commands via execute_command

**Won't Work:**
- ❌ Non-whitelisted commands
- ❌ Tools not integrated in MCP
- ❌ GUI applications (Burp Suite, Wireshark)

**To Add New Tools:**
- Quick: Add to whitelist (5 minutes)
- Full: Create API endpoint + MCP function (30 minutes)

**Recommendation:** Use full integration for frequently-used tools, whitelist for occasional use.
