@echo off
cd /d "%~dp0"
python -m PyInstaller --clean --noconfirm borehole_v4.spec
pause
