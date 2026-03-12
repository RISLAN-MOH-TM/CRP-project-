@echo off
REM Quick installer for CVE RAG System
REM This script launches the main setup in the cve_rag_system folder

echo ╔══════════════════════════════════════════════════════════════════════════════╗
echo ║                   CVE RAG SYSTEM - QUICK INSTALLER                           ║
echo ╚══════════════════════════════════════════════════════════════════════════════╝
echo.

REM Check if cve_rag_system folder exists
if not exist "cve_rag_system" (
    echo ❌ Error: cve_rag_system folder not found
    echo.
    echo Please ensure you're running this from the project root directory.
    pause
    exit /b 1
)

echo ✅ CVE RAG System folder found
echo.
echo Launching setup...
echo.

REM Change to cve_rag_system directory and run setup
cd cve_rag_system
call SETUP.bat

REM Return to original directory
cd ..

echo.
echo ═══════════════════════════════════════════════════════════════════════════════
echo Installation complete!
echo ═══════════════════════════════════════════════════════════════════════════════
pause
