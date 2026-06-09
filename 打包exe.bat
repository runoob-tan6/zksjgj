@echo off
setlocal EnableExtensions

set "PROJECT_DIR=%~dp0"
set "SPEC_FILE="
set "PY_CMD="

echo Building EXE...
echo Project dir: %PROJECT_DIR%

for %%F in ("%PROJECT_DIR%*.spec") do (
    set "SPEC_FILE=%%~fF"
    goto :spec_found
)

echo.
echo ERROR: No .spec file found in project directory.
pause
exit /b 1

:spec_found
if exist "H:\Program Files\Python314\python.exe" (
    set "PY_CMD=H:\Program Files\Python314\python.exe"
    goto :python_found
)

if exist "%SystemRoot%\py.exe" (
    set "PY_CMD=%SystemRoot%\py.exe -3"
    goto :python_found
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PY_CMD=python"
    goto :python_found
)

echo.
echo ERROR: Python not found.
echo Install Python or edit this script to set a valid Python command.
pause
exit /b 1

:python_found
echo Using spec: %SPEC_FILE%
echo Using python: %PY_CMD%

call "%PY_CMD%" -m PyInstaller --clean --noconfirm "%SPEC_FILE%"
if errorlevel 1 (
    echo.
    echo ERROR: Build failed.
    pause
    exit /b 1
)

for %%F in ("%PROJECT_DIR%dist\*.exe") do (
    echo.
    echo Build complete: %%~fF
    pause
    exit /b 0
)

echo.
echo Build command finished, but no EXE was found in dist.
pause
exit /b 1
