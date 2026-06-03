param(
    [Parameter(Mandatory = $true)]
    [string]$Url,

    [string]$Name = "storage",

    [switch]$Default
)

$ErrorActionPreference = "Stop"

dvc remote add --force $Name $Url

if ($Default) {
    dvc remote default $Name
}

Write-Host "DVC remote '$Name' configured at '$Url'."
Write-Host "Store credentials only with 'dvc remote modify --local' so they remain outside Git."
