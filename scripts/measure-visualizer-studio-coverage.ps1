$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
  throw 'python is not installed or not on PATH.'
}

& $python.Source -m coverage --version *> $null
if ($LASTEXITCODE -ne 0) {
  throw 'coverage is not installed for the active Python. Install it with: python -m pip install "coverage[toml]"'
}

$projectRoot = Get-ProjectRoot
$coverageFile = Join-Path $projectRoot '.coverage-visualizer-studio'
$previousNativeCommandErrorPreference = $PSNativeCommandUseErrorActionPreference
Push-Location $projectRoot

try {
  # Some Tk and ttkbootstrap test cases can emit harmless stderr noise while still
  # succeeding. We still trust the real process exit code below, so keep stderr
  # from being promoted into a PowerShell exception during the native Python runs.
  $PSNativeCommandUseErrorActionPreference = $false
  $env:COVERAGE_FILE = $coverageFile

  & $python.Source -m coverage erase
  if ($LASTEXITCODE -ne 0) {
    throw "coverage erase failed with exit code $LASTEXITCODE."
  }

  & $python.Source -m coverage run --branch `
    --source=desktop_visualizer_operator_console,desktop_shared_control_support `
    -m unittest discover -s desktop_visualizer_operator_console/tests -p "test_*.py"
  if ($LASTEXITCODE -ne 0) {
    throw "coverage run failed with exit code $LASTEXITCODE."
  }

  & $python.Source -m coverage report --fail-under=90
  if ($LASTEXITCODE -ne 0) {
    throw "coverage report failed with exit code $LASTEXITCODE."
  }

  & $python.Source -m coverage xml -o coverage-visualizer-studio.xml
  if ($LASTEXITCODE -ne 0) {
    throw "coverage xml failed with exit code $LASTEXITCODE."
  }
}
finally {
  $PSNativeCommandUseErrorActionPreference = $previousNativeCommandErrorPreference
  Remove-Item $coverageFile -ErrorAction SilentlyContinue
  Remove-Item "${coverageFile}-journal" -ErrorAction SilentlyContinue
  Remove-Item Env:COVERAGE_FILE -ErrorAction SilentlyContinue
  Pop-Location
}

Write-Host 'Visualizer Studio coverage completed successfully.'
