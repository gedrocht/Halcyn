$ErrorActionPreference = 'Stop'

Write-Host 'lint-operator-console.ps1 is now a compatibility wrapper.'
Write-Host 'The preferred script name is lint-visualizer-studio.ps1.'

& (Join-Path $PSScriptRoot 'lint-visualizer-studio.ps1')
