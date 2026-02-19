================================================================================
  KALI MCP SERVER - RESEARCH PROJECT
  Read This First!
================================================================================

YOUR SETUP:
-----------
[Kali Linux VM] <---> [Windows Host + VS Code] <---> [Claude AI]

FILES YOU NEED:
---------------
✓ kali_server.py     - Runs on Kali VM
✓ mcp_server.py      - Runs on Windows
✓ .env               - YOUR CONFIG (you must create this!)

QUICK START:
------------

STEP 1: On Kali Linux VM
-------------------------
python3 kali_server.py --ip 0.0.0.0 --port 5000

(Keep this running!)


STEP 2: Get Kali VM IP
-----------------------
ip addr show

(Note the IP, example: 192.168.1.100)


STEP 3: On Windows - Create .env File
--------------------------------------
Location: C:\Users\User\User\Desktop\mcp\.env

Content:
--------
KALI_API_KEY=kali-research-project-2024
KALI_SERVER_IP=192.168.1.100

(Replace 192.168.1.100 with YOUR Kali IP!)


STEP 4: Configure Claude
-------------------------
See HOWTO.md for Claude configuration


STEP 5: Test
------------
Ask Claude: "Check the Kali server health"


DOCUMENTATION:
--------------
1. HOWTO.md              - Simple step-by-step guide (START HERE!)
2. PROJECT_SETUP.md      - Complete setup for your architecture
3. TROUBLESHOOTING.md    - Common problems & solutions
4. README.md             - Project overview

IMPORTANT NOTES:
----------------
• Default API key: kali-research-project-2024 (no need to generate)
• .env file must be in project ROOT folder
• NOT inside mcp\mcp\ folder (that's virtual environment)
• Kali server must use --ip 0.0.0.0 (not 127.0.0.1)
• Use your Kali VM IP in .env, not localhost

COMMON MISTAKES:
----------------
✗ .env in wrong location (mcp\mcp\.env)
✗ .env named as .env.txt
✗ Using localhost instead of Kali VM IP
✗ Kali server running with 127.0.0.1 instead of 0.0.0.0

NEED HELP?
----------
Check TROUBLESHOOTING.md for solutions to common issues

================================================================================
Ready? Open HOWTO.md and follow the steps!
================================================================================
