@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv 2>nul || python -m venv .venv
)

call ".venv\Scripts\pip.exe" install -q -r requirements.txt
if not exist "assets\spvt-admin.ico" call ".venv\Scripts\python.exe" make_icon.py
call ".venv\Scripts\python.exe" -m spvt_admin

endlocal
