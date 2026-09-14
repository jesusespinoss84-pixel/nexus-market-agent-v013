@echo off
title NEXUS MARKET AGENT V0.13.1 - LIVE PAPER
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo ERROR: Ejecuta primero INSTALAR_V013_1.bat
 pause
 exit /b 1
)
".venv\Scripts\python.exe" app.py
pause
