@echo off
rem zellij-config launcher; keep the installed .zellij-config helper alongside it.
setlocal
set "zj_helper=%~dp0.zellij-config\manage.py"
if not exist "%zj_helper%" set "zj_helper=%~dp0..\tools\manage.py"
where py >nul 2>&1
if errorlevel 1 goto python
py -3 "%zj_helper%" launch -- %*
exit /b %errorlevel%
:python
python "%zj_helper%" launch -- %*
exit /b %errorlevel%
