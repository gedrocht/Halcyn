$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

function Write-ToolStatus {
  <#
    .SYNOPSIS
    Prints a consistent one-line status message for a required tool.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [Parameter(Mandatory = $true)]
    [bool]$IsAvailable,
    [string]$Details = ''
  )

  $status = if ($IsAvailable) { 'FOUND ' } else { 'MISSING' }
  if ([string]::IsNullOrWhiteSpace($Details)) {
    Write-Host ("[{0}] {1}" -f $status, $Name)
  }
  else {
    Write-Host ("[{0}] {1} - {2}" -f $status, $Name, $Details)
  }
}

function Write-InstallHint {
  <#
    .SYNOPSIS
    Prints one concise installation hint for a missing prerequisite.
  #>
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [Parameter(Mandatory = $true)]
    [bool]$IsAvailable,
    [Parameter(Mandatory = $true)]
    [string]$Hint
  )

  if (-not $IsAvailable) {
    Write-Host ("  - {0}: {1}" -f $Name, $Hint)
  }
}

$cmakeCommand = Get-Command cmake -ErrorAction SilentlyContinue
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$gitCommand = Get-Command git -ErrorAction SilentlyContinue
$ninjaPath = Get-ResolvedToolPath -ToolName 'ninja'
$doxygenPath = Get-ResolvedToolPath -ToolName 'doxygen'
$clangFormatPath = Get-ResolvedToolPath -ToolName 'clang-format'
$pythonJinja2Available = Test-PythonModuleAvailable -ModuleName 'jinja2'
$pythonTtkbootstrapAvailable = Test-PythonModuleAvailable -ModuleName 'ttkbootstrap'
$pythonMkdocsAvailable = Test-PythonModuleAvailable -ModuleName 'mkdocs'
$pythonSoundDeviceAvailable = Test-PythonModuleAvailable -ModuleName 'sounddevice'
$pythonSoundCardAvailable = Test-PythonModuleAvailable -ModuleName 'soundcard'
$visualStudioInstallation = Test-VisualStudio2022Available
$availableCompiler = Get-AvailableCompiler
$clCompilerCommand = Get-Command cl -ErrorAction SilentlyContinue
$visualStudioCompilerPath = Get-VisualStudioCompilerPath
$clangCompilerPath = Get-ResolvedToolPath -ToolName 'clang++'
$gccCompilerCommand = Get-Command g++ -ErrorAction SilentlyContinue

Write-Host 'Halcyn prerequisite report'
Write-Host '==========================='
Write-ToolStatus -Name 'cmake' -IsAvailable ($null -ne $cmakeCommand) -Details ($cmakeCommand.Source)
Write-ToolStatus -Name 'python' -IsAvailable ($null -ne $pythonCommand) -Details ($pythonCommand.Source)
Write-ToolStatus -Name 'python-jinja2' -IsAvailable $pythonJinja2Available
Write-ToolStatus -Name 'python-ttkbootstrap' -IsAvailable $pythonTtkbootstrapAvailable
Write-ToolStatus -Name 'python-mkdocs' -IsAvailable $pythonMkdocsAvailable
Write-ToolStatus -Name 'python-sounddevice' -IsAvailable $pythonSoundDeviceAvailable
Write-ToolStatus -Name 'python-soundcard' -IsAvailable $pythonSoundCardAvailable
Write-ToolStatus -Name 'git' -IsAvailable ($null -ne $gitCommand) -Details ($gitCommand.Source)
Write-ToolStatus -Name 'ninja' -IsAvailable (-not [string]::IsNullOrWhiteSpace($ninjaPath)) -Details $ninjaPath
Write-ToolStatus -Name 'Visual Studio 2022' -IsAvailable ($null -ne $visualStudioInstallation) -Details $visualStudioInstallation
Write-ToolStatus -Name 'cl.exe' -IsAvailable ($null -ne $clCompilerCommand -or $null -ne $visualStudioCompilerPath) -Details ($(if ($null -ne $clCompilerCommand) { $clCompilerCommand.Source } else { $visualStudioCompilerPath }))
Write-ToolStatus -Name 'clang++' -IsAvailable (-not [string]::IsNullOrWhiteSpace($clangCompilerPath)) -Details $clangCompilerPath
Write-ToolStatus -Name 'g++' -IsAvailable ($null -ne $gccCompilerCommand) -Details ($gccCompilerCommand.Source)
Write-ToolStatus -Name 'doxygen' -IsAvailable (-not [string]::IsNullOrWhiteSpace($doxygenPath)) -Details $doxygenPath
Write-ToolStatus -Name 'clang-format' -IsAvailable (-not [string]::IsNullOrWhiteSpace($clangFormatPath)) -Details $clangFormatPath

