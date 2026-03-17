param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug',
  [string]$ApiHost = '127.0.0.1',
  [int]$Port = 8090,
  [string]$SceneFile = '',
  [int]$Width = 1440,
  [int]$Height = 900,
  [Alias('Fps')]
  [int]$TargetFramesPerSecond = 60,
  [string]$Title = 'Halcyn Visualizer Bar Wall'
)

$ErrorActionPreference = 'Stop'

Write-Host 'launch-halcyn-spectrograph-app.ps1 is now a compatibility wrapper.'
Write-Host 'The unified Visualizer app renders both preset scenes and bar-wall scenes.'

& (Join-Path $PSScriptRoot 'launch-halcyn-app.ps1') `
  -Configuration $Configuration `
  -ApiHost $ApiHost `
  -Port $Port `
  -Sample 'bar-wall' `
  -SceneFile $SceneFile `
  -Width $Width `
  -Height $Height `
  -TargetFramesPerSecond $TargetFramesPerSecond `
  -Title $Title
