@echo off
title NEXUS V0.13.1 - VALIDAR EMPRESA
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo ERROR: Ejecuta primero INSTALAR_V013_1.bat
 pause
 exit /b 1
)
set /p SYMBOL=Ticker a validar:
".venv\Scripts\python.exe" validate_symbol.py %SYMBOL% full
pause
