@echo off
REM Quick Setup Script for CVE JSON RAG Integration

echo ==========================================
echo CVE JSON RAG Integration Setup
echo ==========================================
echo.

REM Your CVE directory
set CVE_DIR=C:\Users\User\User\Desktop\mcp\cves

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo X Python not found. Please install Python 3.8+
    exit /b 1
)

echo [OK] Python found
python --version
echo.

REM Step 1: Install dependencies
echo [Step 1] Installing RAG dependencies...
echo This may take 5-10 minutes...
pip install -r requirements_rag.txt

if errorlevel 1 (
    echo X Failed to install dependencies
    exit /b 1
)

echo [OK] Dependencies installed
echo.

REM Step 2: Check CVE directory
echo [Step 2] Checking CVE directory...
if not exist "%CVE_DIR%" (
    echo X CVE directory not found: %CVE_DIR%
    echo.
    echo Please update the CVE_DIR variable in this script to point to your CVE directory.
    echo Current path: %CVE_DIR%
    echo.
    pause
    exit /b 1
)

echo [OK] CVE directory found: %CVE_DIR%
echo.

REM Count JSON files
echo Counting CVE JSON files...
for /f %%A in ('dir /s /b "%CVE_DIR%\*.json" 2^>nul ^| find /c /v ""') do set JSON_COUNT=%%A
echo Found %JSON_COUNT% CVE JSON files
echo.

REM Step 3: Build vector database
echo [Step 3] Building CVE vector database...
echo.
echo IMPORTANT: This will take 30-180 minutes depending on the number of CVEs.
echo.
echo Options:
echo   1. Process ALL CVEs (recommended, ~2-3 hours)
echo   2. Process specific year (faster, ~10-30 min)
echo   3. Process limited files for testing (fastest, ~5-10 min)
echo   4. Skip database build
echo.

set /p BUILD_OPTION="Choose option (1-4): "

if "%BUILD_OPTION%"=="1" (
    echo.
    echo Building database with ALL CVEs...
    echo This will take 2-3 hours. Please be patient.
    echo.
    python json_cve_rag_integration.py --cve-dir "%CVE_DIR%" --rebuild
    
) else if "%BUILD_OPTION%"=="2" (
    echo.
    set /p YEAR="Enter year (e.g., 2023, 2024): "
    echo.
    echo Building database with CVEs from year %YEAR%...
    python json_cve_rag_integration.py --cve-dir "%CVE_DIR%" --rebuild --year %YEAR%
    
) else if "%BUILD_OPTION%"=="3" (
    echo.
    set /p MAX_FILES="Enter max files (e.g., 1000, 5000): "
    echo.
    echo Building database with first %MAX_FILES% CVEs...
    python json_cve_rag_integration.py --cve-dir "%CVE_DIR%" --rebuild --max-files %MAX_FILES%
    
) else (
    echo.
    echo Skipped database build.
    echo You can build it later with:
    echo   python json_cve_rag_integration.py --cve-dir "%CVE_DIR%" --rebuild
    echo.
    goto :end
)

if errorlevel 1 (
    echo X Failed to build vector database
    exit /b 1
)

echo.
echo [OK] Vector database built successfully!
echo.

REM Step 4: Test search
echo [Step 4] Testing search functionality...
python json_cve_rag_integration.py --cve-dir "%CVE_DIR%" --test-query "SQL injection"

echo.
echo ==========================================
echo [OK] Setup Complete!
echo ==========================================
echo.
echo Next steps:
echo 1. Start the enhanced MCP server:
echo    python mcp_server_with_cve_rag.py --enable-cve-rag --cve-dir "%CVE_DIR%"
echo.
echo 2. Use CVE RAG tools in Claude:
echo    - search_cve_database("SQL injection")
echo    - get_cve_details("CVE-2023-12345")
echo    - search_cves_by_year("remote code execution", "2023")
echo    - enhanced_vulnerability_report_with_cve("192.168.1.100")
echo.

:end
echo ==========================================
echo Setup script completed
echo ==========================================
pause
