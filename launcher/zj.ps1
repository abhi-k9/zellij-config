# zellij-config launcher - zj.ps1, the plugin update check behind zj.cmd (Windows).
#
#   zj.ps1 -Startup                     run the check (zj.cmd calls this when due)
#   zj.ps1 -CheckUpdates [-Config FILE] only report; exit 0 = all current,
#                                       1 = newer release(s), 2 = couldn't check
#
# Same rules as the POSIX launcher/zj: every
# location="https://github.com/OWNER/REPO/releases/download/TAG/..." in the
# config zellij loads is compared with that repo's latest GitHub release, so new
# plugins are covered without a list to maintain; file: and other locations are
# listed as not checked. Nothing is ever changed. The check's date is kept as
# the modification time of %LOCALAPPDATA%\zellij-config\plugin-update-check,
# which zj.cmd tests; after a check that couldn't reach GitHub it's set back 29
# days, so the next try is a day later. Windows PowerShell 5.1 or later; this
# file stays ASCII-only because 5.1 misreads UTF-8 scripts without a BOM.
param(
    [switch]$Startup,
    [switch]$CheckUpdates,
    [string]$Config
)
$ErrorActionPreference = 'Continue'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$Stamp = Join-Path $env:LOCALAPPDATA 'zellij-config\plugin-update-check'

# The config.kdl zellij loads: $env:ZELLIJ_CONFIG_FILE, else config.kdl in the
# dir `zellij setup --check` reports. $null if unknown.
function Get-ConfigFile {
    if ($env:ZELLIJ_CONFIG_FILE) { return $env:ZELLIJ_CONFIG_FILE }
    foreach ($line in (& zellij setup --check 2>&1)) {
        if ("$line" -match '^\[CONFIG DIR\]: "(.*)"$') { return (Join-Path $Matches[1] 'config.kdl') }
    }
    return $null
}

# Tag of OWNER/REPO's latest release, from where github.com/.../releases/latest
# redirects (no API rate limit). '-' if GitHub has no release, $null if it
# didn't answer.
function Get-LatestTag([string]$Repo) {
    try {
        $req = [Net.HttpWebRequest]::Create("https://github.com/$Repo/releases/latest")
        $req.Method = 'HEAD'
        $req.AllowAutoRedirect = $false
        $req.Timeout = 8000
        $req.UserAgent = 'zellij-config-zj'
        $resp = $req.GetResponse()
        try { $loc = $resp.Headers['Location'] } finally { $resp.Close() }
    } catch {
        return $null
    }
    if ($loc -match '/releases/tag/([^/?#]+)$') { return [Uri]::UnescapeDataString($Matches[1]) }
    if ($loc) { return '-' }
    return $null
}

# One report line per plugin location in $File, and the result code.
function Invoke-UpdateCheck([string]$File) {
    $lines = New-Object System.Collections.Generic.List[string]
    if (-not $File -or -not (Test-Path -LiteralPath $File)) {
        $lines.Add("zj: can't read zellij's config ($File)")
        return [pscustomobject]@{ Code = 2; Lines = $lines }
    }
    $lines.Add("Plugin pins in ${File}:")
    $active = ([IO.File]::ReadAllText($File) -split "`n" | Where-Object { $_ -notmatch '^\s*//' }) -join "`n"
    $locs = [regex]::Matches($active, 'location="((?:https?|file):[^"]+)"') |
        ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
    $newer = 0; $checked = 0; $failed = $false
    foreach ($loc in $locs) {
        $leaf = ($loc -split '[/\\]')[-1]
        if ($loc -match '^https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/[^/]+$') {
            $repo = "$($Matches[1])/$($Matches[2])"; $name = $Matches[2]; $pinned = $Matches[3]
            $latest = Get-LatestTag $repo
            if ($null -eq $latest) {
                $lines.Add(('  {0,-16} {1,-10} no answer from GitHub (offline, or the repo is gone)' -f $name, $pinned)); $failed = $true; break
            }
            $checked++
            if ($latest -eq '-') { $lines.Add(('  {0,-16} {1,-10} no published release found' -f $name, $pinned)) }
            elseif ($latest -eq $pinned) { $lines.Add(('  {0,-16} {1,-10} current' -f $name, $pinned)) }
            else {
                $newer++
                $lines.Add(('  {0,-16} {1,-10} -> {2} available: https://github.com/{3}/releases/tag/{2}' -f $name, $pinned, $latest, $repo))
            }
        } elseif ($loc -like 'file:*') {
            $lines.Add(('  {0,-27} loads from disk, not checked' -f $leaf))
        } else {
            $lines.Add(('  {0,-27} not a GitHub release URL, not checked' -f $leaf))
        }
    }
    $code = if ($newer -gt 0) { 1 } elseif ($failed -or $checked -eq 0) { 2 } else { 0 }
    return [pscustomobject]@{ Code = $code; Lines = $lines }
}

if ($CheckUpdates) {
    if (-not $Config) { $Config = Get-ConfigFile }
    $r = Invoke-UpdateCheck $Config
    $r.Lines | ForEach-Object { Write-Host $_ }
    exit $r.Code
}

if ($Startup) {
    if ($env:ZJ_NO_UPDATE_CHECK) { exit 0 }
    if (-not $Config) { $Config = Get-ConfigFile }
    if (-not $Config) { exit 0 }
    $r = Invoke-UpdateCheck $Config
    try {
        New-Item -ItemType Directory -Force (Split-Path $Stamp) | Out-Null
        Set-Content -LiteralPath $Stamp -Value ("last check {0:yyyy-MM-dd HH:mm}, result {1}" -f (Get-Date), $r.Code)
        if ($r.Code -eq 2) { (Get-Item -LiteralPath $Stamp).LastWriteTime = (Get-Date).AddDays(-29) }
    } catch { }
    if ($r.Code -eq 1) {
        $r.Lines | ForEach-Object { Write-Host $_ }
        Write-Host ''
        Write-Host 'Newer plugin releases exist. Nothing was changed; to update, see the'
        Write-Host 'README section "Updating a pinned plugin".'
        if (-not [Console]::IsInputRedirected) { [void](Read-Host 'Press Enter to start zellij') }
    }
    exit 0
}

Write-Host 'usage: zj.ps1 -Startup | -CheckUpdates [-Config FILE]   (normally run by zj.cmd)'
exit 2
