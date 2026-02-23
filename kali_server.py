#!/usr/bin/env python3

# This script connect the MCP AI agent to Kali Linux terminal and API Server.

# some of the code here was inspired from https://github.com/whit3rabbit0/project_astro , be sure to check them out

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import traceback
import threading
from typing import Dict, Any
from datetime import datetime
from flask import Flask, request, jsonify
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
API_PORT = int(os.environ.get("API_PORT", 5000))
DEBUG_MODE = os.environ.get("DEBUG_MODE", "0").lower() in ("1", "true", "yes", "y")
COMMAND_TIMEOUT = 180  # 5 minutes default timeout
API_KEY = os.environ.get("KALI_API_KEY", "kali-research-project-2026")

# Scan logging directory
SCAN_LOG_DIR = "/opt/scans/logs"
os.makedirs(SCAN_LOG_DIR, exist_ok=True)

app = Flask(__name__)

# Security decorators
def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get API key from header
        provided_key = request.headers.get('X-API-Key')
        
        # Check if API key matches
        if provided_key != API_KEY:
            logger.warning(f"Invalid API key attempt from {request.remote_addr}")
            return jsonify({
                "error": "Invalid or missing API key",
                "message": "Please provide a valid X-API-Key header"
            }), 401
        
        return f(*args, **kwargs)
    return decorated_function

def dynamic_rate_limit(tool_name):
    """Decorator for dynamic rate limiting (placeholder - not fully implemented)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Simple rate limiting could be added here
            # For now, just pass through
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def sanitize_arg(arg):
    """Sanitize command arguments to prevent injection"""
    if isinstance(arg, str):
        # Remove potentially dangerous characters
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        sanitized = str(arg)
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        return sanitized
    return str(arg)

def build_safe_command(base_command, args_list):
    """Build a safe command from base and arguments"""
    command = base_command
    for arg in args_list:
        command += f" {sanitize_arg(arg)}"
    return command

# Scan logging functions
def log_scan_request(tool_name: str, params: dict, client_ip: str) -> str:
    """Log scan request with unique ID"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        scan_id = f"{tool_name}_{timestamp}_{client_ip.replace('.', '_')}"
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
    except Exception as e:
        logger.error(f"Error logging scan request: {str(e)}")
        return f"error_{timestamp}"

def log_scan_result(scan_id: str, result: dict):
    """Update scan log with results"""
    try:
        log_file = f"{SCAN_LOG_DIR}/{scan_id}.json"
        
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                log_data = json.load(f)
            
            log_data.update({
                "end_time": datetime.now().isoformat(),
                "status": "completed" if result.get("success") else "failed",
                "result": {
                    "success": result.get("success"),
                    "return_code": result.get("return_code"),
                    "stdout_length": len(result.get("stdout", "")),
                    "stderr_length": len(result.get("stderr", "")),
                    "timed_out": result.get("timed_out", False)
                }
            })
            
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
            
            logger.info(f"Scan result logged: {scan_id}")
    except Exception as e:
        logger.error(f"Error logging scan result: {str(e)}")

class CommandExecutor:
    """Class to handle command execution with better timeout management"""
    
    def __init__(self, command: str, timeout: int = COMMAND_TIMEOUT):
        self.command = command
        self.timeout = timeout
        self.process = None
        self.stdout_data = ""
        self.stderr_data = ""
        self.stdout_thread = None
        self.stderr_thread = None
        self.return_code = None
        self.timed_out = False
    
    def _read_stdout(self):
        """Thread function to continuously read stdout"""
        for line in iter(self.process.stdout.readline, ''):
            self.stdout_data += line
    
    def _read_stderr(self):
        """Thread function to continuously read stderr"""
        for line in iter(self.process.stderr.readline, ''):
            self.stderr_data += line
    
    def execute(self) -> Dict[str, Any]:
        """Execute the command and handle timeout gracefully"""
        logger.info(f"Executing command: {self.command}")
        
        try:
            self.process = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )
            
            # Start threads to read output continuously
            self.stdout_thread = threading.Thread(target=self._read_stdout)
            self.stderr_thread = threading.Thread(target=self._read_stderr)
            self.stdout_thread.daemon = True
            self.stderr_thread.daemon = True
            self.stdout_thread.start()
            self.stderr_thread.start()
            
            # Wait for the process to complete or timeout
            try:
                self.return_code = self.process.wait(timeout=self.timeout)
                # Process completed, join the threads
                self.stdout_thread.join()
                self.stderr_thread.join()
            except subprocess.TimeoutExpired:
                # Process timed out but we might have partial results
                self.timed_out = True
                logger.warning(f"Command timed out after {self.timeout} seconds. Terminating process.")
                
                # Try to terminate gracefully first
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)  # Give it 5 seconds to terminate
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate
                    logger.warning("Process not responding to termination. Killing.")
                    self.process.kill()
                
                # Update final output
                self.return_code = -1
            
            # Always consider it a success if we have output, even with timeout
            success = True if self.timed_out and (self.stdout_data or self.stderr_data) else (self.return_code == 0)
            
            return {
                "stdout": self.stdout_data,
                "stderr": self.stderr_data,
                "return_code": self.return_code,
                "success": success,
                "timed_out": self.timed_out,
                "partial_results": self.timed_out and (self.stdout_data or self.stderr_data)
            }
        
        except Exception as e:
            logger.error(f"Error executing command: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "stdout": self.stdout_data,
                "stderr": f"Error executing command: {str(e)}\n{self.stderr_data}",
                "return_code": -1,
                "success": False,
                "timed_out": False,
                "partial_results": bool(self.stdout_data or self.stderr_data)
            }


