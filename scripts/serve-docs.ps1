param(
  [int]$Port = 5500
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

$docsRoot = Join-Path (Get-ProjectRoot) 'docs/site'
Push-Location $docsRoot

try {
  Write-Host "Serving docs from $docsRoot"
  Write-Host "Open http://127.0.0.1:$Port in your browser."
  Start-Process "http://127.0.0.1:$Port"
  & python -m http.server $Port
}
finally {
  Pop-Location
}
