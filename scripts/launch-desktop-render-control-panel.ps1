param()

$ErrorActionPreference = 'Stop'

Write-Host 'launch-desktop-render-control-panel.ps1 is now a compatibility wrapper.'
Write-Host 'Use launch-visualizer-studio.ps1 for the unified desktop workflow.'

& (Join-Path $PSScriptRoot 'launch-visualizer-studio.ps1')
