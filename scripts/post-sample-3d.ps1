param(
  [string]$Host = '127.0.0.1',
  [int]$Port = 8080
)

$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'post-scene.ps1') `
  -SceneFile (Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'examples/scene_3d_tetrahedron.json') `
  -Host $Host `
  -Port $Port
