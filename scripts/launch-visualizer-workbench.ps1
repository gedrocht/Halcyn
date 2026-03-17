param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug'
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$visualizerScriptPath = Join-Path $PSScriptRoot 'launch-halcyn-app.ps1'
$controlCenterScriptPath = Join-Path $PSScriptRoot 'launch-browser-control-center.ps1'
$visualizerStudioScriptPath = Join-Path $PSScriptRoot 'launch-visualizer-studio.ps1'

Write-Host 'Opening the Halcyn Visualizer workbench...'
Write-Host ''
Write-Host 'This helper opens the main pieces in separate windows so you can:'
Write-Host '  1. watch the unified Visualizer renderer'
Write-Host '  2. tune scene and source settings in Visualizer Studio'
Write-Host '  3. inspect shared logs in the browser Control Center Activity Monitor'

Start-HalcynScriptInNewWindow -ScriptPath $visualizerScriptPath -ArgumentList @(
  '-Configuration', $Configuration,
  '-Sample', 'bar-wall'
)
Start-HalcynScriptInNewWindow -ScriptPath $controlCenterScriptPath
Start-HalcynScriptInNewWindow -ScriptPath $visualizerStudioScriptPath
