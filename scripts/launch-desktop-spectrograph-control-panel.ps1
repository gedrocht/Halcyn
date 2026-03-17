param()

$ErrorActionPreference = 'Stop'

Write-Host 'launch-desktop-spectrograph-control-panel.ps1 is now a compatibility wrapper.'
Write-Host 'Use launch-visualizer-studio.ps1 and choose the Bar wall scene family.'

& (Join-Path $PSScriptRoot 'launch-visualizer-studio.ps1')
