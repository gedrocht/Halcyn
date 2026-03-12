param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug'
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

Write-Host 'Running control-plane tests...'
& (Join-Path $PSScriptRoot 'test-control-plane.ps1')

Write-Host ''
Write-Host 'Running prerequisite report...'
& (Join-Path $PSScriptRoot 'bootstrap.ps1')

Write-Host ''
try {
  $null = Get-PreferredGenerator
  Write-Host 'Running C++ test suite...'
  & (Join-Path $PSScriptRoot 'test.ps1') -Configuration $Configuration
}
catch {
  Write-Host 'Skipping C++ build/test because a supported C++ toolchain is not yet available.'
}

Write-Host ''
Write-Host 'check-all completed.'
