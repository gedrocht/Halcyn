param()

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projectRoot

try {
  & python -m unittest discover -s control_plane/tests -p "test_*.py"
}
finally {
  Pop-Location
}
