$ErrorActionPreference = 'Stop'

function Assert-LastExitCode {
  <#
    .SYNOPSIS
    Stops the current script if the previous native command failed.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [string]$StepName
  )

  if ($LASTEXITCODE -ne 0) {
    throw "$StepName failed with exit code $LASTEXITCODE."
  }
}

function Test-HttpSuccess {
  <#
    .SYNOPSIS
    Returns whether an HTTP GET request succeeds with a 2xx status code.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [string]$RequestUrl,
    [int]$TimeoutSeconds = 2
  )

  try {
    $httpResponse = Invoke-WebRequest -Uri $RequestUrl -UseBasicParsing -TimeoutSec $TimeoutSeconds
    return $httpResponse.StatusCode -ge 200 -and $httpResponse.StatusCode -lt 300
  }
  catch {
    return $false
  }
}

function Get-ControlCenterCompatibility {
  <#
    .SYNOPSIS
    Checks whether a Control Center server is already available on the requested host and port.
  #>
  param(
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 9001
  )

  $baseUrl = "http://$BindHost`:$Port"
  $summaryUrl = "$baseUrl/api/system/summary"
  $sceneStudioCatalogUrl = "$baseUrl/api/scene-studio/catalog"

  $summaryAvailable = Test-HttpSuccess -RequestUrl $summaryUrl
  $sceneStudioAvailable = $summaryAvailable -and (Test-HttpSuccess -RequestUrl $sceneStudioCatalogUrl)

  return @{
    BaseUrl = $baseUrl
    SummaryAvailable = $summaryAvailable
    SceneStudioAvailable = $sceneStudioAvailable
  }
}

function Start-BrowserWhenReady {
  <#
    .SYNOPSIS
    Opens a browser window only after a URL begins returning a 2xx response.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [Alias('RequestUrl')]
    [string]$Url,
    [int]$TimeoutSeconds = 15
  )

  Start-Job -ScriptBlock {
    param($JobUrl, $JobTimeoutSeconds)

    $deadline = (Get-Date).AddSeconds($JobTimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
      try {
        $response = Invoke-WebRequest -Uri $JobUrl -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
          Start-Process $JobUrl
          break
        }
      }
      catch {
        # Keep polling until the server is ready or the timeout expires.
      }

      Start-Sleep -Milliseconds 250
    }
  } -ArgumentList $Url, $TimeoutSeconds | Out-Null
}

function Get-PreferredPowerShellExecutable {
  <#
    .SYNOPSIS
    Returns the best available PowerShell executable for launching helper windows.

    .DESCRIPTION
    Some workflow helpers open multiple scripts in separate console windows so a
    beginner can see "renderer", "browser dashboard", and "Visualizer Studio"
    as distinct moving parts. This helper prefers PowerShell 7 when it is
    available, then falls back to Windows PowerShell.
  #>

  $powerShellSevenCommand = Get-Command pwsh -ErrorAction SilentlyContinue
  if ($null -ne $powerShellSevenCommand) {
    return $powerShellSevenCommand.Source
  }

  $windowsPowerShellCommand = Get-Command powershell -ErrorAction SilentlyContinue
  if ($null -ne $windowsPowerShellCommand) {
    return $windowsPowerShellCommand.Source
  }

  throw 'Neither pwsh nor powershell is available on PATH.'
}

function Start-HalcynScriptInNewWindow {
  <#
    .SYNOPSIS
    Launches one repository script in a separate PowerShell window.

    .DESCRIPTION
    This is intentionally small and explicit. It helps "workbench" scripts open
    related tools side by side without forcing the user to remember several long
    commands. The child script still runs normally with its own arguments and
    current working directory set to the repository root.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,
    [string[]]$ArgumentList = @()
  )

  $powerShellExecutable = Get-PreferredPowerShellExecutable
  $projectRoot = Get-ProjectRoot

  Start-Process -FilePath $powerShellExecutable -ArgumentList (
    @(
      '-ExecutionPolicy', 'Bypass',
      '-NoExit',
      '-File', $ScriptPath
    ) + $ArgumentList
  ) -WorkingDirectory $projectRoot
}

function Get-ProjectRoot {
  <#
    .SYNOPSIS
    Returns the absolute path to the repository root.
  #>
  return Resolve-FilesystemPath -Path (Join-Path $PSScriptRoot '..')
}

function Get-HalcynActivityLogPath {
  <#
    .SYNOPSIS
    Returns the shared cross-process activity journal path.
  #>

  return Join-Path (Get-ProjectRoot) 'artifacts\runtime-activity\halcyn-activity.jsonl'
}

function Initialize-HalcynActivityLogEnvironment {
  <#
    .SYNOPSIS
    Ensures every launched Halcyn process points at the same shared activity journal.

    .DESCRIPTION
    The browser Activity Monitor reads one append-only JSON-lines file. Every
    app launcher calls this helper before starting Python or C++ processes so
    the Visualizer, Control Center, and Visualizer Studio all write to
    that same file.
  #>

  $activityLogPath = Get-HalcynActivityLogPath
  $activityLogDirectory = Split-Path -Parent $activityLogPath
  New-Item -ItemType Directory -Force -Path $activityLogDirectory | Out-Null
  $env:HALCYN_ACTIVITY_LOG_PATH = $activityLogPath
  return $activityLogPath
}

