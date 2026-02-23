#!/usr/bin/env python3
"""
Ollama + MCP Kali Tools Client
Connects local Ollama AI to Kali penetration testing tools

Usage:
    python ollama_client.py                    # Interactive mode
    python ollama_client.py --prompt "..."     # Single command
    python ollama_client.py --model llama3.1:70b  # Use different model
"""

import argparse
import json
import os
import sys
from typing import Dict, Any, List

try:
    import ollama
except ImportError:
    print("❌ Error: 'ollama' package not installed")
    print("Install with: pip install ollama")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("❌ Error: 'requests' package not installed")
    print("Install with: pip install requests")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional

# Configuration from environment or defaults
KALI_SERVER = os.environ.get("KALI_SERVER_IP", "http://172.20.10.11:5000")
if not KALI_SERVER.startswith(('http://', 'https://')):
    KALI_SERVER = f'http://{KALI_SERVER}'

API_KEY = os.environ.get("KALI_API_KEY", "kali-research-project-2026")
DEFAULT_MODEL = "llama3.1:8b"
REQUEST_TIMEOUT = 1800  # 30 minutes


class KaliToolsClient:
    """Simple client for Kali API"""
    
    def __init__(self, server_url: str, api_key: str):
        self.server_url = server_url.rstrip("/")
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    
    def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST request to Kali API"""
        try:
            url = f"{self.server_url}/{endpoint}"
            response = requests.post(url, json=data, headers=self.headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def get(self, endpoint: str) -> Dict[str, Any]:
        """GET request to Kali API"""
        try:
            url = f"{self.server_url}/{endpoint}"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "success": False}


# Initialize Kali client
kali = KaliToolsClient(KALI_SERVER, API_KEY)


# Tool definitions for Ollama
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "server_health",
            "description": "Check if the Kali server is running and healthy",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "nmap_scan",
            "description": "Execute an Nmap network scan to discover open ports and services",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "IP address or hostname to scan (e.g., 192.168.1.1)"
                    },
                    "scan_type": {
                        "type": "string",
                        "description": "Scan type: -sV (version detection), -sS (stealth), -sT (TCP connect), -A (aggressive)"
                    },
                    "ports": {
                        "type": "string",
                        "description": "Ports to scan (e.g., '80,443' or '1-1000')"
                    }
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "nikto_scan",
            "description": "Execute Nikto web server vulnerability scanner",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target URL or IP (e.g., https://example.com)"
                    }
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gobuster_scan",
            "description": "Execute Gobuster to find hidden directories and files",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Target URL (e.g., https://example.com)"
                    },
                    "mode": {
                        "type": "string",
                        "description": "Scan mode: dir (directories), dns (subdomains), vhost (virtual hosts)"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sqlmap_scan",
            "description": "Execute SQLmap to test for SQL injection vulnerabilities",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Target URL with parameter (e.g., https://example.com/page?id=1)"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ffuf_scan",
            "description": "Execute FFUF web fuzzer to find hidden content",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Target URL with FUZZ keyword (e.g., https://example.com/FUZZ)"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_scan_history",
            "description": "Get recent scan history (useful after crashes or to review past scans)",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent scans to retrieve (default: 10)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "nuclei_scan",
            "description": "Execute Nuclei vulnerability scanner with template-based detection for CVEs and misconfigurations",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target URL or IP (e.g., https://example.com)"
                    },
                    "templates": {
                        "type": "string",
                        "description": "Template path or tags (e.g., 'cves/', 'exposures/')"
                    },
                    "severity": {
                        "type": "string",
                        "description": "Severity levels: critical,high,medium,low,info"
                    }
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "masscan_scan",
            "description": "Execute Masscan fast port scanner (faster than nmap for large networks)",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target IP or CIDR range (e.g., 192.168.1.0/24)"
                    },
                    "ports": {
                        "type": "string",
                        "description": "Port range (e.g., '80,443,8080' or '1-65535')"
                    },
                    "rate": {
                        "type": "integer",
                        "description": "Packets per second (default: 1000)"
                    }
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "subfinder_scan",
            "description": "Execute Subfinder for passive subdomain discovery",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Target domain (e.g., example.com)"
                    }
                },
                "required": ["domain"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "searchsploit_search",
            "description": "Search Exploit Database for exploits matching software/CVE",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (e.g., 'apache 2.4', 'CVE-2021-44228')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "whatweb_scan",
            "description": "Execute WhatWeb to identify web technologies, CMS, and frameworks",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target URL (e.g., https://example.com)"
                    },
                    "aggression": {
                        "type": "integer",
                        "description": "Aggression level 1-4 (1=stealthy, 4=aggressive)"
                    }
                },
                "required": ["target"]
            }
        }
    }
]


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Execute a Kali tool and return formatted results"""
    try:
        if tool_name == "server_health":
            result = kali.get("health")
            if result.get("error"):
                return f"❌ Error: {result['error']}"
            return f"""✅ Kali Server Health Check

Status: {result.get('status', 'unknown')}
Message: {result.get('message', 'N/A')}
All Tools Available: {result.get('all_essential_tools_available', False)}

Available Tools:
{json.dumps(result.get('tools_status', {}), indent=2)}
"""
        
        elif tool_name == "nmap_scan":
            result = kali.post("api/tools/nmap", arguments)
            return format_scan_result(result, "Nmap Scan")
        
        elif tool_name == "nikto_scan":
            result = kali.post("api/tools/nikto", arguments)
            return format_scan_result(result, "Nikto Scan")
        
        elif tool_name == "gobuster_scan":
            result = kali.post("api/tools/gobuster", arguments)
            return format_scan_result(result, "Gobuster Scan")
        
        elif tool_name == "sqlmap_scan":
            result = kali.post("api/tools/sqlmap", arguments)
            return format_scan_result(result, "SQLmap Scan")
        
        elif tool_name == "ffuf_scan":
            result = kali.post("api/tools/ffuf", arguments)
            return format_scan_result(result, "FFUF Scan")
        
        elif tool_name == "get_scan_history":
            limit = arguments.get("limit", 10)
            result = kali.get(f"api/scans/history?limit={limit}")
            if result.get("error"):
                return f"❌ Error: {result['error']}"
            
            scans = result.get("scans", [])
            if not scans:
                return "📋 No scan history found."
            
            output = f"\n📊 Recent Scan History ({len(scans)} scans)\n{'='*80}\n\n"
            for i, scan in enumerate(scans, 1):
                status_icon = "✅" if scan.get('status') == 'completed' else "⏳"
                output += f"{i}. {status_icon} {scan['tool'].upper()}\n"
                output += f"   Scan ID: {scan['scan_id']}\n"
                output += f"   Started: {scan['start_time']}\n"
                if scan.get('parameters', {}).get('target'):
                    output += f"   Target: {scan['parameters']['target']}\n"
                output += f"{'-'*80}\n\n"
            
            return output
        
        elif tool_name == "nuclei_scan":
            result = kali.post("api/tools/nuclei", arguments)
            return format_scan_result(result, "Nuclei Scan")
        
        elif tool_name == "masscan_scan":
            result = kali.post("api/tools/masscan", arguments)
            return format_scan_result(result, "Masscan Scan")
        
        elif tool_name == "subfinder_scan":
            result = kali.post("api/tools/subfinder", arguments)
            return format_scan_result(result, "Subfinder Scan")
        
        elif tool_name == "searchsploit_search":
            result = kali.post("api/tools/searchsploit", arguments)
            return format_scan_result(result, "Searchsploit Search")
        
        elif tool_name == "whatweb_scan":
            result = kali.post("api/tools/whatweb", arguments)
            return format_scan_result(result, "WhatWeb Scan")
        
        else:
            return f"❌ Unknown tool: {tool_name}"
    
    except Exception as e:
        return f"❌ Error executing {tool_name}: {str(e)}"


