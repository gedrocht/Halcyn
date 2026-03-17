param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug',
  [switch]$SkipAudioSender,
  [switch]$OpenBarsStudio
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$visualizerScriptPath = Join-Path $PSScriptRoot 'launch-visualizer.ps1'
$signalRouterScriptPath = Join-Path $PSScriptRoot 'launch-signal-router.ps1'
$audioSenderScriptPath = Join-Path $PSScriptRoot 'launch-audio-sender.ps1'
$barsStudioScriptPath = Join-Path $PSScriptRoot 'launch-bars-studio.ps1'

Write-Host 'Opening the Halcyn bar-wall workbench...'
Write-Host ''
Write-Host 'This helper opens the main pieces in separate windows so you can:'
Write-Host '  1. watch the Visualizer in bar-wall mode'
Write-Host '  2. route data into the renderer from one central Signal Router'
Write-Host '  3. feed live audio into that router from the Audio Sender helper'
if ($OpenBarsStudio) {
  Write-Host '  4. fine-tune bar-wall-specific behavior in Bars Studio'
}
Write-Host ''

Start-HalcynScriptInNewWindow -ScriptPath $visualizerScriptPath -ArgumentList @(
  '-Configuration', $Configuration,
  '-Sample', 'spectrograph',
  '-Port', '8090',
  '-Title', 'Halcyn Visualizer - Bar Wall'
)

Start-Sleep -Milliseconds 400

Start-HalcynScriptInNewWindow -ScriptPath $signalRouterScriptPath

if (-not $SkipAudioSender) {
  Start-Sleep -Milliseconds 400
  Start-HalcynScriptInNewWindow -ScriptPath $audioSenderScriptPath
}

if ($OpenBarsStudio) {
  Start-Sleep -Milliseconds 400
  Start-HalcynScriptInNewWindow -ScriptPath $barsStudioScriptPath
}

Write-Host 'Windows launched.'
Write-Host ''
Write-Host 'Suggested next steps:'
Write-Host '  - Wait for the Visualizer window to appear in bar-wall mode.'
Write-Host '  - In Signal Router, enable the Bar-Wall target and choose a source mode.'
if (-not $SkipAudioSender) {
  Write-Host '  - In Audio Sender, choose a device and start capture.'
  Write-Host '  - Use the Signal Router bridge target preset and then click Send once or Start live.'
}
if ($OpenBarsStudio) {
  Write-Host '  - Use Bars Studio only when you want deeper bar-wall-specific tuning.'
}
