param()

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
  throw 'python is not installed or not on PATH.'
}

$projectRoot = Get-ProjectRoot
Initialize-HalcynActivityLogEnvironment | Out-Null

Push-Location $projectRoot
try {
  & $python.Source -m desktop_visualizer_operator_console
}
finally {
  Pop-Location
}