def execute_command(command: str) -> Dict[str, Any]:
    """
    Execute a shell command and return the result
    
    Args:
        command: The command to execute
        
    Returns:
        A dictionary containing the stdout, stderr, and return code
    """
    executor = CommandExecutor(command)
    return executor.execute()


@app.route("/api/command", methods=["POST"])
def generic_command():
    """Execute any command provided in the request."""
    try:
        params = request.json
        command = params.get("command", "")
        
        if not command:
            logger.warning("Command endpoint called without command parameter")
            return jsonify({
                "error": "Command parameter is required"
            }), 400
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in command endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500


@app.route("/api/tools/nmap", methods=["POST"])
def nmap():
    """Execute nmap scan with the provided parameters."""
    scan_id = None
    try:
        params = request.json
        target = params.get("target", "")
        scan_type = params.get("scan_type", "-sCV")
        ports = params.get("ports", "")
        additional_args = params.get("additional_args", "-T4 -Pn")
        
        if not target:
            logger.warning("Nmap called without target parameter")
            return jsonify({
                "error": "Target parameter is required"
            }), 400
        
        # Log scan request
        scan_id = log_scan_request("nmap", params, request.remote_addr)
        
        command = f"nmap {scan_type}"
        
        if ports:
            command += f" -p {ports}"
        
        if additional_args:
            # Basic validation for additional args - more sophisticated validation would be better
            command += f" {additional_args}"
        
        command += f" {target}"
        
        result = execute_command(command)
        
        # Log scan result
        if scan_id:
            log_scan_result(scan_id, result)
            result["scan_id"] = scan_id
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in nmap endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Log failed scan
        if scan_id:
            log_scan_result(scan_id, {"success": False, "error": str(e)})
        
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/gobuster", methods=["POST"])
def gobuster():
    """Execute gobuster with the provided parameters."""
    try:
        params = request.json
        url = params.get("url", "")
        mode = params.get("mode", "dir")
        wordlist = params.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        additional_args = params.get("additional_args", "")
        
        if not url:
            logger.warning("Gobuster called without URL parameter")
            return jsonify({
                "error": "URL parameter is required"
            }), 400
        
        # Validate mode
        if mode not in ["dir", "dns", "fuzz", "vhost"]:
            logger.warning(f"Invalid gobuster mode: {mode}")
            return jsonify({
                "error": f"Invalid mode: {mode}. Must be one of: dir, dns, fuzz, vhost"
            }), 400
        
        command = f"gobuster {mode} -u {url} -w {wordlist}"
        
        if additional_args:
            command += f" {additional_args}"
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in gobuster endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/feroxbuster", methods=["POST"])
def feroxbuster():
    """Execute feroxbuster with the provided parameters."""
    try:
        params = request.json
        url = params.get("url", "")
        wordlist = params.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        threads = params.get("threads", 50)
        additional_args = params.get("additional_args", "")
        max_results = params.get("max_results", 200)
        
        if not url:
            logger.warning("Feroxbuster called without URL parameter")
            return jsonify({
                "error": "URL parameter is required"
            }), 400
        
        # Use JSON output for better parsing
        command = f"feroxbuster -u {url} -w {wordlist} -t {threads} -o /tmp/ferox_output.json --json"
        
        # Add common filters if not specified
        if "-C" not in additional_args and "--filter-status" not in additional_args:
            command += " -C 404"
        
        if additional_args:
            command += f" {additional_args}"
        
        result = execute_command(command)
        
        # Try to parse and limit the JSON output
        try:
            if result.get("success") and os.path.exists("/tmp/ferox_output.json"):
                results = []
                with open("/tmp/ferox_output.json", "r") as f:
                    for line_num, line in enumerate(f):
                        if line_num >= max_results:
                            break
                        try:
                            results.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue
                
                result["parsed_output"] = {
                    "results": results,
                    "truncated": line_num >= max_results,
                    "total_parsed": len(results)
                }
                
                # Clean up temp file
                os.remove("/tmp/ferox_output.json")
        except Exception as parse_error:
            logger.warning(f"Could not parse Feroxbuster JSON output: {str(parse_error)}")
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in feroxbuster endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/nikto", methods=["POST"])
def nikto():
    """Execute nikto with the provided parameters."""
    try:
        params = request.json
        target = params.get("target", "")
        additional_args = params.get("additional_args", "")
        
        if not target:
            logger.warning("Nikto called without target parameter")
            return jsonify({
                "error": "Target parameter is required"
            }), 400
        
        command = f"nikto -h {target}"
        
        if additional_args:
            command += f" {additional_args}"
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in nikto endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/sqlmap", methods=["POST"])
def sqlmap():
    """Execute sqlmap with the provided parameters."""
    try:
        params = request.json
        url = params.get("url", "")
        data = params.get("data", "")
        additional_args = params.get("additional_args", "")
        
        if not url:
            logger.warning("SQLMap called without URL parameter")
            return jsonify({
                "error": "URL parameter is required"
            }), 400
        
        command = f"sqlmap -u {url} --batch"
        
        if data:
            command += f" --data=\"{data}\""
        
        if additional_args:
            command += f" {additional_args}"
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in sqlmap endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/metasploit", methods=["POST"])
@require_api_key
@dynamic_rate_limit("metasploit")
def metasploit():
    """Execute metasploit module with the provided parameters."""
    try:
        params = request.json
        module = params.get("module", "")
        options = params.get("options", {})
        
        if not module:
            logger.warning("Metasploit called without module parameter")
            return jsonify({
                "error": "Module parameter is required"
            }), 400
        
        # Create an MSF resource script with secure temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.rc', delete=False, dir='/tmp') as tmp_file:
            resource_file = tmp_file.name
            resource_content = f"use {module}\n"
            for key, value in options.items():
                resource_content += f"set {sanitize_arg(key)} {sanitize_arg(value)}\n"
            resource_content += "run\nexit\n"
            tmp_file.write(resource_content)
        
        try:
            command = build_safe_command("msfconsole", ["-q", "-r", resource_file])
            result = execute_command(command)
        finally:
            # Clean up the temporary file
            try:
                if os.path.exists(resource_file):
                    os.remove(resource_file)
            except Exception as e:
                logger.warning(f"Error removing temporary resource file: {str(e)}")
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in metasploit endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/hydra", methods=["POST"])
def hydra():
    """Execute hydra with the provided parameters."""
    try:
        params = request.json
        target = params.get("target", "")
        service = params.get("service", "")
        username = params.get("username", "")
        username_file = params.get("username_file", "")
        password = params.get("password", "")
        password_file = params.get("password_file", "")
        additional_args = params.get("additional_args", "")
        
        if not target or not service:
            logger.warning("Hydra called without target or service parameter")
            return jsonify({
                "error": "Target and service parameters are required"
            }), 400
        
        if not (username or username_file) or not (password or password_file):
            logger.warning("Hydra called without username/password parameters")
            return jsonify({
                "error": "Username/username_file and password/password_file are required"
            }), 400
        
        command = f"hydra -t 4"
        
        if username:
            command += f" -l {username}"
        elif username_file:
            command += f" -L {username_file}"
        
        if password:
            command += f" -p {password}"
        elif password_file:
            command += f" -P {password_file}"
        
        command += f" {target} {service}"

        if additional_args:
            command += f" {additional_args}"
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in hydra endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/john", methods=["POST"])
def john():
    """Execute john with the provided parameters."""
    try:
        params = request.json
        hash_file = params.get("hash_file", "")
        wordlist = params.get("wordlist", "/usr/share/wordlists/rockyou.txt")
        format_type = params.get("format", "")
        additional_args = params.get("additional_args", "")
        
        if not hash_file:
            logger.warning("John called without hash_file parameter")
            return jsonify({
                "error": "Hash file parameter is required"
            }), 400
        
        command = f"john"
        
        if format_type:
            command += f" --format={format_type}"
        
        if wordlist:
            command += f" --wordlist={wordlist}"
        
        if additional_args:
            command += f" {additional_args}"
        
        command += f" {hash_file}"
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in john endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/wpscan", methods=["POST"])
def wpscan():
    """Execute wpscan with the provided parameters."""
    try:
        params = request.json
        url = params.get("url", "")
        additional_args = params.get("additional_args", "")
        
        if not url:
            logger.warning("WPScan called without URL parameter")
            return jsonify({
                "error": "URL parameter is required"
            }), 400
        
        command = f"wpscan --url {url}"
        
        if additional_args:
            command += f" {additional_args}"
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in wpscan endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/enum4linux-ng", methods=["POST"])
def enum4linux_ng():
    """Execute enum4linux-ng with the provided parameters."""
    try:
        params = request.json
        target = params.get("target", "")
        additional_args = params.get("additional_args", "-A")
        
        if not target:
            logger.warning("Enum4linux-ng called without target parameter")
            return jsonify({
                "error": "Target parameter is required"
            }), 400
        
        command = f"enum4linux-ng {additional_args} {target}"
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in enum4linux-ng endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500


