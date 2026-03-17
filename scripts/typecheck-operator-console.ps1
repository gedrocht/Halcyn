$ErrorActionPreference = 'Stop'

Write-Host 'typecheck-operator-console.ps1 is now a compatibility wrapper.'
Write-Host 'The preferred script name is typecheck-visualizer-studio.ps1.'

& (Join-Path $PSScriptRoot 'typecheck-visualizer-studio.ps1')
