param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug',
  [string]$ApiHost = '127.0.0.1',
  [int]$Port = 8080,
  [ValidateSet('default', '2d', '3d', 'spectrograph')]
  [string]$Sample = 'default',
  [string]$SceneFile = '',
  [int]$Width = 1280,
  [int]$Height = 720,
  [Alias('Fps')]
  [int]$TargetFramesPerSecond = 60,
  [string]$Title = 'Halcyn Visualizer'
)

$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'launch-halcyn-app.ps1') `
  -Configuration $Configuration `
  -ApiHost $ApiHost `
  -Port $Port `
  -Sample $Sample `
  -SceneFile $SceneFile `
  -Width $Width `
  -Height $Height `
  -TargetFramesPerSecond $TargetFramesPerSecond `
  -Title $Title
