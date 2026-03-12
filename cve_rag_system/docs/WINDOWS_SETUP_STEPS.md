# Windows Setup Steps for CVE RAG Integration

## 🖥️ What Runs on Windows

- **MCP Server** (connects Claude to Kali VM)
- **CVE RAG System** (processes and searches your CVE JSON data)
- **Vector Database** (ChromaDB - stores embeddings locally)

## 📋 Step-by-Step Setup

### Step 1: Install Python Dependencies (5 minutes)

From the `cve_rag_system` directory:

```bash
pip install -r requirements_rag.txt
```

**What gets installed:**
- `langchain` - RAG framework
- `chromadb` - Vector database (local)
- `sentence-transformers` - Embedding model

### Step 2: Verify Your CVE Data (2 minutes)

Your CVE JSON files should be at:
```
C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves
```

Verify:
```bash
dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves\2023"
```

### Step 3: Build Vector Database (30-180 minutes, ONE TIME ONLY)

**Option A: Automated (Recommended)**
```bash
cd cve_rag_system
SETUP.bat
```

**Option B: Manual**
```bash
cd cve_rag_system

# All CVEs (2-3 hours)
python core\json_cve_rag_integration.py --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" --rebuild

# Specific year (15-30 min)
python core\json_cve_rag_integration.py --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" --rebuild --year 2023

# Limited files (5-10 min)
python core\json_cve_rag_integration.py --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" --rebuild --max-files 5000
```

### Step 4: Test the RAG System (1 minute)

```bash
python core\json_cve_rag_integration.py --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves" --test-query "SQL injection"
```

### Step 5: Start Enhanced MCP Server

```bash
python core\mcp_server_with_cve_rag.py --enable-cve-rag --cve-dir "C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves"
```

## 🎯 What You Can Now Do in Claude

### 1. Search CVE Database
```python
search_cve_database("SQL injection", limit=10)
search_cve_database("remote code execution", severity="CRITICAL")
```

### 2. Get Specific CVE
```python
get_cve_details("CVE-2021-44228")  # Log4Shell
```

### 3. Search by Year
```python
search_cves_by_year("buffer overflow", "2023")
```

### 4. Get Statistics
```python
get_cve_statistics()
```

### 5. Enhanced Reports
```python
enhanced_vulnerability_report_with_cve("192.168.1.100")
```

## 📁 Files Created on Windows

After setup:

```
cve_rag_system/
├── chroma_cve_db/               # Vector database (3-6 GB)
├── core/                        # Python modules
├── docs/                        # Documentation
└── requirements_rag.txt         # Dependencies
```

## 🔧 Troubleshooting

### "Module not found"
```bash
pip install -r requirements_rag.txt
```

### "Out of memory"
Process fewer CVEs:
```bash
python core\json_cve_rag_integration.py --cve-dir "..." --rebuild --max-files 5000
```

### "CVE directory not found"
Update the path in SETUP.bat or provide correct path

### "Vector database not found"
Rebuild:
```bash
python core\json_cve_rag_integration.py --cve-dir "..." --rebuild
```

## 💡 Tips

1. **First time setup takes 30-180 minutes** - Normal for large datasets
2. **Database is persistent** - Build once, use forever
3. **Search is fast** - After setup, searches take 50-200 ms
4. **Original server still works** - You can switch between servers
5. **No internet required** - Everything runs locally

## ✅ Checklist

- [ ] Install dependencies
- [ ] Verify CVE directory
- [ ] Build vector database
- [ ] Test search
- [ ] Start enhanced MCP server
- [ ] Use new CVE tools in Claude

**Your Windows machine is ready!** 🎉