function Resolve-FilesystemPath {
  <#
    .SYNOPSIS
    Resolves a path to a plain filesystem path without the PowerShell provider prefix.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path
  )

  $resolvedPath = Resolve-Path -Path $Path
  if ($resolvedPath -is [System.Array]) {
    $resolvedPath = $resolvedPath | Select-Object -First 1
  }

  return $resolvedPath.ProviderPath
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

  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if ($null -eq $pythonCommand) {
    return $false
  }

  try {
    & $pythonCommand.Source -c "import $ModuleName" 1> $null 2> $null
    return $LASTEXITCODE -eq 0
  }
  catch {
    return $false
  }
}

function Get-WingetInstalledBinaryPath {
  <#
    .SYNOPSIS
    Returns the first binary match from a known WinGet package installation.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [string]$PackagePattern,
    [Parameter(Mandatory = $true)]
    [string]$BinaryName
  )

  if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    return $null
  }

  $wingetRoot = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
  if (-not (Test-Path $wingetRoot)) {
    return $null
  }

  $packages = Get-ChildItem -Path $wingetRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like $PackagePattern } |
    Sort-Object Name -Descending

  foreach ($package in $packages) {
    $candidate = Get-ChildItem -Path $package.FullName -Recurse -File -Filter $BinaryName -ErrorAction SilentlyContinue |
      Select-Object -First 1
    if ($null -ne $candidate) {
      return $candidate.FullName
    }
  }

  return $null
}

function Get-ResolvedToolPath {
  <#
    .SYNOPSIS
    Finds a tool either on PATH or in common Windows install locations.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [string]$ToolName
  )

  $command = Get-Command $ToolName -ErrorAction SilentlyContinue
  if ($null -ne $command) {
    return $command.Source
  }

  $candidatePaths = switch ($ToolName) {
    'ninja' { @('C:\ProgramData\Chocolatey\bin\ninja.exe') }
    'clang-format' { @('C:\Program Files\LLVM\bin\clang-format.exe') }
    'doxygen' { @('C:\Program Files\doxygen\bin\doxygen.exe', 'C:\Strawberry\c\bin\doxygen.exe') }
    default { @() }
  }

  foreach ($candidatePath in $candidatePaths) {
    if (Test-Path $candidatePath) {
      return $candidatePath
    }
  }

  if ($ToolName -in @('clang-format', 'clang++')) {
    $visualStudio = Test-VisualStudio2022Available
    if ($null -ne $visualStudio) {
      $installationRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $visualStudio))
      $vsLlvmCandidates = @(
        (Join-Path -Path $installationRoot -ChildPath ("VC\Tools\Llvm\bin\{0}.exe" -f $ToolName))
        (Join-Path -Path $installationRoot -ChildPath ("VC\Tools\Llvm\x64\bin\{0}.exe" -f $ToolName))
        (Join-Path -Path $installationRoot -ChildPath ("VC\Tools\Llvm\ARM64\bin\{0}.exe" -f $ToolName))
      )

      foreach ($candidatePath in $vsLlvmCandidates) {
        if (Test-Path $candidatePath) {
          return $candidatePath
        }
      }
    }
  }

  $wingetMatch = switch ($ToolName) {
    'ninja' { Get-WingetInstalledBinaryPath -PackagePattern 'Ninja-build.Ninja*' -BinaryName 'ninja.exe' }
    'clang-format' { Get-WingetInstalledBinaryPath -PackagePattern 'LLVM.LLVM*' -BinaryName 'clang-format.exe' }
    'clang++' { Get-WingetInstalledBinaryPath -PackagePattern 'LLVM.LLVM*' -BinaryName 'clang++.exe' }
    'doxygen' { Get-WingetInstalledBinaryPath -PackagePattern 'DimitriVanHeesch.Doxygen*' -BinaryName 'doxygen.exe' }
    default { $null }
  }

  if (-not [string]::IsNullOrWhiteSpace($wingetMatch)) {
    return $wingetMatch
  }

  return $null
}

