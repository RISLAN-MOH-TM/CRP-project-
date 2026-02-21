# Rate Limit Handling & Efficient Report Generation

## Overview

This guide explains how the system handles rate limits gracefully and generates efficient reports even when limits are reached.

## The Problem You Identified

**Before:** When rate limits were hit during report generation, the entire process would fail with an error, losing all progress.

**After:** The system now:
1. Detects rate limit errors (HTTP 429)
2. Generates a partial report with data collected before the limit
3. Provides clear guidance on what happened and when to retry
4. Continues processing other tasks when possible

## How It Works

### 1. Enhanced Error Detection

The MCP client now specifically detects:

```python
# Rate limiting (HTTP 429)
if response.status_code == 429:
    return {
        "error": "Rate limit exceeded. Please wait before retrying.",
        "success": False,
        "rate_limited": True,
        "retry_after": "60 seconds"
    }

# Concurrent scan limit (HTTP 503)
if response.status_code == 503:
    return {
        "error": "Maximum concurrent scans reached.",
        "success": False,
        "concurrent_limit_reached": True
    }
```

### 2. Intelligent Report Formatting

The `format_scan_result()` function handles all scenarios:

#### Scenario A: Rate Limit Hit
```
================================================================================
NMAP SCAN REPORT
================================================================================

⚠️  RATE LIMIT REACHED
Status: Rate limit exceeded
Retry After: 60 seconds

This is a protective measure to prevent VM overload.
Please wait before running additional scans.
```

#### Scenario B: Concurrent Scan Limit
```
================================================================================
NMAP SCAN REPORT
================================================================================

⚠️  CONCURRENT SCAN LIMIT REACHED
Status: Maximum concurrent scans running

Please wait for running scans to complete before starting new ones.
```

#### Scenario C: Partial Results (Timeout)
```
================================================================================
NMAP SCAN REPORT
================================================================================

⏱️  SCAN TIMED OUT (Partial Results Available)

📊 OUTPUT:
--------------------------------------------------------------------------------
Starting Nmap 7.94 ( https://nmap.org )
Nmap scan report for 192.168.1.1
Host is up (0.0012s latency).
PORT     STATE SERVICE
22/tcp   open  ssh
80/tcp   open  http
... (partial results shown)
--------------------------------------------------------------------------------

Return Code: -1
Note: Scan timed out but partial results are shown above.
```

#### Scenario D: Error with Partial Output
```
================================================================================
NMAP SCAN REPORT
================================================================================

❌ ERROR: Connection timeout

📊 PARTIAL OUTPUT:
--------------------------------------------------------------------------------
Starting Nmap 7.94 ( https://nmap.org )
... (any output collected before error)
--------------------------------------------------------------------------------
```

## Benefits

### 1. No Lost Work
Even if rate limited, you get:
- All data collected before the limit
- Clear status of what happened
- Guidance on next steps

### 2. Better User Experience
Instead of cryptic errors, users see:
- Friendly formatted reports
- Clear explanations
- Actionable next steps

### 3. Efficient Resource Usage
The system:
- Stops immediately when rate limited (saves resources)
- Provides partial results (maximizes value)
- Guides users to wait (prevents retry storms)

## Example Workflow

### Multi-Target Scan with Rate Limiting

```python
# Scanning 20 targets
targets = ["192.168.1.1", "192.168.1.2", ..., "192.168.1.20"]

results = []
for target in targets:
    result = nmap_scan(target, scan_type="-sV")
    results.append(result)
    
    # Check if rate limited
    if "RATE LIMIT REACHED" in result:
        print(f"Rate limited after {len(results)} scans")
        print("Generating report with collected data...")
        break

# Generate comprehensive report with all collected data
generate_final_report(results)
```

**Output:**
```
Scan 1: ✅ Complete
Scan 2: ✅ Complete
Scan 3: ✅ Complete
Scan 4: ⚠️  Rate limited

Generating report with 4/20 targets scanned...

COMPREHENSIVE SCAN REPORT
=========================
Successfully scanned: 3 targets
Rate limited: After target 4
Recommendation: Wait 60 seconds and resume from target 5
```

## Rate Limit Thresholds

### Current Limits (Per IP Address)

**Global:**
- 200 requests per day
- 50 requests per hour

