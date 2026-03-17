param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug'
)

$ErrorActionPreference = 'Stop'

Write-Host 'launch-spectrograph-audio-workbench.ps1 is now a compatibility wrapper.'
Write-Host 'Use launch-visualizer-workbench.ps1 for the unified workflow.'

& (Join-Path $PSScriptRoot 'launch-visualizer-workbench.ps1') -Configuration $Configuration
