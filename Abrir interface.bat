@echo off
rem Abre a interface local do Video Diario IA no navegador.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m videobot ui
pause
