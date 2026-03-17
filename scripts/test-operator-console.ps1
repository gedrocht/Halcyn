$ErrorActionPreference = 'Stop'

Write-Host 'test-operator-console.ps1 is now a compatibility wrapper.'
Write-Host 'The preferred script name is test-visualizer-studio.ps1.'

& (Join-Path $PSScriptRoot 'test-visualizer-studio.ps1')
