@echo off
rem zellij-config launcher - zj.cmd: start zellij, checking the pinned plugins
rem for updates about once a month (Windows; launcher\zj is the Linux/macOS one).
rem
rem   zj [zellij arguments...]      e.g. zj, zj attach --create main
rem   zj --check-updates [FILE]     only report (see zj.ps1)
rem
rem Keep zj.cmd and zj.ps1 together, e.g. in the folder that holds zellij.exe,
rem which is already on PATH. The date test below runs on every start and is
rem quick; PowerShell (about half a second) starts only when a check is due:
rem 30 days after the last check that reached GitHub, a day after one that
rem didn't. Set ZJ_NO_UPDATE_CHECK=1 to skip it. Delete
rem %LOCALAPPDATA%\zellij-config\plugin-update-check to check on the next start.
rem This file needs CRLF line endings (see .gitattributes).
setlocal
set "zj_state=%LOCALAPPDATA%\zellij-config"
if /i "%~1"=="--check-updates" goto report
if defined ZJ_NO_UPDATE_CHECK goto run
if not exist "%zj_state%\plugin-update-check" goto check
forfiles /P "%zj_state%" /M plugin-update-check /D -30 >nul 2>&1 && goto check
goto run

:check
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0zj.ps1" -Startup

:run
endlocal & zellij %*
exit /b

:report
if "%~2"=="" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0zj.ps1" -CheckUpdates
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0zj.ps1" -CheckUpdates -Config "%~2"
)
exit /b %errorlevel%
