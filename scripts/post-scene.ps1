param(
  [Parameter(Mandatory = $true)]
  [string]$SceneFile,
  [string]$ApiHost = '127.0.0.1',
  [int]$Port = 8080
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'common.ps1')

$scenePath = Resolve-FilesystemPath -Path $SceneFile
$body = Get-Content -Raw -Path $scenePath
$uri = "http://$ApiHost`:$Port/api/v1/scene"

Write-Host "Posting $scenePath to $uri"

try {
  $response = Invoke-RestMethod -Method Post -Uri $uri -ContentType 'application/json' -Body $body
  $response | ConvertTo-Json -Depth 10
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
