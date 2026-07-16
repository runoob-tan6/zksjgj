@echo off
cd /d "%~dp0"
python -m PyInstaller --clean --noconfirm borehole_v3.spec
pause
