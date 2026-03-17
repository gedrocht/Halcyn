param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug',
  [ValidateSet('default', '2d', '3d', 'spectrograph')]
  [string]$Sample = 'spectrograph',
  [switch]$SkipAudioSourcePanel
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$spectrographRendererScriptPath = Join-Path $PSScriptRoot 'launch-halcyn-spectrograph-app.ps1'
$spectrographControlPanelScriptPath = Join-Path $PSScriptRoot 'launch-desktop-spectrograph-control-panel.ps1'
$spectrographAudioSourcePanelScriptPath = Join-Path $PSScriptRoot 'launch-desktop-spectrograph-audio-source-panel.ps1'

Write-Host 'Opening the Halcyn spectrograph audio workbench...'
Write-Host ''
Write-Host 'This helper opens the main pieces in separate windows so you can:'
Write-Host '  1. watch the dedicated spectrograph renderer'
Write-Host '  2. tune how generic data becomes bars in the control panel'
Write-Host '  3. feed live audio into that panel from the helper app'
Write-Host ''

Start-HalcynScriptInNewWindow -ScriptPath $spectrographRendererScriptPath -ArgumentList @(
  '-Configuration', $Configuration,
  '-Sample', $Sample
)

Start-Sleep -Milliseconds 400

Start-HalcynScriptInNewWindow -ScriptPath $spectrographControlPanelScriptPath

if (-not $SkipAudioSourcePanel) {
  Start-Sleep -Milliseconds 400
  Start-HalcynScriptInNewWindow -ScriptPath $spectrographAudioSourcePanelScriptPath
}

Write-Host 'Windows launched.'
Write-Host ''
Write-Host 'Suggested next steps:'
Write-Host '  - Wait for the spectrograph renderer window to appear.'
Write-Host '  - In the Desktop Spectrograph Control Panel, keep the external source bridge enabled.'
if (-not $SkipAudioSourcePanel) {
  Write-Host '  - In the Spectrograph Audio Source Panel, choose a device and start capture.'
  Write-Host '  - Use Send once or Start live to feed the spectrograph panel.'
}
else {
  Write-Host '  - Start the audio source panel later if you want live audio input.'
}
