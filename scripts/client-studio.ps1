param(
  [string]$BindHost = '127.0.0.1',
  [int]$Port = 9001,
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

$projectRoot = Get-ProjectRoot
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
$clientUrl = "http://$BindHost`:$Port/client/"

if ($compatibility.ClientStudioAvailable) {
  if (-not $NoBrowser) {
    Start-Process $clientUrl
  }

  Write-Host "Reusing the already-running Halcyn control plane at $($compatibility.BaseUrl)"
  return
}

if ($compatibility.SummaryAvailable) {
  throw @"
Another Halcyn control plane is already running at $($compatibility.BaseUrl), but it does not expose Client Studio.

Stop that older server and rerun this script, or choose a different port with:
  .\scripts\client-studio.ps1 -Port 9010
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
