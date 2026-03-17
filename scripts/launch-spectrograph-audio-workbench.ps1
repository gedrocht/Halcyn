param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug',
  [switch]$SkipAudioSourcePanel,
  [switch]$OpenBarsStudio
)

$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'launch-bars-workbench.ps1') `
  -Configuration $Configuration `
  -SkipAudioSender:$SkipAudioSourcePanel `
  -OpenBarsStudio:$OpenBarsStudio
