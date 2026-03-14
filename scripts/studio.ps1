param(
  [string]$BindHost = '127.0.0.1',
  [int]$Port = 9001,
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$command = @(
  '-m',
  'control_plane.server',
  '--host',
  $BindHost,
  '--port',
  $Port,
  '--project-root',
  $projectRoot
)

$compatibility = Get-ControlPlaneCompatibility -BindHost $BindHost -Port $Port
$rootUrl = $compatibility.BaseUrl

if ($compatibility.ClientStudioAvailable) {
  if (-not $NoBrowser) {
    Start-Process $rootUrl
  }

  Write-Host "Reusing the already-running Halcyn control plane at $rootUrl"
  return
}

if ($compatibility.SummaryAvailable) {
  throw @"
Another Halcyn control plane is already running at $rootUrl, but it does not expose the newer Client Studio routes.

Stop that older server and rerun this script, or choose a different port with:
  .\scripts\studio.ps1 -Port 9010
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
