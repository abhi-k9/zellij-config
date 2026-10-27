# zellij-config launcher (Windows PowerShell 5.1+); all policy lives in Python.
# No parameter block: Zellij's own named flags remain literal elements of $args.
$ErrorActionPreference = 'Stop'
$helper = Join-Path $PSScriptRoot '.zellij-config\manage.py'
if (-not (Test-Path -LiteralPath $helper)) { $helper = Join-Path $PSScriptRoot '..\tools\manage.py' }
if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) { throw "zj helper is missing: $helper. Keep the launcher beside its installed .zellij-config helpers or inside the checkout's launcher directory." }
$forward = @($args)
if ($args.Count -gt 0 -and $args[0] -eq '-CheckUpdates') {
    $forward = @('--check-updates')
    if ($args.Count -eq 3 -and $args[1] -eq '-Config') { $forward += $args[2] }
    elseif ($args.Count -eq 2) { $forward += $args[1] }
    elseif ($args.Count -gt 1) { throw 'Usage: zj.ps1 -CheckUpdates [-Config FILE]' }
}
# PS5.1 native argument passing drops empty strings and can alter quotes. One
# JSON/base64 transport argument preserves every received value without files
# or stdin redirection; the actual Zellij child inherits the terminal normally.
$json = ConvertTo-Json -InputObject $forward -Compress
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))
if ($env:ZJ_PYTHON) {
    if (-not (Test-Path -LiteralPath $env:ZJ_PYTHON -PathType Leaf) -and -not (Get-Command -Name ([System.Management.Automation.WildcardPattern]::Escape($env:ZJ_PYTHON)) -CommandType Application -ErrorAction SilentlyContinue)) { throw "ZJ_PYTHON executable is unavailable: $env:ZJ_PYTHON. Set one Python 3.10+ executable path without arguments." }
    & $env:ZJ_PYTHON $helper launch --argv64 $encoded
}
elseif (Get-Command py -CommandType Application -ErrorAction SilentlyContinue) { & py -3 $helper launch --argv64 $encoded }
elseif (Get-Command python -CommandType Application -ErrorAction SilentlyContinue) { & python $helper launch --argv64 $encoded }
else { throw 'Python 3.10+ is required for zj. Set ZJ_PYTHON to its executable path if it is installed under another name.' }
exit $LASTEXITCODE
