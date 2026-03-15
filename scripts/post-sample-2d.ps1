param(
  [string]$ApiHost = '127.0.0.1',
  [int]$Port = 8080
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

& (Join-Path $PSScriptRoot 'post-scene.ps1') `
  -SceneFile (Join-Path (Get-ProjectRoot) 'examples/scene_2d_triangle.json') `
  -ApiHost $ApiHost `
  -Port $Port
