param(
  [string]$Host = '127.0.0.1',
  [int]$Port = 9001,
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$command = @(
  '-m',
  'control_plane.server',
  '--host',
  $Host,
  '--port',
  $Port,
  '--project-root',
  $projectRoot
)

if (-not $NoBrowser) {
  Start-Process "http://$Host`:$Port"
}

Push-Location $projectRoot
try {
  & python @command
}
finally {
  Pop-Location
}

