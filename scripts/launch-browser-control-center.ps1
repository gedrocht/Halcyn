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
$rootUrl = $compatibility.BaseUrl

if ($compatibility.SceneStudioAvailable) {
  if (-not $NoBrowser) {
    Start-Process $rootUrl
  }

  Write-Host "Reusing the already-running Halcyn Control Center at $rootUrl"
  return
}

if ($compatibility.SummaryAvailable) {
  throw @"
Another Halcyn Control Center is already running at $rootUrl, but it does not expose the newer Scene Studio routes.

Stop that older server and rerun this script, or choose a different port with:
  .\scripts\launch-browser-control-center.ps1 -Port 9010
"@
}

if (-not $NoBrowser) {
  Start-BrowserWhenReady -Url $rootUrl
}

Push-Location $projectRoot
try {
  & python @command
}
finally {
  Pop-Location
}
