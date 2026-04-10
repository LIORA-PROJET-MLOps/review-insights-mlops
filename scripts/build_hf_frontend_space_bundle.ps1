$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$bundle = Join-Path $root "dist\hf_space_frontend_bundle"

if (Test-Path $bundle) {
    Remove-Item -LiteralPath $bundle -Recurse -Force
}

New-Item -ItemType Directory -Path $bundle | Out-Null
New-Item -ItemType Directory -Path (Join-Path $bundle "assets") -Force | Out-Null

Copy-Item -LiteralPath (Join-Path $root "site\index.html") -Destination $bundle
Copy-Item -LiteralPath (Join-Path $root "site\styles.css") -Destination $bundle
Copy-Item -LiteralPath (Join-Path $root "site\script.js") -Destination $bundle
Copy-Item -LiteralPath (Join-Path $root "site\demo-api.html") -Destination $bundle
Copy-Item -LiteralPath (Join-Path $root "site\app-online.html") -Destination $bundle
Copy-Item -LiteralPath (Join-Path $root "site\app.css") -Destination $bundle
Copy-Item -LiteralPath (Join-Path $root "site\app.js") -Destination $bundle

Copy-Item -LiteralPath (Join-Path $root "deploy\huggingface_frontend_space\Dockerfile") -Destination $bundle
Copy-Item -LiteralPath (Join-Path $root "deploy\huggingface_frontend_space\README.md") -Destination (Join-Path $bundle "README.md")
Copy-Item -LiteralPath (Join-Path $root "deploy\huggingface_frontend_space\.dockerignore") -Destination (Join-Path $bundle ".dockerignore")

Copy-Item -LiteralPath (Join-Path $root "site\assets\*") -Destination (Join-Path $bundle "assets") -Recurse -Force

Write-Output "HF Frontend Space bundle generated in: $bundle"
