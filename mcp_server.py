#!/usr/bin/env python3

# This script connect the MCP AI agent to Kali Linux terminal and API Server.

import argparse
import json
import logging
import os
import sys
import glob
from typing import Any, Dict, Optional, List
from datetime import datetime
from collections import Counter, defaultdict

import requests
from mcp.server.fastmcp import FastMCP

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use system environment variables

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Results directory for saving scan outputs
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

def save_result_to_file(tool_name: str, target: str, result: Dict[str, Any]) -> str:
    """
    Save scan result to persistent JSON file (raw data for both success and failure)
    
    Args:
        tool_name: Name of the tool that was executed
        target: Target that was scanned (IP, URL, domain, etc.)
        result: Result dictionary from kali_client.safe_post()
        
    Returns:
        Filepath where results were saved, or empty string on error
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize target for filename
        safe_target = target.replace('/', '_').replace(':', '_').replace('\\', '_').replace('?', '_').replace('&', '_')
        filename = f"{tool_name}_{safe_target}_{timestamp}.json"
        filepath = os.path.join(RESULTS_DIR, filename)
        
        # Prepare JSON data structure
        json_data = {
            "tool": tool_name,
            "target": target,
            "timestamp": timestamp,
            "datetime": datetime.now().isoformat(),
            "success": result.get('success', False),
            "return_code": result.get('return_code', None),
            "stdout": result.get('stdout', ''),
            "stderr": result.get('stderr', ''),
            "error": result.get('error', None),
            "timed_out": result.get('timed_out', False),
            "partial_results": result.get('partial_results', False),
            "rate_limited": result.get('rate_limited', False),
            "retry_after": result.get('retry_after', None),
            "concurrent_limit_reached": result.get('concurrent_limit_reached', False),
            "scan_id": result.get('scan_id', None),
            "status_code": result.get('status_code', None),
            "parsed_output": result.get('parsed_output', None)
        }
        
        # Write JSON file with pretty formatting
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Error saving results to file: {str(e)}")
        return ""

def load_all_results(results_dir: str = RESULTS_DIR) -> List[Dict[str, Any]]:
    """Load all JSON result files from the results directory"""
    results = []
    try:
        for filepath in glob.glob(os.path.join(results_dir, '*.json')):
            # Skip example files
            if 'EXAMPLE_' in os.path.basename(filepath):
                continue
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    results.append(json.load(f))
            except Exception as e:
                logger.error(f"Error loading {filepath}: {e}")
    except Exception as e:
        logger.error(f"Error reading results directory: {e}")
    return results

def analyze_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze scan results and return statistics"""
    if not results:
        return {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "rate_limited": 0,
            "timed_out": 0,
            "by_tool": {},
            "top_targets": [],
            "failed_scans": []
        }
    
    total = len(results)
    successful = sum(1 for r in results if r.get('success'))
    failed = sum(1 for r in results if not r.get('success'))
    rate_limited = sum(1 for r in results if r.get('rate_limited'))
    timed_out = sum(1 for r in results if r.get('timed_out'))
    
    # Group by tool
    by_tool = defaultdict(lambda: {'total': 0, 'success': 0, 'failed': 0})
    for r in results:
        tool = r.get('tool', 'unknown')
        by_tool[tool]['total'] += 1
        if r.get('success'):
            by_tool[tool]['success'] += 1
        else:
            by_tool[tool]['failed'] += 1
    
    # Top targets
    targets = Counter(r.get('target', 'unknown') for r in results)
    top_targets = [{"target": t, "count": c} for t, c in targets.most_common(10)]
    
    # Failed scans
    failed_scans = [
        {
            "tool": r.get('tool'),
            "target": r.get('target'),
            "datetime": r.get('datetime'),
            "error": r.get('error', 'Unknown error'),
            "stderr": r.get('stderr', '')[:200]  # Limit stderr length
        }
        for r in results if not r.get('success')
    ]
    
    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "rate_limited": rate_limited,
        "timed_out": timed_out,
        "success_rate": f"{(successful/total*100):.1f}%" if total > 0 else "0%",
        "by_tool": dict(by_tool),
        "top_targets": top_targets,
        "failed_scans": failed_scans[:20]  # Limit to 20 most recent
    }

# Default configuration
DEFAULT_KALI_SERVER = "http://localhost:5000"  # Change to your Kali VM IP
DEFAULT_REQUEST_TIMEOUT = 1800  # 30 minutes default timeout for API requests

# Default API key for research/development (matches kali_server.py)
DEFAULT_API_KEY = "kali-research-project-2026"
API_KEY = os.environ.get("KALI_API_KEY", DEFAULT_API_KEY)

