param(
  [string]$ApiBase = "http://localhost:8000",
  [string[]]$AllowedWarnings = @()
)

$ErrorActionPreference = "Stop"
$healthUrl = "$($ApiBase.TrimEnd('/'))/health"
$health = Invoke-RestMethod -Uri $healthUrl -Method Get

Write-Host "Security profile: $($health.security_profile)"
Write-Host "Protected endpoints: $($health.protected_endpoints)"
Write-Host "Warnings: $($health.security_warnings -join ', ')"

if (-not $health.protected_endpoints) {
  Write-Error "Protected endpoints are disabled. Configure REQUIRE_API_KEY=true and API_KEY."
  exit 2
}

$unexpectedWarnings = @($health.security_warnings | Where-Object { $AllowedWarnings -notcontains $_ })
if ($unexpectedWarnings.Count -gt 0) {
  Write-Error "Unexpected security warnings: $($unexpectedWarnings -join ', ')"
  exit 3
}

if ($health.security_profile -eq "needs_hardening") {
  Write-Error "API reports needs_hardening."
  exit 4
}

Write-Host "Staging security check passed."