@app.route("/api/tools/ffuf", methods=["POST"])
def ffuf():
    """Execute FFUF with the provided parameters."""
    try:
        params = request.json
        url = params.get("url", "")
        wordlist = params.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        mode = params.get("mode", "dir")
        additional_args = params.get("additional_args", "")
        max_results = params.get("max_results", 100)  # Limit results by default
        
        if not url:
            logger.warning("FFUF called without URL parameter")
            return jsonify({
                "error": "URL parameter is required"
            }), 400
        
        # Ensure URL contains FUZZ keyword for directory fuzzing
        if mode == "dir" and "FUZZ" not in url:
            if url.endswith("/"):
                url += "FUZZ"
            else:
                url += "/FUZZ"
        
        # Build command with output formatting and filtering
        command = f"ffuf -u {url} -w {wordlist} -o /tmp/ffuf_output.json -of json"
        
        # Add common filters to reduce noise if not specified
        if "-fc" not in additional_args and "-mc" not in additional_args:
            command += " -fc 404"
        
        # Add rate limiting to prevent overwhelming the target
        if "-rate" not in additional_args:
            command += " -rate 100"
        
        if additional_args:
            command += f" {additional_args}"
        
        # Execute the command
        result = execute_command(command)
        
        # Try to parse and limit the JSON output
        try:
            if result.get("success") and os.path.exists("/tmp/ffuf_output.json"):
                with open("/tmp/ffuf_output.json", "r") as f:
                    ffuf_data = json.load(f)
                
                # Limit results to prevent overwhelming output
                if "results" in ffuf_data and len(ffuf_data["results"]) > max_results:
                    ffuf_data["results"] = ffuf_data["results"][:max_results]
                    ffuf_data["truncated"] = True
                    ffuf_data["total_found"] = len(ffuf_data["results"])
                
                result["parsed_output"] = ffuf_data
                
                # Clean up temp file
                os.remove("/tmp/ffuf_output.json")
        except Exception as parse_error:
            logger.warning(f"Could not parse FFUF JSON output: {str(parse_error)}")
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in ffuf endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/amass", methods=["POST"])
def amass():
    """Execute Amass with the provided parameters."""
    try:
        params = request.json
        domain = params.get("domain", "")
        mode = params.get("mode", "enum")
        additional_args = params.get("additional_args", "")
        
        if not domain:
            logger.warning("Amass called without domain parameter")
            return jsonify({
                "error": "Domain parameter is required"
            }), 400
        
        # Validate mode
        if mode not in ["enum", "intel", "viz", "track", "db"]:
            logger.warning(f"Invalid amass mode: {mode}")
            return jsonify({
                "error": f"Invalid mode: {mode}. Must be one of: enum, intel, viz, track, db"
            }), 400
        
        command = f"amass {mode} -d {domain}"
        
        if additional_args:
            command += f" {additional_args}"
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in amass endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/hashcat", methods=["POST"])
def hashcat():
    """Execute Hashcat with the provided parameters."""
    try:
        params = request.json
        hash_file = params.get("hash_file", "")
        wordlist = params.get("wordlist", "/usr/share/wordlists/rockyou.txt")
        hash_type = params.get("hash_type", "")
        attack_mode = params.get("attack_mode", 0)
        additional_args = params.get("additional_args", "")
        
        if not hash_file:
            logger.warning("Hashcat called without hash_file parameter")
            return jsonify({
                "error": "Hash file parameter is required"
            }), 400
        
        command = f"hashcat -a {attack_mode}"
        
        if hash_type:
            command += f" -m {hash_type}"
        
        command += f" {hash_file} {wordlist}"
        
        if additional_args:
            command += f" {additional_args}"
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in hashcat endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@app.route("/api/tools/openvas", methods=["POST"])
def openvas():
    """Execute OpenVAS scan with the provided parameters."""
    try:
        params = request.json
        target = params.get("target", "")
        scan_config = params.get("scan_config", "Full and fast")
        additional_args = params.get("additional_args", "")
        
        if not target:
            logger.warning("OpenVAS called without target parameter")
            return jsonify({
                "error": "Target parameter is required"
            }), 400
        
        # Note: This is a simplified OpenVAS command. In practice, OpenVAS requires
        # more complex setup with GVM (Greenbone Vulnerability Management)
        command = f"gvm-cli socket --xml \"<create_target><name>MCP Target</name><hosts>{target}</hosts></create_target>\""
        
        if additional_args:
            command += f" {additional_args}"
        
        result = execute_command(command)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in openvas endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500