class KaliToolsClient:
    """Client for communicating with the Kali Linux Tools API Server"""
    
    def __init__(self, server_url: str, timeout: int = DEFAULT_REQUEST_TIMEOUT, api_key: Optional[str] = None):
        """
        Initialize the Kali Tools Client
        
        Args:
            server_url: URL of the Kali Tools API Server
            timeout: Request timeout in seconds
            api_key: Optional API key for authentication
        """
        # Ensure URL has a protocol prefix
        if not server_url.startswith(('http://', 'https://')):
            server_url = f'http://{server_url}'
        
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key
        self.headers = {}
        
        if self.api_key:
            self.headers["X-API-Key"] = self.api_key
            logger.info(f"Initialized Kali Tools Client with authentication")
        else:
            logger.warning("Initialized Kali Tools Client WITHOUT authentication - set KALI_API_KEY for security")
        
        logger.info(f"Connecting to {self.server_url}")
        
    def safe_get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Perform a GET request with optional query parameters.
        
        Args:
            endpoint: API endpoint path (without leading slash)
            params: Optional query parameters
            
        Returns:
            Response data as dictionary
        """
        if params is None:
            params = {}

        url = f"{self.server_url}/{endpoint}"

        try:
            logger.debug(f"GET {url} with params: {params}")
            response = requests.get(url, params=params, timeout=self.timeout, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            return {"error": f"Request failed: {str(e)}", "success": False}
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}", "success": False}

    def safe_post(self, endpoint: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform a POST request with JSON data.
        
        Args:
            endpoint: API endpoint path (without leading slash)
            json_data: JSON data to send
            
        Returns:
            Response data as dictionary
        """
        url = f"{self.server_url}/{endpoint}"
        
        try:
            logger.debug(f"POST {url} with data: {json_data}")
            response = requests.post(url, json=json_data, timeout=self.timeout, headers=self.headers)
            
            # Handle rate limiting gracefully
            if response.status_code == 429:
                logger.warning(f"Rate limit exceeded for {endpoint}")
                return {
                    "error": "Rate limit exceeded. Please wait before retrying.",
                    "success": False,
                    "rate_limited": True,
                    "status_code": 429,
                    "retry_after": response.headers.get("Retry-After", "60 seconds")
                }
            
            # Handle concurrent scan limit
            if response.status_code == 503:
                logger.warning(f"Service temporarily unavailable (likely max concurrent scans reached)")
                return {
                    "error": "Maximum concurrent scans reached. Please wait for running scans to complete.",
                    "success": False,
                    "concurrent_limit_reached": True,
                    "status_code": 503
                }
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning(f"Rate limit exceeded for {endpoint}")
                return {
                    "error": "Rate limit exceeded. Please wait before retrying.",
                    "success": False,
                    "rate_limited": True,
                    "status_code": 429
                }
            logger.error(f"HTTP error: {str(e)}")
            return {"error": f"HTTP error: {str(e)}", "success": False, "status_code": e.response.status_code}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            return {"error": f"Request failed: {str(e)}", "success": False}
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}", "success": False}

    def execute_command(self, command: str) -> Dict[str, Any]:
        """
        Execute a generic command on the Kali server
        
        Args:
            command: Command to execute
            
        Returns:
            Command execution results
        """
        return self.safe_post("api/command", {"command": command})
    
    def check_health(self) -> Dict[str, Any]:
        """
        Check the health of the Kali Tools API Server
        
        Returns:
            Health status information
        """
        return self.safe_get("health")

