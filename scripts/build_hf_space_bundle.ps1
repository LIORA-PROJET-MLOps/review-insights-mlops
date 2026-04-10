$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$bundle = Join-Path $root "dist\hf_space_api_bundle"

if (Test-Path $bundle) {
    Remove-Item -LiteralPath $bundle -Recurse -Force
}

New-Item -ItemType Directory -Path $bundle | Out-Null
New-Item -ItemType Directory -Path (Join-Path $bundle "src\review_insights") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $bundle "deploy\huggingface_api_space") -Force | Out-Null

Copy-Item -LiteralPath (Join-Path $root "api_app.py") -Destination $bundle
Copy-Item -LiteralPath (Join-Path $root "requirements.txt") -Destination $bundle
Copy-Item -LiteralPath (Join-Path $root ".env.example") -Destination $bundle

Copy-Item -LiteralPath (Join-Path $root "deploy\huggingface_api_space\Dockerfile") -Destination $bundle
Copy-Item -LiteralPath (Join-Path $root "deploy\huggingface_api_space\README.md") -Destination (Join-Path $bundle "README.md")
Copy-Item -LiteralPath (Join-Path $root "deploy\huggingface_api_space\.dockerignore") -Destination (Join-Path $bundle ".dockerignore")

Copy-Item -LiteralPath (Join-Path $root "src\review_insights\__init__.py") -Destination (Join-Path $bundle "src\review_insights")
Copy-Item -LiteralPath (Join-Path $root "src\review_insights\api.py") -Destination (Join-Path $bundle "src\review_insights")
Copy-Item -LiteralPath (Join-Path $root "src\review_insights\config.py") -Destination (Join-Path $bundle "src\review_insights")
Copy-Item -LiteralPath (Join-Path $root "src\review_insights\dataset.py") -Destination (Join-Path $bundle "src\review_insights")
Copy-Item -LiteralPath (Join-Path $root "src\review_insights\engine.py") -Destination (Join-Path $bundle "src\review_insights")
Copy-Item -LiteralPath (Join-Path $root "src\review_insights\evaluation.py") -Destination (Join-Path $bundle "src\review_insights")
Copy-Item -LiteralPath (Join-Path $root "src\review_insights\model_backend.py") -Destination (Join-Path $bundle "src\review_insights")
Copy-Item -LiteralPath (Join-Path $root "src\review_insights\monitoring.py") -Destination (Join-Path $bundle "src\review_insights")
Copy-Item -LiteralPath (Join-Path $root "src\review_insights\reporting.py") -Destination (Join-Path $bundle "src\review_insights")
Copy-Item -LiteralPath (Join-Path $root "src\review_insights\schemas.py") -Destination (Join-Path $bundle "src\review_insights")
Copy-Item -LiteralPath (Join-Path $root "src\review_insights\service.py") -Destination (Join-Path $bundle "src\review_insights")
Copy-Item -LiteralPath (Join-Path $root "src\review_insights\settings.py") -Destination (Join-Path $bundle "src\review_insights")

Write-Output "HF Space bundle generated in: $bundle"
