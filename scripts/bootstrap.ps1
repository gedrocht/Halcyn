$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

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

$cmake = Get-Command cmake -ErrorAction SilentlyContinue
$python = Get-Command python -ErrorAction SilentlyContinue
$git = Get-Command git -ErrorAction SilentlyContinue
$ninja = Get-Command ninja -ErrorAction SilentlyContinue
$doxygen = Get-Command doxygen -ErrorAction SilentlyContinue
$clangFormat = Get-Command clang-format -ErrorAction SilentlyContinue
$pythonJinja2 = Test-PythonModuleAvailable -ModuleName 'jinja2'
$visualStudio = Test-VisualStudio2022Available
$compiler = Get-AvailableCompiler
$cl = Get-Command cl -ErrorAction SilentlyContinue
$clang = Get-Command clang++ -ErrorAction SilentlyContinue
$gcc = Get-Command g++ -ErrorAction SilentlyContinue

Write-Host 'Halcyn prerequisite report'
Write-Host '==========================='
Write-ToolStatus -Name 'cmake' -IsAvailable ($null -ne $cmake) -Details ($cmake.Source)
Write-ToolStatus -Name 'python' -IsAvailable ($null -ne $python) -Details ($python.Source)
Write-ToolStatus -Name 'python-jinja2' -IsAvailable $pythonJinja2
Write-ToolStatus -Name 'git' -IsAvailable ($null -ne $git) -Details ($git.Source)
Write-ToolStatus -Name 'ninja' -IsAvailable ($null -ne $ninja) -Details ($ninja.Source)
Write-ToolStatus -Name 'Visual Studio 2022' -IsAvailable ($null -ne $visualStudio) -Details $visualStudio
Write-ToolStatus -Name 'cl.exe' -IsAvailable ($null -ne $cl) -Details ($cl.Source)
Write-ToolStatus -Name 'clang++' -IsAvailable ($null -ne $clang) -Details ($clang.Source)
Write-ToolStatus -Name 'g++' -IsAvailable ($null -ne $gcc) -Details ($gcc.Source)
Write-ToolStatus -Name 'doxygen' -IsAvailable ($null -ne $doxygen) -Details ($doxygen.Source)
Write-ToolStatus -Name 'clang-format' -IsAvailable ($null -ne $clangFormat) -Details ($clangFormat.Source)

Write-Host ''
Write-Host 'Next step recommendation:'
if (($null -ne $ninja -and $null -ne $compiler) -or $null -ne $visualStudio) {
  Write-Host '  You have enough tooling to try a build. Run .\scripts\build.ps1'
}
else {
  Write-Host '  Install either Ninja plus a compiler, or Visual Studio 2022 Build Tools, then rerun this script.'
}
