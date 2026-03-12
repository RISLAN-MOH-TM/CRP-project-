@echo off
REM Master Setup Script for CVE RAG System
REM This script sets up the complete CVE RAG integration

echo ╔══════════════════════════════════════════════════════════════════════════════╗
echo ║                   CVE RAG SYSTEM - MASTER SETUP                              ║
echo ╚══════════════════════════════════════════════════════════════════════════════╝
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

echo ✅ Python found
python --version
echo.

REM Step 1: Install dependencies
echo ═══════════════════════════════════════════════════════════════════════════════
echo Step 1: Installing Dependencies
echo ═══════════════════════════════════════════════════════════════════════════════
echo.
echo Installing: langchain, chromadb, sentence-transformers
echo This may take 5-10 minutes...
echo.

pip install -r requirements_rag.txt

if errorlevel 1 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ✅ Dependencies installed successfully
echo.

REM Step 2: Verify CVE directory
echo ═══════════════════════════════════════════════════════════════════════════════
echo Step 2: Verifying CVE Directory
echo ═══════════════════════════════════════════════════════════════════════════════
echo.

set CVE_DIR=C:\Users\User\User\Desktop\mcp\cves

if not exist "%CVE_DIR%" (
    echo ⚠️  Default CVE directory not found: %CVE_DIR%
    echo.
    set /p CVE_DIR="Enter your CVE directory path: "
    
    if not exist "%CVE_DIR%" (
        echo ❌ CVE directory not found: %CVE_DIR%
        pause
        exit /b 1
    )
)

echo ✅ CVE directory found: %CVE_DIR%
echo.

REM Count JSON files
echo Counting CVE JSON files...
for /f %%A in ('dir /s /b "%CVE_DIR%\*.json" 2^>nul ^| find /c /v ""') do set JSON_COUNT=%%A
echo ✅ Found %JSON_COUNT% CVE JSON files
echo.

REM Step 3: Build CVE database
echo ═══════════════════════════════════════════════════════════════════════════════
echo Step 3: Building CVE Vector Database
echo ═══════════════════════════════════════════════════════════════════════════════
echo.
echo This is the most time-consuming step. Choose your option:
echo.
echo   1. Process ALL CVEs (recommended for production)
echo      - CVEs: 100,000+
echo      - Time: 2-3 hours
echo      - Best for: Complete database
echo.
echo   2. Process specific year (faster)
echo      - CVEs: ~10,000 per year
echo      - Time: 15-30 minutes
echo      - Best for: Recent vulnerabilities
echo.
echo   3. Process limited files (testing)
echo      - CVEs: Your choice (e.g., 5000)
echo      - Time: 5-10 minutes
echo      - Best for: Testing setup
echo.
echo   4. Skip database build (build later)
echo.

set /p BUILD_OPTION="Choose option (1-4): "

if "%BUILD_OPTION%"=="1" (
    echo.
    echo ═══════════════════════════════════════════════════════════════════════════════
    echo Building database with ALL CVEs...
    echo This will take 2-3 hours. You can leave this running.
    echo ═══════════════════════════════════════════════════════════════════════════════
    echo.
    
    python core\json_cve_rag_integration.py --cve-dir "%CVE_DIR%" --rebuild
    
) else if "%BUILD_OPTION%"=="2" (
    set YEAR=
    echo.
    set /p YEAR="Enter year (e.g., 2023, 2024, 2025): "
    if not defined YEAR set YEAR=2024
    echo.
    echo ═══════════════════════════════════════════════════════════════════════════════
    echo Building database with CVEs from year %YEAR%...
    echo ═══════════════════════════════════════════════════════════════════════════════
    echo.
    
    python core\json_cve_rag_integration.py --cve-dir "%CVE_DIR%" --rebuild --year %YEAR%
    
) else if "%BUILD_OPTION%"=="3" (
    set MAX_FILES=
    echo.
    set /p MAX_FILES="Enter max files (e.g., 1000, 5000, 10000): "
    if not defined MAX_FILES set MAX_FILES=1000
    echo.
    echo ═══════════════════════════════════════════════════════════════════════════════
    echo Building database with first %MAX_FILES% CVEs...
    echo ═══════════════════════════════════════════════════════════════════════════════
    echo.
    
    python core\json_cve_rag_integration.py --cve-dir "%CVE_DIR%" --rebuild --max-files %MAX_FILES%
    
) else (
    echo.
    echo ⚠️  Skipped database build.
    echo.
    echo You can build it later with:
    echo   cd cve_rag_system
    echo   python core\json_cve_rag_integration.py --cve-dir "%CVE_DIR%" --rebuild
    echo.
    goto :skip_test
)

if errorlevel 1 (
    echo ❌ Failed to build vector database
    pause
    exit /b 1
)

echo.
echo ✅ Vector database built successfully!
echo.

REM Step 4: Test search
echo ═══════════════════════════════════════════════════════════════════════════════
echo Step 4: Testing Search Functionality
echo ═══════════════════════════════════════════════════════════════════════════════
echo.

python core\json_cve_rag_integration.py --cve-dir "%CVE_DIR%" --test-query "SQL injection"

:skip_test

echo.
echo ═══════════════════════════════════════════════════════════════════════════════
echo ✅ SETUP COMPLETE!
echo ═══════════════════════════════════════════════════════════════════════════════
echo.
echo 📁 Files created:
echo    - chroma_cve_db\          (Vector database)
echo    - core\                   (Python modules)
echo    - docs\                   (Documentation)
echo.
echo 🚀 Next steps:
echo.
echo 1. Start the enhanced MCP server:
echo    cd cve_rag_system
echo    python core\mcp_server_with_cve_rag.py --enable-cve-rag --cve-dir "%CVE_DIR%"
echo.
echo 2. Use CVE RAG tools in Claude:
echo    - search_cve_database("SQL injection")
echo    - get_cve_details("CVE-2023-12345")
echo    - search_cves_by_year("remote code execution", "2023")
echo    - get_cve_statistics()
echo    - enhanced_vulnerability_report_with_cve("192.168.1.100")
echo.
echo 📚 Documentation:
echo    - START_HERE.txt          (Quick overview)
echo    - README_CVE_RAG.md       (Main README)
echo    - docs\                   (Detailed guides)
echo.
echo ═══════════════════════════════════════════════════════════════════════════════
pause
