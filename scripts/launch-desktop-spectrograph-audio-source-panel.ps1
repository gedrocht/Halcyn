param()

$ErrorActionPreference = 'Stop'

Write-Host 'launch-desktop-spectrograph-audio-source-panel.ps1 is now a compatibility wrapper.'
Write-Host 'Use launch-visualizer-studio.ps1 and choose Audio device as the source mode.'

& (Join-Path $PSScriptRoot 'launch-visualizer-studio.ps1')
