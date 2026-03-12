$ErrorActionPreference = 'Stop'

function Get-ProjectRoot {
  <#
    .SYNOPSIS
    Returns the absolute path to the repository root.
  #>
  return (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

function Test-PythonModuleAvailable {
  <#
    .SYNOPSIS
    Returns whether a named Python module can be imported successfully.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [string]$ModuleName
  )

  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($null -eq $python) {
    return $false
  }

  & python -c "import $ModuleName" *> $null
  return $LASTEXITCODE -eq 0
}

function Get-BuildDirectory {
  <#
    .SYNOPSIS
    Returns the build directory used for the selected configuration.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration
  )

  return Join-Path (Get-ProjectRoot) ("build/" + $Configuration.ToLowerInvariant())
}

function Get-AvailableCompiler {
  <#
    .SYNOPSIS
    Returns the first supported C++ compiler found on PATH.
  #>
  $cl = Get-Command cl -ErrorAction SilentlyContinue
  if ($null -ne $cl) {
    return @{ Name = 'cl.exe'; Source = $cl.Source }
  }

  $clang = Get-Command clang++ -ErrorAction SilentlyContinue
  if ($null -ne $clang) {
    return @{ Name = 'clang++'; Source = $clang.Source }
  }

  $gcc = Get-Command g++ -ErrorAction SilentlyContinue
  if ($null -ne $gcc) {
    return @{ Name = 'g++'; Source = $gcc.Source }
  }

  return $null
}

function Test-VisualStudio2022Available {
  <#
    .SYNOPSIS
    Detects whether a Visual Studio 2022 installation is present in one of the common locations.
  #>
  $candidatePaths = @(
    'C:\Program Files\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat',
    'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat',
    'C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\Tools\VsDevCmd.bat',
    'C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\Tools\VsDevCmd.bat'
  )

  return $candidatePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
}

function Get-PreferredGenerator {
  <#
    .SYNOPSIS
    Chooses the best available CMake generator for this machine.
  #>
  $ninja = Get-Command ninja -ErrorAction SilentlyContinue
  $compiler = Get-AvailableCompiler
  if ($null -ne $ninja -and $null -ne $compiler) {
    return 'Ninja'
  }

  $visualStudio = Test-VisualStudio2022Available
  if ($null -ne $visualStudio) {
    return 'Visual Studio 17 2022'
  }

  throw @"
No supported C++ toolchain was detected.

Halcyn can build with either:
  - Ninja + a C++ compiler on PATH
  - Visual Studio 2022 Build Tools or Visual Studio 2022

Run .\scripts\bootstrap.ps1 for a fuller prerequisite report.
"@
}

function Invoke-HalcynConfigure {
  <#
    .SYNOPSIS
    Configures the project with CMake using the best available generator.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration
  )

  $projectRoot = Get-ProjectRoot
  $buildDirectory = Get-BuildDirectory -Configuration $Configuration
  $generator = Get-PreferredGenerator

  if (-not (Test-PythonModuleAvailable -ModuleName 'jinja2')) {
    throw @"
Python module 'jinja2' is required during CMake configure because Halcyn generates the OpenGL glad loader.

Install it with:
  python -m pip install jinja2
"@
  }

  New-Item -ItemType Directory -Force -Path $buildDirectory | Out-Null

  $configureArgs = @(
    '-S', $projectRoot,
    '-B', $buildDirectory,
    '-G', $generator,
    '-D', 'HALCYN_ENABLE_TESTS=ON'
  )

  if ($generator -eq 'Ninja') {
    $configureArgs += @('-D', "CMAKE_BUILD_TYPE=$Configuration")
  }

  & cmake @configureArgs
}

function Invoke-HalcynBuild {
  <#
    .SYNOPSIS
    Builds the configured Halcyn targets.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration
  )

  $buildDirectory = Get-BuildDirectory -Configuration $Configuration
  $generator = Get-PreferredGenerator
  $buildArgs = @('--build', $buildDirectory)

  if ($generator -eq 'Visual Studio 17 2022') {
    $buildArgs += @('--config', $Configuration)
  }

  & cmake @buildArgs
}

function Get-HalcynExecutablePath {
  <#
    .SYNOPSIS
    Returns the expected path to the built Halcyn executable.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration
  )

  $buildDirectory = Get-BuildDirectory -Configuration $Configuration
  $generator = Get-PreferredGenerator
  if ($generator -eq 'Visual Studio 17 2022') {
    return Join-Path $buildDirectory "$Configuration/halcyn_app.exe"
  }

  return Join-Path $buildDirectory 'halcyn_app.exe'
}

function Invoke-HalcynCtest {
  <#
    .SYNOPSIS
    Runs the project test suite through CTest.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration
  )

  $buildDirectory = Get-BuildDirectory -Configuration $Configuration
  $generator = Get-PreferredGenerator
  $testArgs = @('--test-dir', $buildDirectory, '--output-on-failure')

  if ($generator -eq 'Visual Studio 17 2022') {
    $testArgs += @('-C', $Configuration)
  }

  & ctest @testArgs
}
