$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$projectRoot = Get-ProjectRoot
$wikiConfigurationPath = Join-Path $projectRoot 'mkdocs-wiki.yml'

if (-not (Test-PythonModuleAvailable -ModuleName 'mkdocs')) {
  throw @"
Python package 'mkdocs' is required to build the hosted beginner wiki.

Install it with:
  python -m pip install mkdocs
"@
}

Push-Location $projectRoot

try {
  Write-Host 'Building the beginner walkthrough wiki...'
  & python -m mkdocs build --strict --config-file $wikiConfigurationPath
  Assert-LastExitCode -StepName 'MkDocs build'
}
finally {
  Pop-Location
}
