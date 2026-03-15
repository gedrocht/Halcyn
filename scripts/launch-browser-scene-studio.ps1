param(
  [string]$BindHost = '127.0.0.1',
  [int]$Port = 9001,
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$projectRoot = Get-ProjectRoot
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
$clientUrl = "http://$BindHost`:$Port/scene-studio/"

if ($compatibility.SceneStudioAvailable) {
  if (-not $NoBrowser) {
    Start-Process $clientUrl
  }

  Write-Host "Reusing the already-running Halcyn Control Center at $($compatibility.BaseUrl)"
  return
}

if ($compatibility.SummaryAvailable) {
  throw @"
Another Halcyn Control Center is already running at $($compatibility.BaseUrl), but it does not expose Scene Studio.

Stop that older server and rerun this script, or choose a different port with:
  .\scripts\launch-browser-scene-studio.ps1 -Port 9010
"@
}

if (-not $NoBrowser) {
  Start-BrowserWhenReady -Url $clientUrl
}

Push-Location $projectRoot
try {
  & python @command
}
finally {
  Pop-Location
}