Write-Host ''
Write-Host 'Next step recommendation:'
if ((-not [string]::IsNullOrWhiteSpace($ninjaPath) -and $null -ne $availableCompiler) -or $null -ne $visualStudioInstallation) {
  Write-Host '  You have enough tooling to try a build. Run .\scripts\build-halcyn-app.ps1'
}
else {
  Write-Host '  Install either Ninja plus a compiler, or Visual Studio 2022 Build Tools, then rerun this script.'
}

Write-Host ''
Write-Host 'Install help for anything marked MISSING:'
Write-InstallHint -Name 'ninja' -IsAvailable (-not [string]::IsNullOrWhiteSpace($ninjaPath)) -Hint 'Install Ninja from https://ninja-build.org/ or with winget: winget install Ninja-build.Ninja'
Write-InstallHint -Name 'Visual Studio 2022 Build Tools' -IsAvailable ($null -ne $visualStudioInstallation) -Hint 'Install Build Tools from https://visualstudio.microsoft.com/downloads/ and include the Desktop development with C++ workload.'
Write-InstallHint -Name 'cl.exe' -IsAvailable ($null -ne $clCompilerCommand -or $null -ne $visualStudioCompilerPath) -Hint 'Install Visual Studio 2022 Build Tools with the Desktop development with C++ workload.'
Write-InstallHint -Name 'clang++' -IsAvailable (-not [string]::IsNullOrWhiteSpace($clangCompilerPath)) -Hint 'Optional alternative compiler. Install LLVM from https://llvm.org/ or with winget: winget install LLVM.LLVM'
Write-InstallHint -Name 'g++' -IsAvailable ($null -ne $gccCompilerCommand) -Hint 'Optional alternative compiler. Install MSYS2/MinGW if you prefer GCC on Windows.'
Write-InstallHint -Name 'doxygen' -IsAvailable (-not [string]::IsNullOrWhiteSpace($doxygenPath)) -Hint 'Needed only for generated code docs. Install from https://www.doxygen.nl/download.html or with winget: winget install DimitriVanHeesch.Doxygen'
Write-InstallHint -Name 'clang-format' -IsAvailable (-not [string]::IsNullOrWhiteSpace($clangFormatPath)) -Hint 'Needed only for the format script. Install LLVM from https://llvm.org/ or with winget: winget install LLVM.LLVM'
Write-InstallHint -Name 'python-jinja2' -IsAvailable $pythonJinja2Available -Hint 'Install with: python -m pip install jinja2'
Write-InstallHint -Name 'python-ttkbootstrap' -IsAvailable $pythonTtkbootstrapAvailable -Hint 'Needed for the native Visualizer Studio desktop UI. Install with: python -m pip install ttkbootstrap'
Write-InstallHint -Name 'python-mkdocs' -IsAvailable $pythonMkdocsAvailable -Hint 'Needed only for the hosted beginner wiki. Install with: python -m pip install mkdocs'
Write-InstallHint -Name 'python-sounddevice' -IsAvailable $pythonSoundDeviceAvailable -Hint 'Needed for microphone and line-input capture. Install with: python -m pip install sounddevice'
Write-InstallHint -Name 'python-soundcard' -IsAvailable $pythonSoundCardAvailable -Hint 'Needed for desktop output-loopback capture. Install with: python -m pip install soundcard'

if ($null -ne $visualStudioInstallation -and $null -eq $clCompilerCommand -and $null -ne $visualStudioCompilerPath) {
  Write-Host ''
  Write-Host "Note: cl.exe was found at $visualStudioCompilerPath even though it is not on PATH in this shell."
  Write-Host 'CMake can still build with the Visual Studio generator, which is the normal path for this project.'
}
