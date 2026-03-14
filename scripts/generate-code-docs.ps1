$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$outputDirectory = Join-Path $projectRoot 'docs/generated/code-reference'
$doxygen = Get-ResolvedToolPath -ToolName 'doxygen'

if ([string]::IsNullOrWhiteSpace($doxygen)) {
  throw 'Doxygen is not installed. Install Doxygen, then rerun this script.'
}

New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
Push-Location $projectRoot

try {
  & $doxygen Doxyfile
  Write-Host "Code docs generated at $outputDirectory"
}
finally {
  Pop-Location
}
