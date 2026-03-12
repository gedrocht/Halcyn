param(
  [ValidateSet('Debug', 'Release')]
  [string]$Configuration = 'Release',
  [string]$OutputDirectory = 'artifacts',
  [string]$VersionLabel = ''
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

function Get-GitValue {
  param(
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments
  )

  $git = Get-Command git -ErrorAction SilentlyContinue
  if ($null -eq $git) {
    return ''
  }

  try {
    $value = & git @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) {
      return ''
    }

    return ($value | Select-Object -First 1).ToString().Trim()
  }
  catch {
    return ''
  }
}

$projectRoot = Get-ProjectRoot
$outputRoot = Join-Path $projectRoot $OutputDirectory

& (Join-Path $PSScriptRoot 'build.ps1') -Configuration $Configuration

$executable = Get-HalcynExecutablePath -Configuration $Configuration
if (-not (Test-Path $executable)) {
  throw "The Halcyn executable was not found at $executable"
}

$resolvedVersion = $VersionLabel.Trim()
if ([string]::IsNullOrWhiteSpace($resolvedVersion)) {
  $resolvedVersion = Get-GitValue -Arguments @('describe', '--tags', '--always', '--dirty')
}

if ([string]::IsNullOrWhiteSpace($resolvedVersion)) {
  $resolvedVersion = 'snapshot'
}

$packageName = "halcyn-$resolvedVersion-win-$($Configuration.ToLowerInvariant())"
$packageDirectory = Join-Path $outputRoot $packageName
$zipPath = Join-Path $outputRoot ($packageName + '.zip')

if (Test-Path $packageDirectory) {
  Remove-Item -Recurse -Force $packageDirectory
}

if (Test-Path $zipPath) {
  Remove-Item -Force $zipPath
}

New-Item -ItemType Directory -Force -Path $packageDirectory | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $packageDirectory 'examples') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $packageDirectory 'docs') | Out-Null

Copy-Item $executable (Join-Path $packageDirectory 'halcyn_app.exe')
Copy-Item (Join-Path $projectRoot 'README.md') (Join-Path $packageDirectory 'README.md')
Copy-Item (Join-Path $projectRoot 'LICENSE') (Join-Path $packageDirectory 'LICENSE')
Copy-Item (Join-Path $projectRoot 'examples\\*') (Join-Path $packageDirectory 'examples') -Recurse
Copy-Item (Join-Path $projectRoot 'docs\\site') (Join-Path $packageDirectory 'docs\\site') -Recurse

$generatedCodeDocs = Join-Path $projectRoot 'docs\\generated\\code-reference'
if (Test-Path $generatedCodeDocs) {
  Copy-Item $generatedCodeDocs (Join-Path $packageDirectory 'docs\\code-reference') -Recurse
}

$manifest = @{
  project = 'Halcyn'
  configuration = $Configuration
  version = $resolvedVersion
  generatedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
  gitCommit = Get-GitValue -Arguments @('rev-parse', '--short', 'HEAD')
  gitBranch = Get-GitValue -Arguments @('branch', '--show-current')
  executable = 'halcyn_app.exe'
}

$manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $packageDirectory 'build-manifest.json')

Compress-Archive -Path (Join-Path $packageDirectory '*') -DestinationPath $zipPath

Write-Host "Package created at $zipPath"
