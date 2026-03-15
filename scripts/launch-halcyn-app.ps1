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
  [Alias('Fps')]
  [int]$TargetFramesPerSecond = 60,
  [string]$Title = 'Halcyn'
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

& (Join-Path $PSScriptRoot 'build-halcyn-app.ps1') -Configuration $Configuration

$halcynExecutablePath = Get-HalcynExecutablePath -Configuration $Configuration
if (-not (Test-Path $halcynExecutablePath)) {
  throw "The Halcyn executable was not found at $halcynExecutablePath"
}

$applicationArguments = @(
  '--host', $ApiHost,
  '--port', $Port,
  '--width', $Width,
  '--height', $Height,
  '--fps', $TargetFramesPerSecond,
  '--title', $Title
)

if ([string]::IsNullOrWhiteSpace($SceneFile)) {
  $applicationArguments += @('--sample', $Sample)
}
else {
  $applicationArguments += @('--scene-file', $SceneFile)
}

Write-Host "Starting $halcynExecutablePath"
& $halcynExecutablePath @applicationArguments
