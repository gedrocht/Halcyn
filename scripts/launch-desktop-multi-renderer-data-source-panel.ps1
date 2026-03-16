param()

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
  throw 'python is not installed or not on PATH.'
}

$projectRoot = Get-ProjectRoot
Push-Location $projectRoot

try {
  & $python.Source -m desktop_multi_renderer_data_source_panel
}
finally {
  Pop-Location
}

