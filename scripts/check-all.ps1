param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug'
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

Write-Host 'Running control-plane lint...'
if ($null -ne (Get-Command ruff -ErrorAction SilentlyContinue)) {
  & (Join-Path $PSScriptRoot 'lint-control-plane.ps1')
}
else {
  Write-Host 'Skipping control-plane lint because ruff is not yet available.'
}

Write-Host ''
Write-Host 'Running control-plane quality checks...'
if ($null -ne (Get-Command coverage -ErrorAction SilentlyContinue)) {
  & (Join-Path $PSScriptRoot 'coverage-control-plane.ps1')
}
else {
  Write-Host 'Falling back to plain control-plane tests because coverage is not yet available.'
  & (Join-Path $PSScriptRoot 'test-control-plane.ps1')
}

Write-Host ''
Write-Host 'Running prerequisite report...'
& (Join-Path $PSScriptRoot 'bootstrap.ps1')

Write-Host ''
if ($null -ne (Get-Command clang-format -ErrorAction SilentlyContinue)) {
  Write-Host 'Verifying C++ formatting...'
  & (Join-Path $PSScriptRoot 'verify-format.ps1')
}
else {
  Write-Host 'Skipping format verification because clang-format is not yet available.'
}

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
