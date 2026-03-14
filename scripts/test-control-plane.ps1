param()

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
  throw 'python is not installed or not on PATH.'
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projectRoot

try {
  & $python.Source -m unittest discover -s control_plane/tests -p "test_*.py"
  Assert-LastExitCode -StepName 'control-plane tests'
}
finally {
  Pop-Location
}
