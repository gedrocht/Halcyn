$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
  throw 'python is not installed or not on PATH.'
}

& $python.Source -m coverage --version *> $null
if ($LASTEXITCODE -ne 0) {
  throw 'coverage is not installed for the active Python. Install it with: python -m pip install coverage'
}

$projectRoot = Get-ProjectRoot
Push-Location $projectRoot

try {
  $coverageDataFile = '.coverage-desktop-multi-renderer-data-source-panel'
  $reportFile = 'coverage-desktop-multi-renderer-data-source-panel.xml'
  Remove-Item $coverageDataFile -ErrorAction SilentlyContinue
  Remove-Item $reportFile -ErrorAction SilentlyContinue
  $env:COVERAGE_FILE = $coverageDataFile
  & $python.Source -m coverage run --branch --source desktop_multi_renderer_data_source_panel,desktop_shared_control_support -m unittest discover -s desktop_multi_renderer_data_source_panel/tests -p "test_*.py"
  if ($LASTEXITCODE -ne 0) {
    throw "coverage run failed with exit code $LASTEXITCODE."
  }
  & $python.Source -m coverage report -m
  if ($LASTEXITCODE -ne 0) {
    throw "coverage report failed with exit code $LASTEXITCODE."
  }
  & $python.Source -m coverage xml -o $reportFile
  if ($LASTEXITCODE -ne 0) {
    throw "coverage xml failed with exit code $LASTEXITCODE."
  }
}
finally {
  Remove-Item Env:COVERAGE_FILE -ErrorAction SilentlyContinue
  Pop-Location
}

Write-Host 'Desktop multi-renderer data source panel coverage completed successfully.'
