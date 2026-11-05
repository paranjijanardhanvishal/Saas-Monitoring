[CmdletBinding()]
param(
    [string]$TaskName = "SaaSMonitorAgent",
    [string]$StateDir = (Join-Path $env:LOCALAPPDATA "SaaSMonitorAgent"),
    [switch]$PurgeState
)

$ErrorActionPreference = "Stop"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task '$TaskName'." -ForegroundColor Green
} else {
    Write-Host "Scheduled task '$TaskName' was not installed."
}

if ($PurgeState) {
    $stateFile = Join-Path $StateDir "device.json"
    if (Test-Path $stateFile) {
        Remove-Item $stateFile -Force
        Write-Host "Removed local device credential: $stateFile" -ForegroundColor Green
    } else {
        Write-Host "No local device credential found at $stateFile."
    }
    Write-Host "The device remains enrolled server-side until an administrator revokes it."
}
