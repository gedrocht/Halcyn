$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
  throw 'python is not installed or not on PATH.'
}

& $python.Source -m coverage --version *> $null
if ($LASTEXITCODE -ne 0) {
  throw 'coverage is not installed for the active Python. Install it with: python -m pip install "coverage[toml]"'
}

$projectRoot = Get-ProjectRoot
$coverageFile = Join-Path $projectRoot ".coverage-desktop-spectrograph-audio-source-panel-$PID"
Push-Location $projectRoot

try {
  $env:COVERAGE_FILE = $coverageFile

  & $python.Source -m coverage erase
  if ($LASTEXITCODE -ne 0) {
    throw "coverage erase failed with exit code $LASTEXITCODE."
  }

  & $python.Source -m coverage run --source=desktop_spectrograph_audio_source_panel -m unittest discover -s desktop_spectrograph_audio_source_panel/tests -p "test_*.py"
  if ($LASTEXITCODE -ne 0) {
    throw "coverage run failed with exit code $LASTEXITCODE."
  }

  & $python.Source -m coverage report --fail-under=90
  if ($LASTEXITCODE -ne 0) {
    throw "coverage report failed with exit code $LASTEXITCODE."
  }

  & $python.Source -m coverage xml -o coverage-desktop-spectrograph-audio-source-panel.xml
  if ($LASTEXITCODE -ne 0) {
    throw "coverage xml failed with exit code $LASTEXITCODE."
  }
}
finally {
  Remove-Item $coverageFile -ErrorAction SilentlyContinue
  Remove-Item "${coverageFile}-journal" -ErrorAction SilentlyContinue
  Remove-Item Env:COVERAGE_FILE -ErrorAction SilentlyContinue
  Pop-Location
}

Write-Host 'Desktop spectrograph audio source panel coverage completed successfully.'
