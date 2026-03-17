$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
  throw 'python is not installed or not on PATH.'
}

$projectRoot = Get-ProjectRoot
Push-Location $projectRoot

try {
  & $python.Source -m unittest discover -s desktop_visualizer_operator_console/tests -p "test_*.py"
  if ($LASTEXITCODE -ne 0) {
    throw "unit tests failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}

Write-Host 'Visualizer Studio tests completed successfully.'
