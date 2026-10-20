@echo off
cd /d "%~dp0"
python -m PyInstaller --clean --noconfirm borehole_v2.spec
pause
