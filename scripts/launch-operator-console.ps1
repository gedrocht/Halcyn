param()

$ErrorActionPreference = 'Stop'

Write-Host 'launch-operator-console.ps1 is now a compatibility wrapper.'
Write-Host 'The preferred launcher name is launch-visualizer-studio.ps1.'

& (Join-Path $PSScriptRoot 'launch-visualizer-studio.ps1')
