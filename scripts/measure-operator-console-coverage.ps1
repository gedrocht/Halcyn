$ErrorActionPreference = 'Stop'

Write-Host 'measure-operator-console-coverage.ps1 is now a compatibility wrapper.'
Write-Host 'The preferred script name is measure-visualizer-studio-coverage.ps1.'

& (Join-Path $PSScriptRoot 'measure-visualizer-studio-coverage.ps1')
