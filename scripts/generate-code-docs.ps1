$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$outputDirectory = Join-Path $projectRoot 'docs/generated/code-reference'
$doxygen = Get-Command doxygen -ErrorAction SilentlyContinue

if ($null -eq $doxygen) {
  throw 'Doxygen is not installed or not on PATH. Install Doxygen, then rerun this script.'
}

New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
Push-Location $projectRoot

try {
  & doxygen Doxyfile
  Write-Host "Code docs generated at $outputDirectory"
}
finally {
  Pop-Location
}

