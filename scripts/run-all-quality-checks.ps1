param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug'
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

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

Write-Host 'Running browser Control Center lint...'
if (Test-PythonCommand -Arguments @('-m', 'ruff', '--version')) {
  & (Join-Path $PSScriptRoot 'lint-browser-control-center.ps1')
}
else {
  Write-Host 'Skipping browser Control Center lint because ruff is not yet available.'
}

Write-Host ''
Write-Host 'Running desktop render control panel lint...'
if (Test-PythonCommand -Arguments @('-m', 'ruff', '--version')) {
  & (Join-Path $PSScriptRoot 'lint-desktop-render-control-panel.ps1')
}
else {
  Write-Host 'Skipping desktop render control panel lint because ruff is not yet available.'
}

Write-Host ''
Write-Host 'Running desktop spectrograph control panel lint...'
if (Test-PythonCommand -Arguments @('-m', 'ruff', '--version')) {
  & (Join-Path $PSScriptRoot 'lint-desktop-spectrograph-control-panel.ps1')
}
else {
  Write-Host 'Skipping desktop spectrograph control panel lint because ruff is not yet available.'
}

Write-Host ''
Write-Host 'Running browser Control Center type checks...'
if (Test-PythonCommand -Arguments @('-m', 'mypy', '--version')) {
  & (Join-Path $PSScriptRoot 'typecheck-browser-control-center.ps1')
}
else {
  Write-Host 'Skipping browser Control Center type checks because mypy is not yet available.'
}

Write-Host ''
Write-Host 'Running desktop render control panel type checks...'
if (Test-PythonCommand -Arguments @('-m', 'mypy', '--version')) {
  & (Join-Path $PSScriptRoot 'typecheck-desktop-render-control-panel.ps1')
}
else {
  Write-Host 'Skipping desktop render control panel type checks because mypy is not yet available.'
}

Write-Host ''
Write-Host 'Running desktop spectrograph control panel type checks...'
if (Test-PythonCommand -Arguments @('-m', 'mypy', '--version')) {
  & (Join-Path $PSScriptRoot 'typecheck-desktop-spectrograph-control-panel.ps1')
}
else {
  Write-Host 'Skipping desktop spectrograph control panel type checks because mypy is not yet available.'
}

Write-Host ''
Write-Host 'Running browser Control Center quality checks...'
if (Test-PythonCommand -Arguments @('-m', 'coverage', '--version')) {
  & (Join-Path $PSScriptRoot 'measure-browser-control-center-coverage.ps1')
}
else {
  Write-Host 'Falling back to plain browser Control Center tests because coverage is not yet available.'
  & (Join-Path $PSScriptRoot 'test-browser-control-center.ps1')
}

Write-Host ''
Write-Host 'Running desktop render control panel quality checks...'
if (Test-PythonCommand -Arguments @('-m', 'coverage', '--version')) {
  & (Join-Path $PSScriptRoot 'measure-desktop-render-control-panel-coverage.ps1')
}
else {
  Write-Host 'Falling back to plain desktop render control panel tests because coverage is not yet available.'
  & (Join-Path $PSScriptRoot 'test-desktop-render-control-panel.ps1')
}

Write-Host ''
Write-Host 'Running desktop spectrograph control panel quality checks...'
if (Test-PythonCommand -Arguments @('-m', 'coverage', '--version')) {
  & (Join-Path $PSScriptRoot 'measure-desktop-spectrograph-control-panel-coverage.ps1')
}
else {
  Write-Host 'Falling back to plain desktop spectrograph control panel tests because coverage is not yet available.'
  & (Join-Path $PSScriptRoot 'test-desktop-spectrograph-control-panel.ps1')
}

Write-Host ''
Write-Host 'Running prerequisite report...'
& (Join-Path $PSScriptRoot 'report-prerequisites.ps1')

Write-Host ''
if (-not [string]::IsNullOrWhiteSpace((Get-ResolvedToolPath -ToolName 'clang-format'))) {
  Write-Host 'Verifying C++ formatting...'
  & (Join-Path $PSScriptRoot 'verify-cpp-formatting.ps1')
}
else {
  Write-Host 'Skipping format verification because clang-format is not yet available.'
}

Write-Host ''
try {
  $null = Get-PreferredGenerator
  Write-Host 'Running C++ test suite...'
  & (Join-Path $PSScriptRoot 'run-native-tests.ps1') -Configuration $Configuration
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
Write-Host 'run-all-quality-checks completed.'
