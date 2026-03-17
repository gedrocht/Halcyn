$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
  throw 'python is not installed or not on PATH.'
}

$projectRoot = Get-ProjectRoot
$previousNativeCommandErrorPreference = $PSNativeCommandUseErrorActionPreference
Push-Location $projectRoot

try {
  # The UI tests can print harmless Tk theme warnings to stderr even when the
  # unittest process exits successfully. Rely on the Python exit code instead of
  # letting PowerShell treat that stderr chatter as a terminating script error.
  $PSNativeCommandUseErrorActionPreference = $false
  & $python.Source -m unittest discover -s desktop_visualizer_operator_console/tests -p "test_*.py"
  if ($LASTEXITCODE -ne 0) {
    throw "unit tests failed with exit code $LASTEXITCODE."
  }
}
finally {
  $PSNativeCommandUseErrorActionPreference = $previousNativeCommandErrorPreference
  Pop-Location
}

Write-Host 'Visualizer Studio tests completed successfully.'
