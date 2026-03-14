param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug'
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

function Test-PythonCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments
  )

  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($null -eq $python) {
    return $false
  }

  & $python.Source @Arguments *> $null
  return $LASTEXITCODE -eq 0
}

Write-Host 'Running control-plane lint...'
if (Test-PythonCommand -Arguments @('-m', 'ruff', '--version')) {
  & (Join-Path $PSScriptRoot 'lint-control-plane.ps1')
}
else {
  Write-Host 'Skipping control-plane lint because ruff is not yet available.'
}

Write-Host ''
Write-Host 'Running control-plane type checks...'
if (Test-PythonCommand -Arguments @('-m', 'mypy', '--version')) {
  & (Join-Path $PSScriptRoot 'typecheck-control-plane.ps1')
}
else {
  Write-Host 'Skipping control-plane type checks because mypy is not yet available.'
}

Write-Host ''
Write-Host 'Running control-plane quality checks...'
if (Test-PythonCommand -Arguments @('-m', 'coverage', '--version')) {
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
if (-not [string]::IsNullOrWhiteSpace((Get-ResolvedToolPath -ToolName 'clang-format'))) {
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
  if ($_.Exception.Message -like 'No supported C++ toolchain was detected.*') {
    Write-Host 'Skipping C++ build/test because a supported C++ toolchain is not yet available.'
  }
  else {
    throw
  }
}

Write-Host ''
Write-Host 'check-all completed.'