**High-Risk Tools (5/minute):**
- Generic commands
- SQLMap
- Metasploit
- Hydra
- John the Ripper
- Hashcat
- OpenVAS

**Medium-Risk Tools (10/minute):**
- Nmap
- Gobuster
- Feroxbuster
- Nikto
- WPScan
- Enum4linux-ng
- FFUF
- Amass

**Concurrent Scans:**
- Maximum 5 simultaneous scans

## Best Practices for Report Generation

### 1. Batch Processing with Delays

```python
import time

def scan_multiple_targets(targets, delay=6):
    """Scan multiple targets with rate limit awareness"""
    results = []
    
    for i, target in enumerate(targets):
        print(f"Scanning {i+1}/{len(targets)}: {target}")
        
        result = nmap_scan(target)
        results.append(result)
        
        # Check for rate limit
        if "RATE LIMIT REACHED" in result:
            print("Rate limit hit. Pausing...")
            break
        
        # Add delay between scans (10 per minute = 6 second delay)
        if i < len(targets) - 1:
            time.sleep(delay)
    
    return results
```

### 2. Progressive Report Generation

```python
def generate_progressive_report(targets):
    """Generate report progressively as scans complete"""
    report = "PROGRESSIVE SCAN REPORT\n" + "="*80 + "\n\n"
    
    for i, target in enumerate(targets):
        result = nmap_scan(target)
        
        # Add to report immediately
        report += f"\n--- Target {i+1}: {target} ---\n"
        report += result
        
        # Save intermediate report
        with open(f"scan_report_progress.txt", "w") as f:
            f.write(report)
        
        # Stop if rate limited
        if "RATE LIMIT REACHED" in result:
            report += f"\n\nScan paused at target {i+1}/{len(targets)} due to rate limiting.\n"
            break
    
    return report
```

### 3. Smart Retry Logic

```python
def scan_with_retry(target, max_retries=3):
    """Scan with automatic retry on rate limit"""
    import time
    
    for attempt in range(max_retries):
        result = nmap_scan(target)
        
        if "RATE LIMIT REACHED" not in result:
            return result
        
        if attempt < max_retries - 1:
            wait_time = 60 * (attempt + 1)  # Exponential backoff
            print(f"Rate limited. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
    
    return result  # Return last result even if rate limited
```

## Monitoring Rate Limits

### Check Current Usage

The system logs all rate limit events:

```bash
# On Kali VM, check logs
tail -f /var/log/kali_server.log | grep "Rate limit"

# Output:
# 2026-02-21 10:15:23 [WARNING] Rate limit exceeded for 192.168.1.100
# 2026-02-21 10:16:45 [WARNING] Rate limit exceeded for 192.168.1.100
```

### Health Check Endpoint

```bash
curl http://172.20.10.11:5000/health

# Response includes rate limiting status:
{
  "status": "healthy",
  "security": {
    "rate_limiting": "enabled",
    "authentication": "enabled"
  }
}
```

## Troubleshooting

### Issue: Reports Always Show Rate Limit

**Cause:** Too many requests too quickly

**Solution:**
1. Add delays between scans (6+ seconds for 10/minute limit)
2. Reduce concurrent operations
3. Use batch processing with pauses

### Issue: Partial Results Not Showing

**Cause:** Error occurred before any output

**Solution:**
1. Check network connectivity
2. Verify API key is correct
3. Ensure target is reachable
4. Check Kali VM resources (CPU/RAM)

### Issue: Rate Limits Too Restrictive

**Cause:** Default limits may be too low for your use case

**Solution:**
Edit `kali_server.py`:
```python
# Increase global limits
limiter = Limiter(
    default_limits=["500 per day", "100 per hour"],  # Increased
    ...
)

# Increase per-endpoint limits
@limiter.limit("20 per minute")  # Increased from 10
def nmap():
    ...
```

## Summary

The improved error handling ensures:

✅ **No data loss** - Partial results are always captured
✅ **Clear communication** - Users know exactly what happened
✅ **Efficient reports** - Formatted output even on errors
✅ **Resource protection** - VM stays stable under load
✅ **Better UX** - Actionable guidance instead of cryptic errors

Rate limits are a feature, not a bug - they protect your VM while still delivering maximum value from completed scans.
