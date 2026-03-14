param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug',
  [string]$ApiHost = '127.0.0.1',
  [int]$Port = 8080,
  [ValidateSet('default', '2d', '3d')]
  [string]$Sample = 'default',
  [string]$SceneFile = '',
  [int]$Width = 1280,
  [int]$Height = 720,
  [int]$Fps = 60,
  [string]$Title = 'Halcyn'
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

& (Join-Path $PSScriptRoot 'build.ps1') -Configuration $Configuration

$executable = Get-HalcynExecutablePath -Configuration $Configuration
if (-not (Test-Path $executable)) {
  throw "The Halcyn executable was not found at $executable"
}

$arguments = @(
  '--host', $ApiHost,
  '--port', $Port,
  '--width', $Width,
  '--height', $Height,
  '--fps', $Fps,
  '--title', $Title
)

if ([string]::IsNullOrWhiteSpace($SceneFile)) {
  $arguments += @('--sample', $Sample)
}
else {
  $arguments += @('--scene-file', $SceneFile)
}

Write-Host "Starting $executable"
& $executable @arguments