def format_scan_result(result: Dict[str, Any], tool_name: str) -> str:
    """
    Format scan results into a readable report, handling errors gracefully.
    
    Args:
        result: The result dictionary from a tool execution
        tool_name: Name of the tool that was executed
        
    Returns:
        Formatted string report
    """
    report = f"\n{'='*80}\n{tool_name.upper()} SCAN REPORT\n{'='*80}\n\n"
    
    # Handle rate limiting
    if result.get("rate_limited"):
        report += "⚠️  RATE LIMIT REACHED\n"
        report += f"Status: Rate limit exceeded\n"
        report += f"Retry After: {result.get('retry_after', 'Unknown')}\n"
        report += "\nThis is a protective measure to prevent VM overload.\n"
        report += "Please wait before running additional scans.\n"
        return report
    
    # Handle concurrent scan limit
    if result.get("concurrent_limit_reached"):
        report += "⚠️  CONCURRENT SCAN LIMIT REACHED\n"
        report += "Status: Maximum concurrent scans running\n"
        report += "\nPlease wait for running scans to complete before starting new ones.\n"
        return report
    
    # Handle general errors
    if not result.get("success", False) and result.get("error"):
        report += f"❌ ERROR: {result['error']}\n"
        
        # Still show partial results if available
        if result.get("stdout"):
            report += f"\n📊 PARTIAL OUTPUT:\n{'-'*80}\n"
            report += result["stdout"][:5000]  # Limit to first 5000 chars
            if len(result["stdout"]) > 5000:
                report += "\n... (output truncated for readability)"
        
        return report
    
    # Handle timeout with partial results
    if result.get("timed_out") and result.get("partial_results"):
        report += "⏱️  SCAN TIMED OUT (Partial Results Available)\n\n"
    
    # Show successful results
    if result.get("success"):
        report += "✅ SCAN COMPLETED SUCCESSFULLY\n\n"
    
    # Add stdout output
    if result.get("stdout"):
        report += f"📊 OUTPUT:\n{'-'*80}\n"
        report += result["stdout"]
        report += f"\n{'-'*80}\n"
    
    # Add stderr if present
    if result.get("stderr") and result["stderr"].strip():
        report += f"\n⚠️  WARNINGS/ERRORS:\n{'-'*80}\n"
        report += result["stderr"]
        report += f"\n{'-'*80}\n"
    
    # Add metadata
    report += f"\nReturn Code: {result.get('return_code', 'N/A')}\n"
    
    if result.get("timed_out"):
        report += "Note: Scan timed out but partial results are shown above.\n"
    
    report += f"\n{'='*80}\n"
    return report

