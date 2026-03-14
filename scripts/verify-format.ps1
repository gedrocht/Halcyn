$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

$clangFormat = Get-ResolvedToolPath -ToolName 'clang-format'
if ([string]::IsNullOrWhiteSpace($clangFormat)) {
  throw 'clang-format is not installed. Install LLVM/clang-format, then rerun this script.'
}

$files = Get-HalcynCppFiles
foreach ($file in $files) {
  & $clangFormat --dry-run --Werror $file
  if ($LASTEXITCODE -ne 0) {
    throw "clang-format verification failed for $file."
  }
}

Write-Host 'Formatting verification completed successfully.'
