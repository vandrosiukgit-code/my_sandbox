@echo off
setlocal

cd /d "%~dp0"
".\.venv\Scripts\python.exe" -m tools.activity_sandbox bot_turn %*

endlocal