def setup_mcp_server(kali_client: KaliToolsClient) -> FastMCP:
    """
    Set up the MCP server with all tool functions
    
    Args:
        kali_client: Initialized KaliToolsClient
        
    Returns:
        Configured FastMCP instance
    """
    mcp = FastMCP("kali_mcp")
    
    @mcp.tool(name="nmap_scan")
    def nmap_scan(target: str, scan_type: str = "-sV", ports: str = "", additional_args: str = "") -> str:
        """
        Execute an Nmap scan against a target.
        
        Args:
            target: The IP address or hostname to scan
            scan_type: Scan type (e.g., -sV for version detection)
            ports: Comma-separated list of ports or port ranges
            additional_args: Additional Nmap arguments
            
        Returns:
            Formatted scan report (handles rate limits gracefully)
        """
        data = {
            "target": target,
            "scan_type": scan_type,
            "ports": ports,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/nmap", data)
        
        # Save raw result to file (for both success and failure)
        filepath = save_result_to_file("nmap", target, result)
        
        # Format result for display
        formatted = format_scan_result(result, f"Nmap Scan: {target}")
        
        # Add file location to result
        if filepath:
            formatted += f"\n📁 Results saved to: {filepath}\n"
            formatted += "💾 You can review this file even if the connection is lost.\n"
        
        # Add scan ID if available
        if result.get("scan_id"):
            formatted += f"🔍 Scan ID: {result['scan_id']}\n"
            formatted += "   Use 'get_scan_details' to retrieve this scan later.\n"
        
        return formatted

    @mcp.tool(name="gobuster_scan")
    def gobuster_scan(url: str, mode: str = "dir", wordlist: str = "/usr/share/wordlists/dirb/common.txt", additional_args: str = "") -> Dict[str, Any]:
        """
        Execute Gobuster to find directories, DNS subdomains, or virtual hosts.
        
        Args:
            url: The target URL
            mode: Scan mode (dir, dns, fuzz, vhost)
            wordlist: Path to wordlist file
            additional_args: Additional Gobuster arguments
            
        Returns:
            Scan results
        """
        data = {
            "url": url,
            "mode": mode,
            "wordlist": wordlist,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/gobuster", data)
        
        # Save raw result to file (for both success and failure)
        save_result_to_file("gobuster", url, result)
        
        return result

    @mcp.tool(name="feroxbuster_scan")
    def feroxbuster_scan(url: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt", threads: int = 50, max_results: int = 200, additional_args: str = "") -> Dict[str, Any]:
        """
        Execute Feroxbuster web content scanner (modern replacement for DIRB).
        
        Args:
            url: The target URL
            wordlist: Path to wordlist file
            threads: Number of concurrent threads
            max_results: Maximum number of results to return (default: 200)
            additional_args: Additional Feroxbuster arguments
            
        Returns:
            Scan results
        """
        data = {
            "url": url,
            "wordlist": wordlist,
            "threads": threads,
            "max_results": max_results,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/feroxbuster", data)
        
        # Save raw result to file (for both success and failure)
        save_result_to_file("feroxbuster", url, result)
        
        return result

    @mcp.tool(name="nikto_scan")
    def nikto_scan(target: str, additional_args: str = "") -> Dict[str, Any]:
        """
        Execute Nikto web server scanner.
        
        Args:
            target: The target URL or IP
            additional_args: Additional Nikto arguments
            
        Returns:
            Scan results
        """
        data = {
            "target": target,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/nikto", data)
        
        # Save raw result to file (for both success and failure)
        save_result_to_file("nikto", target, result)
        
        return result

    @mcp.tool(name="sqlmap_scan")
    def sqlmap_scan(url: str, data: str = "", additional_args: str = "") -> Dict[str, Any]:
        """
        Execute SQLmap SQL injection scanner.
        
        Args:
            url: The target URL
            data: POST data string
            additional_args: Additional SQLmap arguments
            
        Returns:
            Scan results
        """
        post_data = {
            "url": url,
            "data": data,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/sqlmap", post_data)
        
        # Save raw result to file (for both success and failure)
        save_result_to_file("sqlmap", url, result)
        
        return result

    @mcp.tool(name="metasploit_run")
    def metasploit_run(module: str, options: Dict[str, Any] = {}) -> str:
        """
        Execute a Metasploit Framework module.
        
        Args:
            module: The Metasploit module path (e.g., "exploit/windows/smb/ms17_010_eternalblue")
            options: Dictionary of module options (e.g., {"RHOSTS": "192.168.1.100", "LHOST": "192.168.1.50"})
            
        Returns:
            Formatted module execution report
            
        Examples:
            - Scan: metasploit_run("auxiliary/scanner/smb/smb_version", {"RHOSTS": "192.168.1.0/24"})
            - Exploit: metasploit_run("exploit/multi/handler", {"PAYLOAD": "windows/meterpreter/reverse_tcp", "LHOST": "192.168.1.50"})
        """
        data = {
            "module": module,
            "options": options
        }
        result = kali_client.safe_post("api/tools/metasploit", data)
        
        # Extract target for filename
        target = options.get("RHOSTS", options.get("RHOST", module.split('/')[-1]))
        
        # Save raw result to file (for both success and failure)
        filepath = save_result_to_file("metasploit", target, result)
        
        # Format result for display
        formatted = format_scan_result(result, f"Metasploit: {module}")
        
        # Add file location to result
        if filepath:
            formatted += f"\n📁 Results saved to: {filepath}\n"
        
        return formatted

    @mcp.tool(name="hydra_attack")
    def hydra_attack(
        target: str, 
        service: str, 
        username: str = "", 
        username_file: str = "", 
        password: str = "", 
        password_file: str = "", 
        additional_args: str = ""
    ) -> Dict[str, Any]:
        """
        Execute Hydra password cracking tool.
        
        Args:
            target: Target IP or hostname
            service: Service to attack (ssh, ftp, http-post-form, etc.)
            username: Single username to try
            username_file: Path to username file
            password: Single password to try
            password_file: Path to password file
            additional_args: Additional Hydra arguments
            
        Returns:
            Attack results
        """
        data = {
            "target": target,
            "service": service,
            "username": username,
            "username_file": username_file,
            "password": password,
            "password_file": password_file,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/hydra", data)
        
        # Save raw result to file (for both success and failure)
        save_result_to_file("hydra", f"{target}_{service}", result)
        
        return result

    @mcp.tool(name="john_crack")
    def john_crack(
        hash_file: str, 
        wordlist: str = "/usr/share/wordlists/rockyou.txt", 
        format_type: str = "", 
        additional_args: str = ""
    ) -> Dict[str, Any]:
        """
        Execute John the Ripper password cracker.
        
        Args:
            hash_file: Path to file containing hashes
            wordlist: Path to wordlist file
            format_type: Hash format type
            additional_args: Additional John arguments
            
        Returns:
            Cracking results
        """
        data = {
            "hash_file": hash_file,
            "wordlist": wordlist,
            "format": format_type,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/john", data)
        
        # Save raw result to file (for both success and failure)
        save_result_to_file("john", hash_file.split('/')[-1], result)
        
        return result

    @mcp.tool(name="wpscan_analyze")
    def wpscan_analyze(url: str, additional_args: str = "") -> Dict[str, Any]:
        """
        Execute WPScan WordPress vulnerability scanner.
        
        Args:
            url: The target WordPress URL
            additional_args: Additional WPScan arguments
            
        Returns:
            Scan results
        """
        data = {
            "url": url,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/wpscan", data)
        
        # Save raw result to file (for both success and failure)
        save_result_to_file("wpscan", url, result)
        
        return result

    @mcp.tool(name="enum4linux_ng_scan")
    def enum4linux_ng_scan(target: str, additional_args: str = "-A") -> Dict[str, Any]:
        """
        Execute Enum4linux-ng Windows/Samba enumeration tool (modern version).
        
        Args:
            target: The target IP or hostname
            additional_args: Additional enum4linux-ng arguments
            
        Returns:
            Enumeration results
        """
        data = {
            "target": target,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/enum4linux-ng", data)
        
        # Save raw result to file (for both success and failure)
        save_result_to_file("enum4linux-ng", target, result)
        
        return result

    @mcp.tool(name="ffuf_scan")
    def ffuf_scan(url: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt", mode: str = "dir", max_results: int = 100, additional_args: str = "") -> Dict[str, Any]:
        """
        Execute FFUF (Fuzz Faster U Fool) web fuzzer.
        
        Args:
            url: The target URL with FUZZ keyword
            wordlist: Path to wordlist file
            mode: Fuzzing mode (dir, subdomain, parameter, etc.)
            max_results: Maximum number of results to return (default: 100)
            additional_args: Additional FFUF arguments
            
        Returns:
            Fuzzing results
        """
        data = {
            "url": url,
            "wordlist": wordlist,
            "mode": mode,
            "max_results": max_results,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/ffuf", data)
        
        # Save raw result to file (for both success and failure)
        save_result_to_file("ffuf", url, result)
        
        return result

    @mcp.tool(name="amass_scan")
    def amass_scan(domain: str, mode: str = "enum", additional_args: str = "") -> Dict[str, Any]:
        """
        Execute Amass subdomain enumeration and network mapping.
        
        Args:
            domain: The target domain
            mode: Amass mode (enum, intel, viz, track, db)
            additional_args: Additional Amass arguments
            
        Returns:
            Enumeration results
        """
        data = {
            "domain": domain,
            "mode": mode,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/amass", data)
        
        # Save raw result to file (for both success and failure)
        save_result_to_file("amass", domain, result)
        
        return result

    @mcp.tool(name="hashcat_crack")
    def hashcat_crack(
        hash_file: str, 
        wordlist: str = "/usr/share/wordlists/rockyou.txt", 
        hash_type: str = "", 
        attack_mode: int = 0,
        additional_args: str = ""
    ) -> Dict[str, Any]:
        """
        Execute Hashcat password cracker.
        
        Args:
            hash_file: Path to file containing hashes
            wordlist: Path to wordlist file
            hash_type: Hash type number (e.g., 0 for MD5, 1000 for NTLM)
            attack_mode: Attack mode (0=straight, 1=combination, 3=brute-force)
            additional_args: Additional Hashcat arguments
            
        Returns:
            Cracking results
        """
        data = {
            "hash_file": hash_file,
            "wordlist": wordlist,
            "hash_type": hash_type,
            "attack_mode": attack_mode,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/hashcat", data)
        
        # Save raw result to file (for both success and failure)
        save_result_to_file("hashcat", hash_file.split('/')[-1], result)
        
        return result

    @mcp.tool(name="nuclei_scan")
    def nuclei_scan(target: str, templates: str = "", severity: str = "critical,high,medium", additional_args: str = "") -> str:
        """
        Execute Nuclei vulnerability scanner with template-based detection.
        
        Args:
            target: The target URL or IP to scan
            templates: Template path or tags (e.g., "cves/", "exposures/", "technologies/")
            severity: Severity levels to report (critical, high, medium, low, info)
            additional_args: Additional Nuclei arguments
            
        Returns:
            Formatted scan report with detected vulnerabilities
            
        Examples:
            - CVE scan: nuclei_scan("https://example.com", templates="cves/", severity="critical,high")
            - Full scan: nuclei_scan("https://example.com")
            - Specific tech: nuclei_scan("https://example.com", templates="technologies/wordpress/")
        """
        data = {
            "target": target,
            "templates": templates,
            "severity": severity,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/nuclei", data)
        
        # Save raw result to file (for both success and failure)
        filepath = save_result_to_file("nuclei", target, result)
        
        # Format result for display
        formatted = format_scan_result(result, f"Nuclei: {target}")
        
        # Add file location to result
        if filepath:
            formatted += f"\n📁 Results saved to: {filepath}\n"
        
        return formatted

    @mcp.tool(name="masscan_scan")
    def masscan_scan(target: str, ports: str = "1-65535", rate: int = 1000, additional_args: str = "") -> str:
        """
        Execute Masscan fast port scanner (faster than nmap for large ranges).
        
        Args:
            target: The target IP or CIDR range to scan
            ports: Port range to scan (default: all ports)
            rate: Packets per second (default: 1000, max: 10000)
            additional_args: Additional Masscan arguments
            
        Returns:
            Formatted scan report with open ports
            
        Examples:
            - Quick scan: masscan_scan("192.168.1.0/24", ports="80,443,8080", rate=1000)
            - Full scan: masscan_scan("192.168.1.100")
            - Fast scan: masscan_scan("10.0.0.0/8", ports="22,80,443", rate=10000)
        """
        data = {
            "target": target,
            "ports": ports,
            "rate": rate,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/masscan", data)
        
        # Save raw result to file (for both success and failure)
        filepath = save_result_to_file("masscan", target, result)
        
        # Format result for display
        formatted = format_scan_result(result, f"Masscan: {target}")
        
        # Add file location to result
        if filepath:
            formatted += f"\n📁 Results saved to: {filepath}\n"
        
        return formatted

    @mcp.tool(name="subfinder_scan")
    def subfinder_scan(domain: str, additional_args: str = "-silent") -> str:
        """
        Execute Subfinder for passive subdomain discovery.
        
        Args:
            domain: The target domain to enumerate subdomains
            additional_args: Additional Subfinder arguments
            
        Returns:
            List of discovered subdomains
            
        Examples:
            - Basic: subfinder_scan("example.com")
            - Verbose: subfinder_scan("example.com", additional_args="-v")
            - With sources: subfinder_scan("example.com", additional_args="-sources")
        """
        data = {
            "domain": domain,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/subfinder", data)
        
        # Save raw result to file (for both success and failure)
        filepath = save_result_to_file("subfinder", domain, result)
        
        # Format result for display
        formatted = format_scan_result(result, f"Subfinder: {domain}")
        
        # Add file location to result
        if filepath:
            formatted += f"\n📁 Results saved to: {filepath}\n"
        
        return formatted

    @mcp.tool(name="searchsploit_search")
    def searchsploit_search(query: str, additional_args: str = "") -> str:
        """
        Search the Exploit Database for exploits matching the query.
        
        Args:
            query: Search term (software name, version, CVE, etc.)
            additional_args: Additional Searchsploit arguments (e.g., "--json", "--www")
            
        Returns:
            List of matching exploits with paths and descriptions
            
        Examples:
            - Search: searchsploit_search("apache 2.4")
            - CVE: searchsploit_search("CVE-2021-44228")
            - JSON: searchsploit_search("wordpress", additional_args="--json")
        """
        data = {
            "query": query,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/searchsploit", data)
        
        # Save raw result to file (for both success and failure)
        filepath = save_result_to_file("searchsploit", query, result)
        
        # Format result for display
        formatted = format_scan_result(result, f"Searchsploit: {query}")
        
        # Add file location to result
        if filepath:
            formatted += f"\n📁 Results saved to: {filepath}\n"
        
        return formatted

    @mcp.tool(name="whatweb_scan")
    def whatweb_scan(target: str, aggression: int = 1, additional_args: str = "") -> str:
        """
        Execute WhatWeb to identify web technologies and frameworks.
        
        Args:
            target: The target URL to analyze
            aggression: Aggression level 1-4 (1=stealthy, 4=aggressive)
            additional_args: Additional WhatWeb arguments
            
        Returns:
            Detected technologies, CMS, frameworks, and versions
            
        Examples:
            - Basic: whatweb_scan("https://example.com")
            - Aggressive: whatweb_scan("https://example.com", aggression=3)
            - Verbose: whatweb_scan("https://example.com", additional_args="-v")
        """
        data = {
            "target": target,
            "aggression": aggression,
            "additional_args": additional_args
        }
        result = kali_client.safe_post("api/tools/whatweb", data)
        
        # Save raw result to file (for both success and failure)
        filepath = save_result_to_file("whatweb", target, result)
        
        # Format result for display
        formatted = format_scan_result(result, f"WhatWeb: {target}")
        
        # Add file location to result
        if filepath:
            formatted += f"\n📁 Results saved to: {filepath}\n"
        
        return formatted

    @mcp.tool(name="server_health")
    def server_health() -> Dict[str, Any]:
        """
        Check the health status of the Kali API server.
        
        Returns:
            Server health information
        """
        return kali_client.check_health()
    
    @mcp.tool(name="execute_command")
    def execute_command(command: str) -> Dict[str, Any]:
        """
        Execute an arbitrary command on the Kali server.
        
        Args:
            command: The command to execute
            
        Returns:
            Command execution results
        """
        return kali_client.execute_command(command)
    
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
            return f"❌ Error: {result['error']}"
        
        scans = result.get("scans", [])
        
        if not scans:
            return "📋 No scan history found."
        
        report = f"\n{'='*80}\n📊 RECENT SCAN HISTORY ({len(scans)} scans)\n{'='*80}\n\n"
        
        for i, scan in enumerate(scans, 1):
            status_icon = "✅" if scan.get('status') == 'completed' else "⏳" if scan.get('status') == 'started' else "❌"
            
            report += f"{i}. {status_icon} {scan['tool'].upper()}\n"
            report += f"   Scan ID: {scan['scan_id']}\n"
            report += f"   Started: {scan['start_time']}\n"
            report += f"   Status: {scan['status']}\n"
            
            if scan.get('parameters'):
                # Show key parameters
                params = scan['parameters']
                if 'target' in params:
                    report += f"   Target: {params['target']}\n"
                elif 'url' in params:
                    report += f"   URL: {params['url']}\n"
                elif 'domain' in params:
                    report += f"   Domain: {params['domain']}\n"
            
            if scan.get('end_time'):
                report += f"   Completed: {scan['end_time']}\n"
            
            report += f"{'-'*80}\n\n"
        
        report += "💡 Tip: Use 'get_scan_details(scan_id)' to see full results\n"
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
            return f"❌ Error: {result['error']}"
        
        report = f"\n{'='*80}\n🔍 SCAN DETAILS: {scan_id}\n{'='*80}\n\n"
        report += f"Tool: {result['tool'].upper()}\n"
        report += f"Started: {result['start_time']}\n"
        report += f"Status: {result['status']}\n"
        
        if result.get('end_time'):
            report += f"Completed: {result['end_time']}\n"
        
        if result.get('parameters'):
            report += f"\n📋 Parameters:\n"
            for key, value in result['parameters'].items():
                report += f"   {key}: {value}\n"
        
        if result.get('result'):
            scan_result = result['result']
            report += f"\n{'='*80}\n📊 RESULTS\n{'='*80}\n\n"
            
            report += f"Success: {'✅ Yes' if scan_result.get('success') else '❌ No'}\n"
            report += f"Return Code: {scan_result.get('return_code', 'N/A')}\n"
            
            if scan_result.get('timed_out'):
                report += "⏱️  Note: Scan timed out (partial results may be available)\n"
            
            report += f"\nOutput Length: {scan_result.get('stdout_length', 0)} characters\n"
            report += f"Error Length: {scan_result.get('stderr_length', 0)} characters\n"
            
            report += "\n💡 Full output was saved to the results directory on the MCP server\n"
        
        return report
    
    @mcp.tool(name="analyze_all_results")
    def analyze_all_results() -> str:
        """
        Analyze all scan results in the results folder and provide statistics.
        
        Returns:
            Comprehensive analysis including success rates, tool usage, top targets, and failed scans
        """
        results = load_all_results()
        
        if not results:
            return "📋 No scan results found in the results folder."
        
        analysis = analyze_results(results)
        
        report = f"\n{'='*80}\n📊 SCAN RESULTS ANALYSIS\n{'='*80}\n\n"
        
        # Summary
        report += "📈 SUMMARY\n"
        report += f"{'─'*80}\n"
        report += f"Total scans: {analysis['total']}\n"
        report += f"Successful: {analysis['successful']} ({analysis['success_rate']})\n"
        report += f"Failed: {analysis['failed']}\n"
        report += f"Rate limited: {analysis['rate_limited']}\n"
        report += f"Timed out: {analysis['timed_out']}\n\n"
        
        # By tool
        report += "🔧 SCANS BY TOOL\n"
        report += f"{'─'*80}\n"
        for tool, stats in sorted(analysis['by_tool'].items()):
            report += f"{tool:20s}: {stats['total']:3d} total, {stats['success']:3d} success, {stats['failed']:3d} failed\n"
        report += "\n"
        
        # Top targets
        if analysis['top_targets']:
            report += "🎯 TOP 10 TARGETS\n"
            report += f"{'─'*80}\n"
            for item in analysis['top_targets']:
                report += f"{item['target']:50s}: {item['count']:3d} scans\n"
            report += "\n"
        
        # Failed scans
        if analysis['failed_scans']:
            report += f"❌ FAILED SCANS ({len(analysis['failed_scans'])} shown)\n"
            report += f"{'─'*80}\n"
            for scan in analysis['failed_scans']:
                report += f"Tool: {scan['tool']}\n"
                report += f"Target: {scan['target']}\n"
                report += f"Time: {scan['datetime']}\n"
                report += f"Error: {scan['error']}\n"
                if scan['stderr']:
                    report += f"Stderr: {scan['stderr']}...\n"
                report += f"{'─'*80}\n"
        
        report += f"\n{'='*80}\n"
        report += "💡 Use this analysis to generate professional penetration testing reports\n"
        report += "💡 All raw data is available in JSON format in the results/ folder\n"
        report += f"{'='*80}\n"
        
        return report
    
    @mcp.tool(name="get_results_for_target")
    def get_results_for_target(target: str) -> str:
        """
        Get all scan results for a specific target.
        
        Args:
            target: The target IP, URL, or domain to search for
            
        Returns:
            All scan results for the specified target
        """
        results = load_all_results()
        
        # Filter by target (partial match)
        target_results = [r for r in results if target.lower() in r.get('target', '').lower()]
        
        if not target_results:
            return f"📋 No scan results found for target: {target}"
        
        report = f"\n{'='*80}\n🎯 SCAN RESULTS FOR: {target}\n{'='*80}\n\n"
        report += f"Found {len(target_results)} scan(s)\n\n"
        
        for i, result in enumerate(target_results, 1):
            status_icon = "✅" if result.get('success') else "❌"
            report += f"{i}. {status_icon} {result['tool'].upper()}\n"
            report += f"   Time: {result.get('datetime', 'Unknown')}\n"
            report += f"   Success: {result.get('success', False)}\n"
            
            if not result.get('success'):
                report += f"   Error: {result.get('error', 'Unknown error')}\n"
            
            if result.get('scan_id'):
                report += f"   Scan ID: {result['scan_id']}\n"
            
            # Show brief output preview
            stdout = result.get('stdout', '')
            if stdout:
                preview = stdout[:200].replace('\n', ' ')
                report += f"   Output: {preview}...\n"
            
            report += f"{'─'*80}\n\n"
        
        report += "💡 Full results are available in the results/ folder as JSON files\n"
        return report
    
    @mcp.tool(name="export_results_summary")
    def export_results_summary(output_file: str = "scan_summary.json") -> str:
        """
        Export a summary of all scan results to a JSON file.
        
        Args:
            output_file: Output filename (default: scan_summary.json)
            
        Returns:
            Status message with file location
        """
        try:
            results = load_all_results()
            analysis = analyze_results(results)
            
            # Add timestamp
            analysis['generated_at'] = datetime.now().isoformat()
            analysis['total_results_files'] = len(results)
            
            output_path = os.path.join(RESULTS_DIR, output_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)
            
            return f"✅ Summary exported to: {output_path}\n\nContains:\n- Statistics\n- Tool usage\n- Top targets\n- Failed scans\n\nUse this file for report generation or further analysis."
        except Exception as e:
            return f"❌ Error exporting summary: {str(e)}"

    return mcp

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run the MCP Kali client")
    parser.add_argument("--server", type=str, default=DEFAULT_KALI_SERVER, 
                      help=f"Kali API server URL (default: {DEFAULT_KALI_SERVER})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_REQUEST_TIMEOUT,
                      help=f"Request timeout in seconds (default: {DEFAULT_REQUEST_TIMEOUT})")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()

def main():
    """Main entry point for the MCP server."""
    args = parse_args()
    
    # Configure logging based on debug flag
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Initialize the Kali Tools client
    kali_client = KaliToolsClient(args.server, args.timeout, API_KEY)
    
    # Check server health and log the result
    health = kali_client.check_health()
    if "error" in health:
        logger.warning(f"Unable to connect to Kali API server at {args.server}: {health['error']}")
        logger.warning("MCP server will start, but tool execution may fail")
    else:
        logger.info(f"Successfully connected to Kali API server at {args.server}")
        logger.info(f"Server health status: {health['status']}")
        if not health.get("all_essential_tools_available", False):
            logger.warning("Not all essential tools are available on the Kali server")
            missing_tools = [tool for tool, available in health.get("tools_status", {}).items() if not available]
            if missing_tools:
                logger.warning(f"Missing tools: {', '.join(missing_tools)}")
    
    # Set up and run the MCP server
    mcp = setup_mcp_server(kali_client)
    logger.info("Starting MCP Kali server")
    mcp.run()

if __name__ == "__main__":
    main()
