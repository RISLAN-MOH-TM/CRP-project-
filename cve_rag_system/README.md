# CVE RAG System

Complete CVE JSON RAG integration for your penetration testing system.

## 📁 Folder Structure

```
cve_rag_system/
├── SETUP.bat                    # Master setup script (START HERE!)
├── START_HERE.txt               # Quick overview
├── README_CVE_RAG.md            # Detailed README
├── requirements_rag.txt         # Python dependencies
│
├── core/                        # Core system files
│   ├── json_cve_rag_integration.py    # CVE RAG system
│   └── mcp_server_with_cve_rag.py     # Enhanced MCP server
│
├── docs/                        # Documentation
│   ├── CVE_JSON_QUICK_START.txt       # Quick reference
│   ├── CVE_JSON_SETUP_GUIDE.md        # Setup guide
│   ├── WINDOWS_SETUP_STEPS.md         # Windows details
│   ├── KALI_SETUP_STEPS.md            # Kali VM info
│   └── CHANGES_SUMMARY.md             # What changes
│
├── setup/                       # Additional setup scripts
│   └── setup_cve_rag.bat              # Alternative setup
│
└── chroma_cve_db/              # Vector database (created after setup)
```

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)

```bash
cd cve_rag_system
SETUP.bat
```

The script will:
1. ✅ Install dependencies
2. ✅ Verify CVE directory
3. ✅ Build vector database
4. ✅ Test search
5. ✅ Show next steps

### Option 2: Manual Setup

```bash
cd cve_rag_system

# 1. Install dependencies
pip install -r requirements_rag.txt

# 2. Build database
python core\json_cve_rag_integration.py --cve-dir "C:\path\to\cves" --rebuild

# 3. Test
python core\json_cve_rag_integration.py --cve-dir "C:\path\to\cves" --test-query "test"

# 4. Start server
python core\mcp_server_with_cve_rag.py --enable-cve-rag --cve-dir "C:\path\to\cves"
```

## 📊 Your CVE Data

- **Location**: `C:\Users\User\User\Downloads\cvelistV5-main\cvelistV5-main\cves`
- **Format**: JSON files (CVE 5.0)
- **Size**: ~2.5 GB
- **Years**: 1999-2026
- **Files**: 100,000+ CVEs

## 🎯 What You Get

### 5 New MCP Tools

1. **search_cve_database()** - Search CVEs using natural language
2. **get_cve_details()** - Get detailed CVE information
3. **search_cves_by_year()** - Filter CVEs by year
4. **get_cve_statistics()** - Database statistics
5. **enhanced_vulnerability_report_with_cve()** - Reports with CVE context

### Example Usage

```python
# Search for vulnerabilities
search_cve_database("SQL injection", limit=10)

# Get specific CVE
get_cve_details("CVE-2021-44228")  # Log4Shell

# Search by year
search_cves_by_year("buffer overflow", "2023")

# Enhanced reports
enhanced_vulnerability_report_with_cve("192.168.1.100")
```

## 📚 Documentation

**Start Here:**
- `START_HERE.txt` - Quick overview
- `README_CVE_RAG.md` - Main README

**Detailed Guides:**
- `docs/CVE_JSON_QUICK_START.txt` - Quick reference
- `docs/CVE_JSON_SETUP_GUIDE.md` - Setup guide
- `docs/WINDOWS_SETUP_STEPS.md` - Windows setup
- `docs/KALI_SETUP_STEPS.md` - Kali VM (no changes)
- `docs/CHANGES_SUMMARY.md` - What changes where

## 🖥️ What Changes

### Windows
- ✅ Install RAG dependencies
- ✅ Build CVE vector database (30 min - 3 hours, one-time)
- ✅ Use enhanced MCP server

### Kali VM
- ❌ **NO CHANGES!** Everything stays the same

## ⏱️ Processing Time

| Option | CVEs | Time | Best For |
|--------|------|------|----------|
| All CVEs | 100,000+ | 2-3 hours | Production |
| Year 2023 | ~10,000 | 15-30 min | Recent CVEs |
| 5000 files | 5,000 | 5-10 min | Testing |

## 🐛 Troubleshooting

**"CVE directory not found"**
- Update path in SETUP.bat
- Or provide path when prompted

**"Out of memory"**
- Process fewer CVEs: `--max-files 5000`
- Or by year: `--year 2023`

**"Slow processing"**
- Normal for large datasets
- 100,000+ CVEs takes 2-3 hours

## ✅ Verification

```bash
# Check database exists
dir chroma_cve_db\

# Test search
python core\json_cve_rag_integration.py --cve-dir "..." --test-query "test"

# Start server
python core\mcp_server_with_cve_rag.py --enable-cve-rag --cve-dir "..."
```

## 🎉 Result

After setup:
- ✅ All 18 original Kali tools (unchanged)
- ✅ 5 new CVE RAG tools
- ✅ Search 100,000+ CVEs in milliseconds
- ✅ Enhanced reports with CVE context

## 🚀 Next Steps

1. Run `SETUP.bat`
2. Start enhanced MCP server
3. Use CVE tools in Claude!

---

**Your CVE database is ready to integrate!** 🎉
