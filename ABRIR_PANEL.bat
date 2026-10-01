@echo off
REM Abre el panel de control de la E-Book Factory en el navegador.
cd /d "%~dp0"
git config core.longpaths true >nul 2>&1
python factory.py panel
pause
