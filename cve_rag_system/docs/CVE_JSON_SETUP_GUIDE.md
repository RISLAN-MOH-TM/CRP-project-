# CVE JSON RAG Integration Setup Guide

## 🎯 Your Data

**Location**: `C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves`  
**Format**: JSON files (CVE 5.0 format from NVD/CVEList)  
**Size**: ~2.5 GB  
**Years**: 1999-2026

## 📦 What You Have

Your CVE data is in JSON format, organized by year:

```
cves/
├── 1999/
│   ├── 0xxx/
│   │   ├── CVE-1999-0001.json
│   │   ├── CVE-1999-0002.json
│   │   └── ...
├── 2000/
├── 2001/
├── ...
├── 2023/
├── 2024/
├── 2025/
└── 2026/
```

Each JSON file contains rich CVE data:
- CVE ID
- Description
- CVSS scores
- Severity levels
- Affected products
- CWE classifications
- References
- Publication dates

## 🚀 Quick Start (3 Steps)

### Step 1: Install Dependencies (5 minutes)

```bash
pip install -r requirements_rag.txt
```

### Step 2: Build CVE Database (30-60 minutes, ONE TIME)

```bash
# Process all CVEs (recommended)
python json_cve_rag_integration.py --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" --rebuild

# Or process specific year (faster for testing)
python json_cve_rag_integration.py --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" --rebuild --year 2023

# Or process limited number (for testing)
python json_cve_rag_integration.py --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" --rebuild --max-files 1000
```

### Step 3: Start Enhanced MCP Server

```bash
python mcp_server_with_cve_rag.py --enable-cve-rag --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves"
```

## 🎯 New MCP Tools

### 1. search_cve_database
Search through CVE database using natural language

```python
# Basic search
search_cve_database("SQL injection")

# With severity filter
search_cve_database("remote code execution", severity="CRITICAL")

# More results
search_cve_database("Apache vulnerabilities", limit=20)
```

### 2. get_cve_details
Get detailed information about a specific CVE

```python
get_cve_details("CVE-2023-12345")
get_cve_details("CVE-2021-44228")  # Log4Shell
```

### 3. search_cves_by_year
Search CVEs from a specific year

```python
search_cves_by_year("SQL injection", "2023")
search_cves_by_year("buffer overflow", "2024", limit=20)
```

### 4. get_cve_statistics
Get database statistics

```python
get_cve_statistics()
```

### 5. enhanced_vulnerability_report_with_cve
Generate reports with CVE context

```python
enhanced_vulnerability_report_with_cve("192.168.1.100", include_cve_context=True)
```

## 📊 Processing Time Estimates

| CVEs | Files | Time | Database Size |
|------|-------|------|---------------|
| 1,000 | 1,000 | 2-3 min | 50 MB |
| 10,000 | 10,000 | 15-20 min | 500 MB |
| 50,000 | 50,000 | 60-90 min | 2.5 GB |
| 100,000+ | 100,000+ | 120-180 min | 5 GB |

## 🔧 Configuration Options

### Process Specific Year (Faster)

```bash
# Only 2023 CVEs
python json_cve_rag_integration.py --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" --rebuild --year 2023

# Only 2024 CVEs
python json_cve_rag_integration.py --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" --rebuild --year 2024
```

### Process Limited Files (Testing)

```bash
# First 1000 CVEs
python json_cve_rag_integration.py --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" --rebuild --max-files 1000

# First 5000 CVEs
python json_cve_rag_integration.py --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" --rebuild --max-files 5000
```

### Test Search

```bash
python json_cve_rag_integration.py --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" --test-query "SQL injection"
```

## 💡 Example Usage

### Search for Vulnerabilities

```python
# Find SQL injection CVEs
search_cve_database("SQL injection", limit=10)

# Find critical remote code execution
search_cve_database("remote code execution", severity="CRITICAL", limit=5)

# Find Apache vulnerabilities
search_cve_database("Apache HTTP Server")

# Find authentication bypass
search_cve_database("authentication bypass")
```

### Get Specific CVE

```python
# Log4Shell
get_cve_details("CVE-2021-44228")

# Heartbleed
get_cve_details("CVE-2014-0160")

# EternalBlue
get_cve_details("CVE-2017-0144")
```

### Year-Based Analysis

```python
# 2023 SQL injections
search_cves_by_year("SQL injection", "2023", limit=20)

# 2024 critical vulnerabilities
search_cves_by_year("critical", "2024", limit=50)
```

### Enhanced Reports

```python
# Scan target and get CVE context
nmap_scan("192.168.1.100")
enhanced_vulnerability_report_with_cve("192.168.1.100", include_cve_context=True)
```

## 🎓 Complete Workflow

```bash
# 1. Install dependencies (5 min)
pip install -r requirements_rag.txt

# 2. Build CVE database (30-60 min, ONE TIME)
python json_cve_rag_integration.py ^
    --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" ^
    --rebuild

# 3. Test search (1 min)
python json_cve_rag_integration.py ^
    --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" ^
    --test-query "SQL injection"

# 4. Start enhanced MCP server
python mcp_server_with_cve_rag.py ^
    --enable-cve-rag ^
    --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves"

# 5. Use in Claude!
```

## 📁 Files Created

After setup:

```
your_project/
├── chroma_cve_db/                    # Vector database (3-6 GB)
│   ├── chroma.sqlite3
│   └── ... (database files)
├── json_cve_rag_integration.py       # CVE RAG system
├── mcp_server_with_cve_rag.py        # Enhanced MCP server
└── requirements_rag.txt              # Dependencies
```

## 🐛 Troubleshooting

### "No CVE documents loaded"

Check the path:
```bash
dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves\2023"
```

### "Out of memory"

Process fewer CVEs:
```bash
python json_cve_rag_integration.py --cve-dir "..." --rebuild --max-files 5000
```

Or process by year:
```bash
python json_cve_rag_integration.py --cve-dir "..." --rebuild --year 2023
```

### "Slow processing"

This is normal for large datasets. Processing 100,000+ CVEs takes 2-3 hours.

## ✅ Verification

```bash
# Check database exists
dir chroma_cve_db\

# Test search
python json_cve_rag_integration.py --cve-dir "..." --test-query "test"

# Check statistics
python mcp_server_with_cve_rag.py --enable-cve-rag --cve-dir "..."
# Then in Claude: get_cve_statistics()
```

## 🎉 You're Ready!

Your CVE JSON database is now integrated with your penetration testing system!

**Next**: Use the new CVE tools in Claude to enhance your security reports with real CVE data.
