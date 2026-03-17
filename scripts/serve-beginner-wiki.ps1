param(
  [int]$Port = 8010
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$projectRoot = Get-ProjectRoot
$wikiConfigurationPath = Join-Path $projectRoot 'mkdocs-wiki.yml'

if (-not (Test-PythonModuleAvailable -ModuleName 'mkdocs')) {
  throw @"
Python package 'mkdocs' is required to serve the hosted beginner wiki.

Install it with:
  python -m pip install mkdocs
"@
}

Push-Location $projectRoot

try {
  Write-Host "Serving the beginner walkthrough wiki on http://127.0.0.1:$Port"
  & python -m mkdocs serve --config-file $wikiConfigurationPath --dev-addr "127.0.0.1:$Port"
  Assert-LastExitCode -StepName 'MkDocs serve'
}
finally {
  Pop-Location
}
