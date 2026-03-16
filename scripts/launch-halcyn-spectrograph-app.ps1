param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug',
  [string]$ApiHost = '127.0.0.1',
  [int]$Port = 8090,
  [ValidateSet('default', '2d', '3d', 'spectrograph')]
  [string]$Sample = 'spectrograph',
  [string]$SceneFile = '',
  [int]$Width = 1440,
  [int]$Height = 900,
  [Alias('Fps')]
  [int]$TargetFramesPerSecond = 60,
  [string]$Title = 'Halcyn Spectrograph'
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

& (Join-Path $PSScriptRoot 'build-halcyn-app.ps1') -Configuration $Configuration

$spectrographExecutablePath = Get-HalcynSpectrographExecutablePath -Configuration $Configuration
if (-not (Test-Path $spectrographExecutablePath)) {
  throw "The Halcyn spectrograph executable was not found at $spectrographExecutablePath"
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

Write-Host "Starting $spectrographExecutablePath"
& $spectrographExecutablePath @applicationArguments

