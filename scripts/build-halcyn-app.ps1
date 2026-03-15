param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Debug',
  [switch]$Clean
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$buildDirectory = Get-BuildDirectory -Configuration $Configuration
if ($Clean -and (Test-Path $buildDirectory)) {
  Remove-Item -Recurse -Force $buildDirectory
}

Write-Host "Configuring Halcyn ($Configuration)..."
Invoke-HalcynConfigure -Configuration $Configuration

Write-Host "Building Halcyn ($Configuration)..."
Invoke-HalcynBuild -Configuration $Configuration

Write-Host 'Build completed successfully.'
