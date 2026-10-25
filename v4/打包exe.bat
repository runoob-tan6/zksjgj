@echo off
setlocal DisableDelayedExpansion
set "PS7=%ProgramFiles%\PowerShell\7\pwsh.exe"
if not exist "%PS7%" set "PS7=%LOCALAPPDATA%\Programs\PowerShell\7\pwsh.exe"
if exist "%PS7%" goto run
where pwsh.exe >nul 2>nul
if errorlevel 1 goto missing_powershell
set "PS7=pwsh.exe"

:run
"%PS7%" -NoProfile -ExecutionPolicy Bypass -File "%~dpn0.ps1" %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" goto failed
echo.
echo [OK] Build completed.
goto finish

:missing_powershell
set "RESULT=1"
echo [ERROR] PowerShell 7 was not found. Install it or add pwsh.exe to PATH.
goto finish

:failed
echo.
echo [ERROR] Build failed. See the PowerShell message above.

:finish
pause
endlocal & exit /b %RESULT%
