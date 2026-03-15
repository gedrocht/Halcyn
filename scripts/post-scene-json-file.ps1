param(
  [Parameter(Mandatory = $true)]
  [string]$SceneFile,
  [string]$ApiHost = '127.0.0.1',
  [int]$Port = 8080
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'shared-script-helpers.ps1')

$scenePath = Resolve-FilesystemPath -Path $SceneFile
$sceneJson = Get-Content -Raw -Path $scenePath
$requestUri = "http://$ApiHost`:$Port/api/v1/scene"

Write-Host "Posting $scenePath to $requestUri"

try {
  $httpResponse = Invoke-RestMethod -Method Post -Uri $requestUri -ContentType 'application/json' -Body $sceneJson
  $httpResponse | ConvertTo-Json -Depth 10
}
catch {
  if ($_.Exception.Response -and $_.Exception.Response.GetResponseStream) {
    $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
    $reader.BaseStream.Position = 0
    $reader.DiscardBufferedData()
    Write-Host $reader.ReadToEnd()
  }
  throw
}
