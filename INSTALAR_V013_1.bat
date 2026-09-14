@echo off
title NEXUS MARKET AGENT V0.13.1 - INSTALADOR
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -3.11 -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.
echo INSTALACION V0.13.1 TERMINADA CORRECTAMENTE
pause