def format_scan_result(result: Dict[str, Any], tool_name: str) -> str:
    """Format scan results into readable text"""
    output = f"\n{'='*80}\n{tool_name.upper()} RESULTS\n{'='*80}\n\n"
    
    # Handle rate limiting
    if result.get("rate_limited"):
        output += "⚠️  RATE LIMIT REACHED\n"
        output += f"Retry After: {result.get('retry_after', 'Unknown')}\n"
        return output
    
    # Handle errors
    if not result.get("success") and result.get("error"):
        output += f"❌ ERROR: {result['error']}\n"
        if result.get("stdout"):
            output += f"\n📊 PARTIAL OUTPUT:\n{'-'*80}\n"
            output += result["stdout"][:3000]
        return output
    
    # Show success
    if result.get("success"):
        output += "✅ SCAN COMPLETED SUCCESSFULLY\n\n"
    
    # Add scan ID if available
    if result.get("scan_id"):
        output += f"🔍 Scan ID: {result['scan_id']}\n"
        output += "   (Use get_scan_history to retrieve later)\n\n"
    
    # Add output
    if result.get("stdout"):
        output += f"📊 OUTPUT:\n{'-'*80}\n"
        # Limit output to prevent overwhelming the AI
        stdout = result["stdout"]
        if len(stdout) > 5000:
            output += stdout[:5000]
            output += f"\n\n... (output truncated, {len(stdout)} total characters)"
        else:
            output += stdout
        output += f"\n{'-'*80}\n"
    
    # Add warnings
    if result.get("stderr") and result["stderr"].strip():
        output += f"\n⚠️  WARNINGS:\n{'-'*80}\n"
        output += result["stderr"][:1000]
        output += f"\n{'-'*80}\n"
    
    output += f"\n{'='*80}\n"
    return output