# Health check endpoint
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    # Check if essential tools are installed
    essential_tools = ["nmap", "gobuster", "feroxbuster", "nikto", "sqlmap", "hydra", "john", "wpscan", "enum4linux-ng", "ffuf", "amass", "hashcat"]
    tools_status = {}
    
    for tool in essential_tools:
        try:
            result = execute_command(f"which {tool}")
            tools_status[tool] = result["success"]
        except:
            tools_status[tool] = False
    
    all_essential_tools_available = all(tools_status.values())
    
    return jsonify({
        "status": "healthy",
        "message": "Kali Linux Tools API Server is running",
        "tools_status": tools_status,
        "all_essential_tools_available": all_essential_tools_available,
        "notes": {
            "burp_suite": "Burp Suite Community Edition should be installed separately and run manually as it's a GUI application",
            "openvas": "OpenVAS requires additional setup with GVM (Greenbone Vulnerability Management)"
        }
    })

@app.route("/mcp/capabilities", methods=["GET"])
def get_capabilities():
    # Return tool capabilities similar to our existing MCP server
    pass

@app.route("/mcp/tools/kali_tools/<tool_name>", methods=["POST"])
def execute_tool(tool_name):
    # Direct tool execution without going through the API server
    pass

# Scan history endpoints
@app.route("/api/scans/history", methods=["GET"])
def scan_history():
    """Get recent scan history"""
    try:
        limit = int(request.args.get('limit', 20))
        
        # Get all log files
        if not os.path.exists(SCAN_LOG_DIR):
            return jsonify({"total": 0, "scans": []})
        
        log_files = sorted(
            [f for f in os.listdir(SCAN_LOG_DIR) if f.endswith('.json')],
            reverse=True
        )[:limit]
        
        scans = []
        for log_file in log_files:
            try:
                with open(f"{SCAN_LOG_DIR}/{log_file}", 'r') as f:
                    scans.append(json.load(f))
            except Exception as e:
                logger.error(f"Error reading log file {log_file}: {str(e)}")
        
        return jsonify({
            "total": len(scans),
            "scans": scans
        })
    except Exception as e:
        logger.error(f"Error getting scan history: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/scans/<scan_id>", methods=["GET"])
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

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run the Kali Linux API Server")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--port", type=int, default=API_PORT, help=f"Port for the API server (default: {API_PORT})")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="IP address to bind the server to (default: 127.0.0.1 for localhost only)")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    # Set configuration from command line arguments
    if args.debug:
        DEBUG_MODE = True
        os.environ["DEBUG_MODE"] = "1"
        logger.setLevel(logging.DEBUG)
    
    if args.port != API_PORT:
        API_PORT = args.port
    
    logger.info(f"Starting Kali Linux Tools API Server on {args.ip}:{API_PORT}")
    app.run(host=args.ip, port=API_PORT, debug=DEBUG_MODE)
