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
  & $python.Source -m unittest discover -s desktop_spectrograph_audio_source_panel/tests -p "test_*.py"
  Assert-LastExitCode -StepName 'desktop spectrograph audio source panel tests'
}
finally {
  Pop-Location
}
