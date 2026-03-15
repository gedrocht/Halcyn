$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
  throw 'python is not installed or not on PATH.'
}

& $python.Source -m ruff --version *> $null
if ($LASTEXITCODE -ne 0) {
  throw 'ruff is not installed for the active Python. Install it with: python -m pip install ruff'
}

$projectRoot = Get-ProjectRoot
Push-Location $projectRoot

try {
  & $python.Source -m ruff check control_plane
  if ($LASTEXITCODE -ne 0) {
    throw "ruff check failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}

Write-Host 'Control-plane lint completed successfully.'
