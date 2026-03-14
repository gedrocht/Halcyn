$ErrorActionPreference = 'Stop'

$clangFormat = Get-Command clang-format -ErrorAction SilentlyContinue
if ($null -eq $clangFormat) {
  throw 'clang-format is not installed or not on PATH. Install LLVM/clang-format, then rerun this script.'
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$files = Get-ChildItem -Path $projectRoot -Recurse -Include *.cpp,*.hpp
foreach ($file in $files) {
  & clang-format --dry-run --Werror $file.FullName
  if ($LASTEXITCODE -ne 0) {
    throw "clang-format verification failed for $($file.FullName)."
  }
}

Write-Host 'Formatting verification completed successfully.'
