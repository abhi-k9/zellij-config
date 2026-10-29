# Staged, verified installer for Windows PowerShell 5.1+; Python 3.10+ required.
# This wrapper maps named switches to the shared CLI; it changes no execution policy.
# If scripts are blocked, run python tools/manage.py install from the checkout.
param(
    [switch]$Offline, [switch]$Restore, [switch]$DryRun, [switch]$NoLauncher,
    [switch]$LauncherOnly,
    [string]$ConfigDir, [string]$BinDir
)
$ErrorActionPreference = 'Stop'
$helper = Join-Path $PSScriptRoot 'tools\manage.py'
if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) { throw "Setup helper is missing: $helper. Keep setup.ps1 in the complete checkout." }
$forward = @('install')
if ($Offline) { $forward += '--offline' }
if ($Restore) { $forward += '--restore' }
if ($DryRun) { $forward += '--dry-run' }
if ($NoLauncher) { $forward += '--no-launcher' }
if ($LauncherOnly) { $forward += '--launcher-only' }
if ($ConfigDir) { $forward += @('--config-dir', $ConfigDir) }
if ($BinDir) { $forward += @('--bin-dir', $BinDir) }
if ($env:ZJ_PYTHON) {
    if (-not (Test-Path -LiteralPath $env:ZJ_PYTHON -PathType Leaf) -and -not (Get-Command -Name ([System.Management.Automation.WildcardPattern]::Escape($env:ZJ_PYTHON)) -CommandType Application -ErrorAction SilentlyContinue)) { throw "ZJ_PYTHON executable is unavailable: $env:ZJ_PYTHON. Set one Python 3.10+ executable path without arguments." }
    & $env:ZJ_PYTHON $helper @forward
}
elseif (Get-Command py -CommandType Application -ErrorAction SilentlyContinue) { & py -3 $helper @forward }
elseif (Get-Command python -CommandType Application -ErrorAction SilentlyContinue) { & python $helper @forward }
else { throw 'Python 3.10+ is required. Set ZJ_PYTHON to its executable path if it is installed under another name.' }
exit $LASTEXITCODE
