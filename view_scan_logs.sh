#!/bin/bash

# Script to view scan logs on Kali VM

LOGS_DIR="/opt/scans/logs"

echo "==================================="
echo "  Scan Logs Viewer"
echo "==================================="
echo ""

# Check if logs directory exists
if [ ! -d "$LOGS_DIR" ]; then
    echo "❌ Logs directory not found: $LOGS_DIR"
    echo "Run: sudo mkdir -p $LOGS_DIR && sudo chmod 777 $LOGS_DIR"
    exit 1
fi

# Count total logs
TOTAL=$(ls -1 $LOGS_DIR/*.json 2>/dev/null | wc -l)
echo "📊 Total scans logged: $TOTAL"
echo ""

if [ $TOTAL -eq 0 ]; then
    echo "No scan logs found yet."
    exit 0
fi

# Show options
echo "What would you like to do?"
echo "1) List all scans"
echo "2) View most recent scan"
echo "3) View specific scan by ID"
echo "4) Search scans by tool"
echo "5) View all scans from today"
echo ""
read -p "Enter choice (1-5): " choice

case $choice in
    1)
        echo ""
        echo "All Scans (newest first):"
        echo "-----------------------------------"
        ls -lht $LOGS_DIR/*.json | head -20
        ;;
    2)
        echo ""
        echo "Most Recent Scan:"
        echo "-----------------------------------"
        LATEST=$(ls -t $LOGS_DIR/*.json | head -1)
        cat "$LATEST" | python3 -m json.tool
        ;;
    3)
        echo ""
        read -p "Enter scan ID: " scan_id
        if [ -f "$LOGS_DIR/${scan_id}.json" ]; then
            cat "$LOGS_DIR/${scan_id}.json" | python3 -m json.tool
        else
            echo "❌ Scan not found: $scan_id"
        fi
        ;;
    4)
        echo ""
        read -p "Enter tool name (nmap, gobuster, etc.): " tool
        echo "Scans using $tool:"
        echo "-----------------------------------"
        ls -lht $LOGS_DIR/${tool}_*.json 2>/dev/null
        ;;
    5)
        echo ""
        TODAY=$(date +%Y%m%d)
        echo "Scans from today ($TODAY):"
        echo "-----------------------------------"
        ls -lht $LOGS_DIR/*_${TODAY}_*.json 2>/dev/null
        ;;
    *)
        echo "Invalid choice"
        ;;
esac

echo ""
echo "Log files location: $LOGS_DIR"