def chat(user_message: str, model: str, verbose: bool = True) -> str:
    """Send message to Ollama and handle tool calls"""
    
    messages = [
        {
            "role": "system",
            "content": """You are a professional penetration testing assistant with access to Kali Linux tools.

Available tools:
- server_health: Check if Kali server is running
- nmap_scan: Network scanning and port detection
- masscan_scan: Fast port scanner for large networks (faster than nmap)
- nikto_scan: Web server vulnerability scanning
- gobuster_scan: Directory and file enumeration
- sqlmap_scan: SQL injection testing
- ffuf_scan: Web fuzzing and content discovery
- nuclei_scan: Modern vulnerability scanner with CVE detection
- subfinder_scan: Passive subdomain discovery
- searchsploit_search: Search exploit database
- whatweb_scan: Web technology and CMS detection
- get_scan_history: View recent scans (useful after crashes)

When the user asks to scan or test something:
1. Use the appropriate tool(s)
2. Analyze the results
3. Explain findings in clear, professional language
4. Suggest next steps or additional scans if needed

Always prioritize security and ethical testing practices."""
        },
        {
            "role": "user",
            "content": user_message
        }
    ]
    
    if verbose:
        print(f"\n🤖 AI: Thinking...\n")
    
    try:
        # Call Ollama with tools
        response = ollama.chat(
            model=model,
            messages=messages,
            tools=TOOLS
        )
        
        # Check if AI wants to use a tool
        if response.get('message', {}).get('tool_calls'):
            for tool_call in response['message']['tool_calls']:
                tool_name = tool_call['function']['name']
                arguments = tool_call['function']['arguments']
                
                if verbose:
                    print(f"🔧 Executing: {tool_name}")
                    print(f"📋 Parameters: {json.dumps(arguments, indent=2)}\n")
                
                # Execute the tool
                result = execute_tool(tool_name, arguments)
                
                if verbose:
                    print(f"📊 Results:\n{result}\n")
                
                # Send results back to AI for interpretation
                messages.append(response['message'])
                messages.append({
                    "role": "tool",
                    "content": result
                })
                
                # Get AI's interpretation
                final_response = ollama.chat(
                    model=model,
                    messages=messages
                )
                
                analysis = final_response['message']['content']
                
                if verbose:
                    print(f"🤖 AI Analysis:\n{analysis}\n")
                
                return analysis
        
        else:
            # No tool call, just a regular response
            response_text = response['message']['content']
            if verbose:
                print(f"🤖 AI: {response_text}\n")
            return response_text
    
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        if verbose:
            print(error_msg)
        return error_msg


def interactive_mode(model: str):
    """Interactive chat loop"""
    print("="*80)
    print("🛡️  Ollama + Kali MCP Client")
    print("="*80)
    print(f"Model: {model}")
    print(f"Kali Server: {KALI_SERVER}")
    print("Type 'exit' to quit, 'help' for examples\n")
    
    # Test connection
    print("🔍 Testing Kali server connection...")
    health = kali.get("health")
    if health.get("error"):
        print(f"❌ Error: {health['error']}")
        print("\n⚠️  Make sure:")
        print("  1. Kali VM is running")
        print("  2. kali_server.py is running on Kali")
        print("  3. IP address in .env is correct")
        print("  4. Firewall allows port 5000")
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
            
            if user_input.lower() == 'help':
                print("""
📚 Example Commands:

1. Check server health:
   "Check if the Kali server is healthy"

2. Basic port scan:
   "Scan 192.168.1.1 with nmap"

3. Web vulnerability scan:
   "Use nikto to scan https://example.com"

4. Directory enumeration:
   "Find hidden directories on https://example.com"

5. SQL injection test:
   "Test https://example.com/page?id=1 for SQL injection"

6. View scan history:
   "Show me recent scan history"

7. Full pentest:
   "Run a complete penetration test on 192.168.1.100"
""")
                continue
            
            chat(user_input, model)
        
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Ollama + Kali MCP Client - AI-powered penetration testing"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Ollama model to use (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="Single prompt to execute (non-interactive mode)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output (only final response)"
    )
    
    args = parser.parse_args()
    
    # Check if Ollama is available
    try:
        ollama.list()
    except Exception as e:
        print("❌ Error: Cannot connect to Ollama")
        print("\nMake sure Ollama is installed and running:")
        print("  1. Download from: https://ollama.ai/download")
        print("  2. Install and restart your terminal")
        print("  3. Pull a model: ollama pull llama3.1:8b")
        sys.exit(1)
    
    # Check if model is available
    try:
        models = ollama.list()
        model_names = [m['name'] for m in models.get('models', [])]
        if args.model not in model_names:
            print(f"❌ Error: Model '{args.model}' not found")
            print(f"\nAvailable models: {', '.join(model_names)}")
            print(f"\nPull the model with: ollama pull {args.model}")
            sys.exit(1)
    except Exception as e:
        print(f"⚠️  Warning: Could not verify model availability: {str(e)}")
    
    # Run in appropriate mode
    if args.prompt:
        # Single prompt mode
        chat(args.prompt, args.model, verbose=not args.quiet)
    else:
        # Interactive mode
        interactive_mode(args.model)


if __name__ == "__main__":
    main()
