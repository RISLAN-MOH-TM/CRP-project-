# Using Kali Tools with Claude MCP

## ⚠️ Important Security Notice

You're giving Claude AI access to powerful penetration testing tools. This setup is designed with security in mind, but you should understand the implications:

### What Claude Can Do:
- ✅ Run network scans (nmap, nikto)
- ✅ Perform web fuzzing (ffuf, feroxbuster, gobuster)
- ✅ Test for SQL injection (sqlmap)
- ✅ Crack passwords (john, hashcat, hydra)
- ✅ Enumerate systems (enum4linux-ng, amass)
- ✅ Run Metasploit modules
- ✅ Execute any command in the whitelist

### Security Protections in Place:
- ✅ API key authentication required
- ✅ Rate limiting prevents abuse
- ✅ Command whitelist (only allowed tools)
- ✅ Path sanitization (can't access arbitrary files)
- ✅ All actions are logged
- ✅ Input validation on all parameters

### Recommendations:
1. **Only use on authorized targets** - You're legally responsible
2. **Review Claude's actions** - Check logs regularly
3. **Use in isolated environment** - Separate network/VM recommended
4. **Set strong API key** - Use 32+ character random key
5. **Monitor resource usage** - Some scans are resource-intensive

---

## 🚀 Quick Setup for Claude MCP

### Step 1: Install Prerequisites

On your Kali Linux machine:
```bash
# Install Python packages
pip3 install flask requests mcp

# Install penetration testing tools
sudo apt update
sudo apt install -y nmap gobuster feroxbuster nikto sqlmap \
                    metasploit-framework hydra john wpscan \
                    ffuf amass hashcat

# Install enum4linux-ng
pip3 install enum4linux-ng
```

### Step 2: Generate and Set API Key

```bash
# Generate secure API key
API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "Your API Key: $API_KEY"

# Save to environment (add to ~/.bashrc for persistence)
export KALI_API_KEY="$API_KEY"
echo "export KALI_API_KEY='$API_KEY'" >> ~/.bashrc
```

### Step 3: Start Kali API Server

```bash
# For local testing (Claude on same machine)
python3 kali_server.py --ip 127.0.0.1 --port 5000

# For remote access (Claude on different machine)
python3 kali_server.py --ip 0.0.0.0 --port 5000
```

### Step 4: Configure Claude MCP

Create or edit your MCP configuration file:

**Location:** `~/.config/claude-mcp/config.json` (or your MCP config location)

```json
{
  "mcpServers": {
    "kali-tools": {
      "command": "python3",
      "args": [
        "/path/to/mcp_server.py",
        "--server", "http://localhost:5000"
      ],
      "env": {
        "KALI_API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

**For remote Kali server:**
```json
{
  "mcpServers": {
    "kali-tools": {
      "command": "python3",
      "args": [
        "/path/to/mcp_server.py",
        "--server", "http://KALI_IP:5000"
      ],
      "env": {
        "KALI_API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

### Step 5: Restart Claude

Restart Claude Desktop or your MCP client to load the new configuration.

---

## 🧪 Testing the Setup

### 1. Check if Claude can see the tools

Ask Claude:
```
Can you check the health of the Kali server?
```

Claude should be able to call `server_health()` and show you the status.

### 2. Test a simple scan

Ask Claude:
```
Can you run a basic nmap scan on 127.0.0.1 to check ports 80 and 443?
```

### 3. Verify authentication

Check the Kali server logs - you should see authenticated requests.

---

## 💡 Example Conversations with Claude

### Network Reconnaissance
```
You: "Scan 192.168.1.1 with nmap to identify open ports and services"

Claude will:
- Run nmap_scan with appropriate parameters
- Parse the results
- Summarize findings
- Suggest next steps
```

### Web Application Testing
```
You: "Find hidden directories on https://example.com"

Claude will:
- Use ffuf_scan or feroxbuster_scan
- Apply appropriate filters
- Show discovered paths
- Identify interesting findings
```

### Vulnerability Assessment
```
You: "Check if https://wordpress-site.com has any WordPress vulnerabilities"

Claude will:
- Run wpscan_analyze
- Identify WordPress version
- List plugins and themes
- Report known vulnerabilities
```

### Password Cracking
```
You: "Crack the hashes in /tmp/hashes.txt using rockyou.txt"

Claude will:
- Use john_crack or hashcat_crack
- Select appropriate hash format
- Run the cracking process
- Report cracked passwords
```

---

## 🎯 Best Practices with Claude

### 1. Be Specific
❌ "Scan this website"
✅ "Run a directory fuzzing scan on https://example.com using the common.txt wordlist, limiting results to 100"

### 2. Set Boundaries
```
You: "Scan 192.168.1.0/24 but only check ports 80, 443, 8080 and use -T2 timing"
```

### 3. Review Before Execution
```
You: "What command would you run to scan example.com for SQL injection?"
(Review Claude's plan before confirming)
You: "Okay, proceed with that scan"
```

### 4. Monitor Progress
```
You: "Check the status of the current scan"
You: "Show me the last 50 lines of output"
```

### 5. Understand Limitations
- Claude can't see real-time progress of long scans
- Some tools may timeout (default: 3 minutes)
- Rate limits apply (10 requests/minute for most tools)

---

## 🔒 Security Considerations

### What You Should Do:

1. **Use Isolated Environment**
   ```bash
   # Run in a VM or container
   docker run -it kalilinux/kali-rolling
   ```

2. **Restrict Network Access**
   ```bash
   # Firewall rules - only allow from Claude's IP
   sudo ufw allow from CLAUDE_IP to any port 5000
   sudo ufw deny 5000
   ```

3. **Monitor Logs**
   ```bash
   # Watch for suspicious activity
   tail -f /var/log/kali-server.log | grep -E "WARN|ERROR"
   ```

4. **Regular Audits**
   ```bash
   # Review what Claude has been doing
   grep "Executing command" /var/log/kali-server.log
   ```

5. **Rotate API Keys**
   ```bash
   # Change API key monthly
   NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
   export KALI_API_KEY="$NEW_KEY"
   # Update Claude MCP config
   ```

### What You Should NOT Do:

❌ Expose the API server to the public internet without VPN/firewall
❌ Use weak or default API keys
❌ Run as root user
❌ Disable authentication for "convenience"
❌ Scan targets without authorization
❌ Ignore rate limit warnings

---

## 🐛 Troubleshooting

### Claude says "Tool not available"
**Check:**
```bash
# Is the server running?
ps aux | grep kali_server.py

# Is MCP server running?
ps aux | grep mcp_server.py

# Check MCP config
cat ~/.config/claude-mcp/config.json
```

### "Authentication failed" errors
**Fix:**
```bash
# Verify API key matches on both sides
echo $KALI_API_KEY

# Check MCP config has correct key
grep KALI_API_KEY ~/.config/claude-mcp/config.json

# Restart both servers
```

### "Rate limit exceeded"
**Solution:**
- Wait 60 seconds
- Or adjust rate limits in `kali_server.py`
- Or batch your requests

### Scans timing out
**Fix:**
```bash
# Increase timeout in mcp_server.py
python3 mcp_server.py --server http://localhost:5000 --timeout 3600

# Or use faster scan options
# Example: nmap -T4 instead of -T2
```

---

## 📊 Monitoring Claude's Activity

### Real-time Monitoring
```bash
# Watch all commands
tail -f /var/log/kali-server.log | grep "Executing command"

# Watch authentication attempts
tail -f /var/log/kali-server.log | grep "API key"

# Watch rate limit hits
tail -f /var/log/kali-server.log | grep "Rate limit"
```

### Daily Audit
```bash
# Commands run today
grep "$(date +%Y-%m-%d)" /var/log/kali-server.log | grep "Executing command"

# Failed authentication attempts
grep "$(date +%Y-%m-%d)" /var/log/kali-server.log | grep "Invalid API key"

# Most used tools
grep "Executing command" /var/log/kali-server.log | awk '{print $NF}' | sort | uniq -c | sort -rn
```

---

## 🎓 Teaching Claude About Your Environment

When starting a new conversation, give Claude context:

```
You: "I have a Kali MCP server set up with the following tools available:
- nmap for network scanning
- ffuf and feroxbuster for web fuzzing
- sqlmap for SQL injection testing
- wpscan for WordPress scanning
- john and hashcat for password cracking

I need help testing a web application at https://test.example.com.
This is an authorized penetration test.
Please suggest a testing methodology."
```

---

## 🚨 Emergency Procedures

### If Claude Goes Rogue (Unlikely but prepared)

1. **Stop the servers immediately**
   ```bash
   pkill -f kali_server.py
   pkill -f mcp_server.py
   ```

2. **Revoke API key**
   ```bash
   unset KALI_API_KEY
   export KALI_API_KEY="revoked"
   ```

3. **Check what was executed**
   ```bash
   grep "Executing command" /var/log/kali-server.log | tail -100
   ```

4. **Block the IP if remote**
   ```bash
   sudo ufw deny from CLAUDE_IP
   ```

---

## 📈 Performance Tips

### For Large Scans
```
You: "Scan this /24 network but use -T2 timing and scan in batches of 10 hosts"
```

### For Multiple Targets
```
You: "I have 50 URLs to scan. Process them in batches of 5 with 30 second delays between batches"
```

### For Resource-Intensive Tasks
```
You: "Run hashcat with --workload-profile=2 to avoid maxing out the GPU"
```

---

## ✅ Pre-Engagement Checklist

Before starting a penetration test with Claude:

- [ ] Authorization obtained for all targets
- [ ] API key is set and secure
- [ ] Kali server is running
- [ ] MCP server is connected
- [ ] Logs are being captured
- [ ] Backup of important data
- [ ] Network isolation configured
- [ ] Rate limits are appropriate
- [ ] Timeout settings are configured
- [ ] Emergency stop procedure tested

---

## 🎉 You're Ready!

Your Claude MCP setup is now ready to assist with penetration testing. Remember:

1. **Always get authorization** before testing any target
2. **Monitor Claude's actions** through logs
3. **Review results** before taking action
4. **Stay within legal boundaries**
5. **Use responsibly**

Claude is a powerful assistant, but you're the one in control and responsible for all actions.

---

## 📚 Additional Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [Kali Linux Tools](https://www.kali.org/tools/)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
- [Penetration Testing Execution Standard](http://www.pentest-standard.org/)

---

**Happy (Ethical) Hacking with Claude! 🎯🤖**
