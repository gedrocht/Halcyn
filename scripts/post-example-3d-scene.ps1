param(
  [string]$ApiHost = '127.0.0.1',
  [int]$Port = 8080
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

& (Join-Path $PSScriptRoot 'post-scene-json-file.ps1') `
  -SceneFile (Join-Path (Get-ProjectRoot) 'examples/scene_3d_tetrahedron.json') `
  -ApiHost $ApiHost `
  -Port $Port
