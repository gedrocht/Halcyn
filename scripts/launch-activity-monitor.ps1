param(
  [string]$BindHost = '127.0.0.1',
  [int]$Port = 9001,
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
  throw 'python is not installed or not on PATH.'
}

$projectRoot = Get-ProjectRoot
Initialize-HalcynActivityLogEnvironment | Out-Null

$baseUrl = "http://$BindHost`:$Port"
$activityMonitorUrl = "$baseUrl/activity-monitor/"
$command = @(
  '-m',
  'browser_control_center.control_center_http_server',
  '--host',
  $BindHost,
  '--port',
  $Port,
  '--project-root',
  $projectRoot
)

$compatibility = Get-ControlCenterCompatibility -BindHost $BindHost -Port $Port
$activityMonitorAvailable = Test-HttpSuccess -RequestUrl $activityMonitorUrl

if ($activityMonitorAvailable) {
  if (-not $NoBrowser) {
    Start-Process $activityMonitorUrl
  }

  Write-Host "Reusing the already-running Halcyn Activity Monitor at $activityMonitorUrl"
  return
}

if ($compatibility.SummaryAvailable) {
  throw @"
Another Halcyn Control Center is already running at $baseUrl, but it does not expose the newer Activity Monitor route.

Stop that older server and rerun this script, or choose a different port with:
  .\scripts\launch-activity-monitor.ps1 -Port 9010
"@
}

if (-not $NoBrowser) {
  Start-BrowserWhenReady -Url $activityMonitorUrl
}

Push-Location $projectRoot
try {
  & $python.Source @command
}
finally {
  Pop-Location
}