function Get-HalcynCppFiles {
  <#
    .SYNOPSIS
    Returns the tracked C++ source files that belong to this repository.
  #>
  $projectRoot = Get-ProjectRoot
  $gitCommand = Get-Command git -ErrorAction SilentlyContinue

  if ($null -ne $gitCommand) {
    Push-Location $projectRoot
    try {
      $trackedFiles = & $gitCommand.Source ls-files '*.cpp' '*.hpp'
      if ($LASTEXITCODE -eq 0) {
        return @(
          $trackedFiles |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            ForEach-Object { Join-Path $projectRoot $_ } |
            Where-Object { Test-Path $_ }
        )
      }
    }
    finally {
      Pop-Location
    }
  }

  $sourceRoots = @(
    Join-Path $projectRoot 'src',
    Join-Path $projectRoot 'tests'
  ) | Where-Object { Test-Path $_ }

  return @(
    Get-ChildItem -Path $sourceRoots -Recurse -File -Include *.cpp, *.hpp |
      Select-Object -ExpandProperty FullName
  )
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
  $visualStudioCompilerCommand = Get-Command cl -ErrorAction SilentlyContinue
  if ($null -ne $visualStudioCompilerCommand) {
    return @{ Name = 'cl.exe'; Source = $visualStudioCompilerCommand.Source }
  }

  $clang = Get-Command clang++ -ErrorAction SilentlyContinue
  if ($null -ne $clang) {
    return @{ Name = 'clang++'; Source = $clang.Source }
  }

  $gccCompilerCommand = Get-Command g++ -ErrorAction SilentlyContinue
  if ($null -ne $gccCompilerCommand) {
    return @{ Name = 'g++'; Source = $gccCompilerCommand.Source }
  }

  return $null
}

function Get-VisualStudioCompilerPath {
  <#
    .SYNOPSIS
    Returns the newest installed MSVC cl.exe path if Visual Studio 2022 is installed.
  #>
  $visualStudio = Test-VisualStudio2022Available
  if ($null -eq $visualStudio) {
    return $null
  }

  $installationRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $visualStudio))
  $compilerRoots = Get-ChildItem -Path (Join-Path $installationRoot 'VC\Tools\MSVC') -Directory -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending

  foreach ($compilerRoot in $compilerRoots) {
    $candidate = Join-Path $compilerRoot.FullName 'bin\Hostx64\x64\cl.exe'
    if (Test-Path $candidate) {
      return $candidate
    }
  }

  return $null
}

function Test-VisualStudio2022Available {
  <#
    .SYNOPSIS
    Detects whether a Visual Studio 2022 installation is present in one of the common locations.
  #>
  $vswherePath = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
  if (Test-Path $vswherePath) {
    try {
      $installationPath = & $vswherePath -latest -products * -requires Microsoft.VisualStudio.Workload.NativeDesktop -property installationPath
      if (-not [string]::IsNullOrWhiteSpace($installationPath)) {
        $trimmedPath = $installationPath.Trim()
        $devCmdCandidate = Join-Path $trimmedPath 'Common7\Tools\VsDevCmd.bat'
        if (Test-Path $devCmdCandidate) {
          return $devCmdCandidate
        }

        return $trimmedPath
      }
    }
    catch {
      # Fall back to the common install paths below if vswhere is unavailable or errors.
    }
  }

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
  if (-not [string]::IsNullOrWhiteSpace($env:HALCYN_CMAKE_GENERATOR)) {
    return $env:HALCYN_CMAKE_GENERATOR
  }

  $ninja = Get-ResolvedToolPath -ToolName 'ninja'
  $compiler = Get-AvailableCompiler
  if (-not [string]::IsNullOrWhiteSpace($ninja) -and $null -ne $compiler) {
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

Run .\scripts\report-prerequisites.ps1 for a fuller prerequisite report.
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
  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue

  if (-not (Test-PythonModuleAvailable -ModuleName 'jinja2')) {
    throw @"
Python module 'jinja2' is required during CMake configure because Halcyn generates the OpenGL glad loader.

Install it with:
  python -m pip install jinja2
"@
  }

  New-Item -ItemType Directory -Force -Path $buildDirectory | Out-Null

  $configureArgs = @(
    '-Wno-dev',
    '-Wno-deprecated',
    '-S', $projectRoot,
    '-B', $buildDirectory,
    '-G', $generator,
    '-D', 'HALCYN_ENABLE_TESTS=ON'
  )

  if ($null -ne $pythonCommand) {
    $configureArgs += @('-D', "Python_EXECUTABLE=$($pythonCommand.Source)")
  }

  if ($generator -eq 'Ninja') {
    $configureArgs += @('-D', "CMAKE_BUILD_TYPE=$Configuration")
    $ninja = Get-ResolvedToolPath -ToolName 'ninja'
    if (-not [string]::IsNullOrWhiteSpace($ninja)) {
      $configureArgs += @('-D', "CMAKE_MAKE_PROGRAM=$ninja")
    }
  }

  & cmake @configureArgs
  Assert-LastExitCode -StepName 'CMake configure'
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
  Assert-LastExitCode -StepName 'CMake build'
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

function Get-HalcynSpectrographExecutablePath {
  <#
    .SYNOPSIS
    Backward-compatible alias for the older spectrograph executable helper.

    .DESCRIPTION
    Halcyn now ships one unified Visualizer executable that can start with
    either the classic preset scenes or the bar-wall scene family. The older
    helper name remains available so legacy scripts do not break, but it now
    resolves to the singular Visualizer executable path.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration
  )

  return Get-HalcynExecutablePath -Configuration $Configuration
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
  Assert-LastExitCode -StepName 'CTest'
}
