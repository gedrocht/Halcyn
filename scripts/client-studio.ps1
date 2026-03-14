param(
  [string]$BindHost = '127.0.0.1',
  [int]$Port = 9001,
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

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

if (-not $NoBrowser) {
  Start-Process "http://$BindHost`:$Port/client/"
}

Push-Location $projectRoot
try {
  & python @command
}
finally {
  Pop-Location
}
