# Recover the specific Windows stale-socket startup failure without deleting data.
# First quit Docker Desktop with: docker desktop stop --timeout 30
[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference = 'Stop'

if (Get-Process 'com.docker.backend','Docker Desktop' -ErrorAction SilentlyContinue) {
    throw 'Quit Docker Desktop before repairing its stopped runtime directories.'
}
$localRoot = [IO.Path]::GetFullPath($env:LOCALAPPDATA)
$targets = @(
    @{ Relative = 'Docker\run'; Sockets = @('dockerInference','userAnalyticsOtlpHttp.sock') },
    @{ Relative = 'docker-secrets-engine'; Sockets = @('engine.sock') }
)
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$plans = @()
foreach ($target in $targets) {
    $path = [IO.Path]::GetFullPath((Join-Path $localRoot $target.Relative))
    if (-not $path.StartsWith($localRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Runtime path escaped LocalAppData.'
    }
    $directory = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    if ($null -eq $directory) { continue }
    if (-not $directory.PSIsContainer -or ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Unexpected runtime directory type: $path"
    }
    $entries = @(Get-ChildItem -LiteralPath $path -Force)
    if ($entries.Count -eq 0) { continue }
    # Fail closed if a future Docker version stores anything else here.
    foreach ($entry in $entries) {
        if ($entry.Name -notin $target.Sockets -or $entry.PSIsContainer -or $entry.Length -ne 0 -or
            -not ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Unrecognized runtime contents; no changes made: $path"
        }
    }
    $backup = $directory.Name + '.stale-' + $stamp
    if (Test-Path -LiteralPath (Join-Path $directory.Parent.FullName $backup)) {
        throw 'Backup directory already exists.'
    }
    $plans += @{ Path = $path; Backup = $backup }
}
foreach ($plan in $plans) {
    if ($PSCmdlet.ShouldProcess($plan.Path, 'Preserve stale runtime as ' + $plan.Backup)) {
        Rename-Item -LiteralPath $plan.Path -NewName $plan.Backup
        Write-Host ('Preserved: ' + $plan.Path + ' -> ' + $plan.Backup)
    }
}
if (-not $WhatIfPreference) {
    & docker desktop start --timeout 60
    if ($LASTEXITCODE -ne 0) { throw 'Docker startup failed; inspect its latest backend log.' }
    & docker info --format '{{.ServerVersion}}'
    if ($LASTEXITCODE -ne 0) { throw 'Docker engine is not ready.' }
}
