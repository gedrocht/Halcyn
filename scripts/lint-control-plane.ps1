$ErrorActionPreference = 'Stop'

$ruff = Get-Command ruff -ErrorAction SilentlyContinue
if ($null -eq $ruff) {
  throw 'ruff is not installed or not on PATH. Install it with: python -m pip install ruff'
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projectRoot

try {
  & ruff check control_plane
  if ($LASTEXITCODE -ne 0) {
    throw "ruff check failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}

Write-Host 'Control-plane lint completed successfully.'
