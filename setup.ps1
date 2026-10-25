# Staged, verified installer for Windows PowerShell 5.1+; Python 3.10+ required.
param(
    [switch]$Offline, [switch]$Restore, [switch]$DryRun, [switch]$NoLauncher,
    [switch]$LauncherOnly,
    [string]$ConfigDir, [string]$BinDir
)
$ErrorActionPreference = 'Stop'
$helper = Join-Path $PSScriptRoot 'tools\manage.py'
$forward = @('install')
if ($Offline) { $forward += '--offline' }
if ($Restore) { $forward += '--restore' }
if ($DryRun) { $forward += '--dry-run' }
if ($NoLauncher) { $forward += '--no-launcher' }
if ($LauncherOnly) { $forward += '--launcher-only' }
if ($ConfigDir) { $forward += @('--config-dir', $ConfigDir) }
if ($BinDir) { $forward += @('--bin-dir', $BinDir) }
if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 $helper @forward }
else { & python $helper @forward }
exit $LASTEXITCODE
