param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug'
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

& (Join-Path $PSScriptRoot 'build.ps1') -Configuration $Configuration

Write-Host "Running tests ($Configuration)..."
Invoke-HalcynCtest -Configuration $Configuration
