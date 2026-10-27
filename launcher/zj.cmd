@echo off
rem zellij-config launcher; keep the installed .zellij-config helper alongside it.
setlocal DisableDelayedExpansion
set "zj_helper=%~dp0.zellij-config\manage.py"
if not exist "%zj_helper%" set "zj_helper=%~dp0..\tools\manage.py"
if not exist "%zj_helper%" goto missing_helper
if defined ZJ_PYTHON goto override
where py >nul 2>&1
if errorlevel 1 goto python
py -3 "%zj_helper%" launch -- %*
exit /b %errorlevel%
:override
if exist "%ZJ_PYTHON%" goto run_override
where "%ZJ_PYTHON%" >nul 2>&1
if errorlevel 1 goto missing_override
:run_override
"%ZJ_PYTHON%" "%zj_helper%" launch -- %*
exit /b %errorlevel%
:python
where python >nul 2>&1
if errorlevel 1 goto missing_python
python "%zj_helper%" launch -- %*
exit /b %errorlevel%
:missing_helper
echo zj helper is missing. Keep the launcher beside its installed .zellij-config helpers or inside the checkout's launcher directory. >&2
exit /b 1
:missing_python
echo Python 3.10+ is required for zj. Set ZJ_PYTHON to its executable path if it is installed under another name. >&2
exit /b 1
:missing_override
echo ZJ_PYTHON executable is unavailable. Set one Python 3.10+ executable path without arguments. >&2
exit /b 1
