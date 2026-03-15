$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
  throw 'python is not installed or not on PATH.'
}

& $python.Source -m mypy --version *> $null
if ($LASTEXITCODE -ne 0) {
  throw 'mypy is not installed for the active Python. Install it with: python -m pip install mypy'
}

$projectRoot = Get-ProjectRoot
Push-Location $projectRoot

try {
  & $python.Source -m mypy control_plane
  if ($LASTEXITCODE -ne 0) {
    throw "mypy failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}

Write-Host 'Control-plane type checks completed successfully.'
