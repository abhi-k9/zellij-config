# zellij-config launcher (Windows PowerShell 5.1+); all policy lives in Python.
# No parameter block: Zellij's own named flags remain literal elements of $args.
$ErrorActionPreference = 'Stop'
$helper = Join-Path $PSScriptRoot '.zellij-config\manage.py'
if (-not (Test-Path -LiteralPath $helper)) { $helper = Join-Path $PSScriptRoot '..\tools\manage.py' }
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
if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 $helper launch --argv64 $encoded }
else { & python $helper launch --argv64 $encoded }
exit $LASTEXITCODE
