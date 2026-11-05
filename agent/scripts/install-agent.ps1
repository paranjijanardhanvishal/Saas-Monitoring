# Installs the SaaS Security Monitor endpoint agent as an explicit per-user
# logon task. No hidden persistence is created: the task name, command and
# removal script are printed at the end.
[CmdletBinding()]
param(
    [string]$BackendUrl = $env:BACKEND_URL,
    [string]$StateDir = (Join-Path $env:LOCALAPPDATA "SaaSMonitorAgent"),
    [string]$PythonExe = "",
    [string]$TaskName = "SaaSMonitorAgent",
    [switch]$SkipEnroll
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if (-not $BackendUrl) { $BackendUrl = "https://monitor.example.com/api" }
if ($BackendUrl -match '^http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(/|$)') {
    Write-Warning "Loopback HTTP is for local development only."
} elseif ($BackendUrl -notmatch '^https://') {
    throw "BackendUrl must use HTTPS outside loopback development."
}

if (-not $PythonExe) {
    $venvPython = Join-Path $RepoRoot "venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $PythonExe = $venvPython
    } else {
        $command = Get-Command python.exe -ErrorAction SilentlyContinue
        if (-not $command) { throw "Python was not found. Pass -PythonExe with the full path." }
        $PythonExe = $command.Source
    }
}
if (-not (Test-Path $PythonExe)) { throw "Python executable not found: $PythonExe" }

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
$identity = if ($env:USERDOMAIN) { "$env:USERDOMAIN\$env:USERNAME" } else { $env:USERNAME }
& icacls.exe $StateDir /inheritance:r /grant:r "${identity}:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not restrict permissions on $StateDir" }

$stateFile = Join-Path $StateDir "device.json"
if (-not $SkipEnroll -and -not (Test-Path $stateFile)) {
    Write-Host "A one-time enrollment token is required." -ForegroundColor Cyan
    Write-Host "Issue one from the dashboard after granting monitoring consent." -ForegroundColor Cyan
    $secure = Read-Host "Enrollment token" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $env:AGENT_ENROLLMENT_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    try {
        Push-Location $RepoRoot
        & $PythonExe -m agent enroll --backend-url $BackendUrl --state-dir $StateDir
        if ($LASTEXITCODE -ne 0) { throw "Enrollment failed. Check the backend URL, consent and token." }
    } finally {
        Pop-Location
        Remove-Item Env:\AGENT_ENROLLMENT_TOKEN -ErrorAction SilentlyContinue
    }
}

$arguments = "-m agent run --backend-url `"$BackendUrl`" --state-dir `"$StateDir`""
$action = New-ScheduledTaskAction -Execute $PythonExe -Argument $arguments -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Description "SaaS Security Monitor metadata-only endpoint agent" -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host ""
Write-Host "Installed scheduled task '$TaskName' (runs at logon for $identity)." -ForegroundColor Green
Write-Host "State directory: $StateDir"
Write-Host "Stop:    powershell -File agent\scripts\stop-agent.ps1 -TaskName $TaskName"
Write-Host "Remove:  powershell -File agent\scripts\uninstall-agent.ps1 -TaskName $TaskName -StateDir `"$StateDir`" -PurgeState"
