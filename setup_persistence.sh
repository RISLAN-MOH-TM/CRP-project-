#!/bin/bash

# Setup script for scan logging and persistence

echo "Setting up scan logging and persistence..."

# Create scan logs directory on Kali VM
echo "Creating scan logs directory..."
sudo mkdir -p /opt/scans/logs
sudo chmod 777 /opt/scans/logs

echo "✅ Scan logs directory created: /opt/scans/logs"

# Create results directory on Windows (will be created automatically by Python)
echo "✅ Results directory will be created automatically at: ./results"

echo ""
echo "Setup complete! Features enabled:"
echo "  ✅ Automatic scan logging to /opt/scans/logs/"
echo "  ✅ Automatic result saving to ./results/"
echo "  ✅ Scan history API endpoints"
echo "  ✅ Recovery tools (get_scan_history, get_scan_details)"
echo ""
echo "Restart your servers to apply changes:"
echo "  1. On Kali VM: python3 kali_server.py --ip 0.0.0.0 --port 5000"
echo "  2. On Windows: Restart Claude Desktop"
echo ""
echo "Test with Claude:"
echo '  "Show me the recent scan history"'
echo '  "Get details for scan ID: nmap_20240220_143022_..."'
