# Security Features & Rate Limiting

## Critical Security Improvements

This document outlines the security measures implemented to protect your Kali VM from resource exhaustion and abuse.

## Rate Limiting Protection

### Why Rate Limiting is Critical

Without rate limiting, attackers or misconfigured AI agents can:
- Send unlimited requests to `/api/command` and `/api/tools/*`
- Run heavy scans continuously (nmap, sqlmap, hydra)
- Overload CPU & RAM resources
- Crash your Kali VM
- Cause system unresponsiveness

### Implemented Rate Limits

#### Global Limits (All Endpoints)
- **200 requests per day** per IP address
- **50 requests per hour** per IP address

#### Endpoint-Specific Limits

**High-Risk Endpoints (5 requests/minute):**
- `/api/command` - Generic command execution
- `/api/tools/sqlmap` - SQL injection testing
- `/api/tools/metasploit` - Exploit framework
- `/api/tools/hydra` - Password brute-forcing
- `/api/tools/john` - Password cracking
- `/api/tools/hashcat` - Hash cracking
- `/api/tools/openvas` - Vulnerability scanning

**Medium-Risk Endpoints (10 requests/minute):**
- `/api/tools/nmap` - Network scanning
- `/api/tools/gobuster` - Directory brute-forcing
- `/api/tools/feroxbuster` - Web fuzzing
- `/api/tools/nikto` - Web vulnerability scanning
- `/api/tools/wpscan` - WordPress scanning
- `/api/tools/enum4linux-ng` - SMB enumeration
- `/api/tools/ffuf` - Web fuzzing
- `/api/tools/amass` - Subdomain enumeration

### Concurrent Scan Limiting

**Maximum Concurrent Scans:** 5 (configurable via `MAX_CONCURRENT_SCANS` environment variable)

This prevents resource exhaustion by limiting how many heavy scans can run simultaneously. When the limit is reached, new requests receive:
```json
{
  "error": "Maximum concurrent scans (5) reached. Please try again later.",
  "return_code": -1,
  "success": false
}
```

## Additional Security Features

### 1. API Key Authentication
- All endpoints require `X-API-Key` header
- Uses constant-time comparison to prevent timing attacks
- Default key: `kali-research-project-2024` (CHANGE IN PRODUCTION!)
- Set via `KALI_API_KEY` environment variable

### 2. Command Validation
- Whitelist of allowed commands only
- Prevents arbitrary command injection
- Validates command structure before execution

### 3. Path Sanitization
- Prevents path traversal attacks
- Validates file paths against allowed directories
- Resolves symbolic links to prevent bypass

### 4. Argument Escaping
- All command arguments are properly escaped using `shlex.quote()`
- Prevents command injection via arguments

### 5. Timeout Protection
- Default 30-minute timeout for all commands
- Prevents infinite-running processes
- Graceful termination with partial results

## Configuration

### Environment Variables

```bash
# API Security
export KALI_API_KEY="your-secure-api-key-here"

# Rate Limiting
export MAX_CONCURRENT_SCANS=5

# Server Configuration
export API_PORT=5000
export DEBUG_MODE=0
```

### Updating Rate Limits

To modify rate limits, edit `kali_server.py`:

```python
# Global limits
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],  # Modify here
    storage_uri="memory://",
    strategy="fixed-window"
)

# Per-endpoint limits
@limiter.limit("5 per minute")  # Modify decorator
def endpoint():
    pass
```

## Rate Limit Response

When rate limit is exceeded, the server returns:

```json
HTTP 429 Too Many Requests
{
  "error": "Rate limit exceeded"
}
```

## Monitoring

### Check Active Scans
The server tracks active scans internally. Monitor logs for:
```
[WARNING] Maximum concurrent scans (5) reached
[INFO] Executing command: nmap -sCV 192.168.1.1
```

### Check Rate Limit Status
Flask-Limiter automatically logs rate limit violations:
```
[WARNING] Rate limit exceeded for 192.168.1.100
```

## Best Practices

1. **Change Default API Key**
   ```bash
   export KALI_API_KEY="$(openssl rand -hex 32)"
   ```

2. **Run on Localhost Only** (default)
   ```bash
   python kali_server.py --ip 127.0.0.1
   ```

3. **Use Firewall Rules**
   ```bash
   # Allow only specific IPs
   sudo ufw allow from 192.168.1.0/24 to any port 5000
   ```

4. **Monitor Resource Usage**
   ```bash
   # Watch CPU/Memory
   htop
   
   # Monitor active connections
   netstat -an | grep :5000
   ```

5. **Set Appropriate Concurrent Scan Limit**
   - Low-resource VM: `MAX_CONCURRENT_SCANS=2`
   - Medium VM: `MAX_CONCURRENT_SCANS=5` (default)
   - High-resource VM: `MAX_CONCURRENT_SCANS=10`

## Troubleshooting

### "Rate limit exceeded" errors
- Wait for the time window to reset
- Increase limits if legitimate use case
- Check for misconfigured automation

### "Maximum concurrent scans reached"
- Wait for running scans to complete
- Increase `MAX_CONCURRENT_SCANS` if you have resources
- Check for stuck processes: `ps aux | grep -E 'nmap|sqlmap|hydra'`

### VM Still Unresponsive
If rate limiting doesn't solve the issue:
1. Check for memory leaks: `free -h`
2. Kill stuck processes: `pkill -9 nmap`
3. Restart the server
4. Lower `MAX_CONCURRENT_SCANS`
5. Reduce command timeouts in code

## Installation

Install the required dependency:
```bash
pip install Flask-Limiter>=3.5.0
```

Or use requirements.txt:
```bash
pip install -r requirements.txt
```

## Testing Rate Limits

Test with curl:
```bash
# Send multiple requests quickly
for i in {1..20}; do
  curl -X POST http://localhost:5000/api/tools/nmap \
    -H "X-API-Key: kali-research-project-2024" \
    -H "Content-Type: application/json" \
    -d '{"target":"scanme.nmap.org","scan_type":"-sn"}' &
done
```

You should see rate limit errors after the threshold.
