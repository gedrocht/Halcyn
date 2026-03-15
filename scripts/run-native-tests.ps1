param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug'
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

& (Join-Path $PSScriptRoot 'build-halcyn-app.ps1') -Configuration $Configuration

Write-Host "Running tests ($Configuration)..."
Invoke-HalcynCtest -Configuration $Configuration
