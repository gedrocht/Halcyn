param()

$ErrorActionPreference = 'Stop'

Write-Host 'launch-desktop-multi-renderer-data-source-panel.ps1 is now a compatibility wrapper.'
Write-Host 'Visualizer Studio now owns live data sources and scene delivery.'

& (Join-Path $PSScriptRoot 'launch-visualizer-studio.ps1')
