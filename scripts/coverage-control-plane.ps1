$ErrorActionPreference = 'Stop'

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
  throw 'python is not installed or not on PATH.'
}

& python -m coverage --version *> $null
if ($LASTEXITCODE -ne 0) {
  throw 'coverage is not installed for the active Python. Install it with: python -m pip install "coverage[toml]"'
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projectRoot

try {
  & python -m coverage erase
  if ($LASTEXITCODE -ne 0) {
    throw "coverage erase failed with exit code $LASTEXITCODE."
  }

  & python -m coverage run -m unittest discover -s control_plane/tests -p "test_*.py"
  if ($LASTEXITCODE -ne 0) {
    throw "coverage run failed with exit code $LASTEXITCODE."
  }

  & python -m coverage report --fail-under=85
  if ($LASTEXITCODE -ne 0) {
    throw "coverage report failed with exit code $LASTEXITCODE."
  }

  & python -m coverage xml -o coverage-control-plane.xml
  if ($LASTEXITCODE -ne 0) {
    throw "coverage xml failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}

Write-Host 'Control-plane coverage completed successfully.'
