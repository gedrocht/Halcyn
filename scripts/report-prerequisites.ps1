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

$cmake = Get-Command cmake -ErrorAction SilentlyContinue
$python = Get-Command python -ErrorAction SilentlyContinue
$git = Get-Command git -ErrorAction SilentlyContinue
$ninja = Get-ResolvedToolPath -ToolName 'ninja'
$doxygen = Get-ResolvedToolPath -ToolName 'doxygen'
$clangFormat = Get-ResolvedToolPath -ToolName 'clang-format'
$pythonJinja2 = Test-PythonModuleAvailable -ModuleName 'jinja2'
$visualStudio = Test-VisualStudio2022Available
$compiler = Get-AvailableCompiler
$cl = Get-Command cl -ErrorAction SilentlyContinue
$visualStudioCl = Get-VisualStudioCompilerPath
$clang = Get-ResolvedToolPath -ToolName 'clang++'
$gcc = Get-Command g++ -ErrorAction SilentlyContinue

Write-Host 'Halcyn prerequisite report'
Write-Host '==========================='
Write-ToolStatus -Name 'cmake' -IsAvailable ($null -ne $cmake) -Details ($cmake.Source)
Write-ToolStatus -Name 'python' -IsAvailable ($null -ne $python) -Details ($python.Source)
Write-ToolStatus -Name 'python-jinja2' -IsAvailable $pythonJinja2
Write-ToolStatus -Name 'git' -IsAvailable ($null -ne $git) -Details ($git.Source)
Write-ToolStatus -Name 'ninja' -IsAvailable (-not [string]::IsNullOrWhiteSpace($ninja)) -Details $ninja
Write-ToolStatus -Name 'Visual Studio 2022' -IsAvailable ($null -ne $visualStudio) -Details $visualStudio
Write-ToolStatus -Name 'cl.exe' -IsAvailable ($null -ne $cl -or $null -ne $visualStudioCl) -Details ($(if ($null -ne $cl) { $cl.Source } else { $visualStudioCl }))
Write-ToolStatus -Name 'clang++' -IsAvailable (-not [string]::IsNullOrWhiteSpace($clang)) -Details $clang
Write-ToolStatus -Name 'g++' -IsAvailable ($null -ne $gcc) -Details ($gcc.Source)
Write-ToolStatus -Name 'doxygen' -IsAvailable (-not [string]::IsNullOrWhiteSpace($doxygen)) -Details $doxygen
Write-ToolStatus -Name 'clang-format' -IsAvailable (-not [string]::IsNullOrWhiteSpace($clangFormat)) -Details $clangFormat

Write-Host ''
Write-Host 'Next step recommendation:'
if ((-not [string]::IsNullOrWhiteSpace($ninja) -and $null -ne $compiler) -or $null -ne $visualStudio) {
  Write-Host '  You have enough tooling to try a build. Run .\scripts\build-halcyn-app.ps1'
}
else {
  Write-Host '  Install either Ninja plus a compiler, or Visual Studio 2022 Build Tools, then rerun this script.'
}

Write-Host ''
Write-Host 'Install help for anything marked MISSING:'
Write-InstallHint -Name 'ninja' -IsAvailable (-not [string]::IsNullOrWhiteSpace($ninja)) -Hint 'Install Ninja from https://ninja-build.org/ or with winget: winget install Ninja-build.Ninja'
Write-InstallHint -Name 'Visual Studio 2022 Build Tools' -IsAvailable ($null -ne $visualStudio) -Hint 'Install Build Tools from https://visualstudio.microsoft.com/downloads/ and include the Desktop development with C++ workload.'
Write-InstallHint -Name 'cl.exe' -IsAvailable ($null -ne $cl -or $null -ne $visualStudioCl) -Hint 'Install Visual Studio 2022 Build Tools with the Desktop development with C++ workload.'
Write-InstallHint -Name 'clang++' -IsAvailable (-not [string]::IsNullOrWhiteSpace($clang)) -Hint 'Optional alternative compiler. Install LLVM from https://llvm.org/ or with winget: winget install LLVM.LLVM'
Write-InstallHint -Name 'g++' -IsAvailable ($null -ne $gcc) -Hint 'Optional alternative compiler. Install MSYS2/MinGW if you prefer GCC on Windows.'
Write-InstallHint -Name 'doxygen' -IsAvailable (-not [string]::IsNullOrWhiteSpace($doxygen)) -Hint 'Needed only for generated code docs. Install from https://www.doxygen.nl/download.html or with winget: winget install DimitriVanHeesch.Doxygen'
Write-InstallHint -Name 'clang-format' -IsAvailable (-not [string]::IsNullOrWhiteSpace($clangFormat)) -Hint 'Needed only for the format script. Install LLVM from https://llvm.org/ or with winget: winget install LLVM.LLVM'
Write-InstallHint -Name 'python-jinja2' -IsAvailable $pythonJinja2 -Hint 'Install with: python -m pip install jinja2'

if ($null -ne $visualStudio -and $null -eq $cl -and $null -ne $visualStudioCl) {
  Write-Host ''
  Write-Host "Note: cl.exe was found at $visualStudioCl even though it is not on PATH in this shell."
  Write-Host 'CMake can still build with the Visual Studio generator, which is the normal path for this project.'
}
