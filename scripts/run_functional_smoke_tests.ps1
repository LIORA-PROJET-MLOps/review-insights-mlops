param(
  [string]$ApiBase = "http://localhost:8000",
  [string]$DataBase = "http://localhost:8001",
  [string]$MonitoringBase = "http://localhost:9000",
  [string]$FrontendBase = "http://localhost:8501",
  [string]$ApiKey = "",
  [string]$FunctionalCsv = "data/sample/reviews_functional_test.csv",
  [switch]$SkipFrontend,
  [switch]$SkipPipelines
)

$ErrorActionPreference = "Stop"

function Join-Url([string]$Base, [string]$Path) {
  return "$($Base.TrimEnd('/'))/$($Path.TrimStart('/'))"
}

function Request-Json {
  param(
    [string]$Method,
    [string]$Url,
    [object]$Body = $null
  )
  $headers = @{}
  if ($ApiKey) {
    $headers["X-API-Key"] = $ApiKey
  }
  $params = @{
    Uri = $Url
    Method = $Method
    Headers = $headers
  }
  if ($null -ne $Body) {
    $params["ContentType"] = "application/json"
    $params["Body"] = ($Body | ConvertTo-Json -Depth 12)
  }
  return Invoke-RestMethod @params
}

function Assert-True {
  param(
    [bool]$Condition,
    [string]$Message
  )
  if (-not $Condition) {
    throw $Message
  }
}

Write-Host "== Review Insights+ functional smoke tests =="
Write-Host "API:        $ApiBase"
Write-Host "Data:       $DataBase"
Write-Host "Monitoring: $MonitoringBase"
Write-Host "Frontend:   $FrontendBase"

Write-Host "`n[1/10] Healthchecks"
$apiHealth = Request-Json GET (Join-Url $ApiBase "/health")
$dataHealth = Request-Json GET (Join-Url $DataBase "/health")
$monitoringHealth = Request-Json GET (Join-Url $MonitoringBase "/health")
Assert-True ($apiHealth.status -eq "ok") "API health failed."
Assert-True ($dataHealth.status -eq "ok") "Data health failed."
Assert-True ($monitoringHealth.status -in @("ok", "degraded")) "Monitoring health failed."
Write-Host "API backend: $($apiHealth.inference_backend), security: $($apiHealth.security_profile)"

Write-Host "`n[2/10] Single analysis"
$analysis = Request-Json POST (Join-Url $ApiBase "/v1/analyze") @{
  review_id = "functional_single_support"
  review_text = "customer support never answered and the refund process was slow"
  threshold = 0.34
}
Assert-True ($analysis.review_id -eq "functional_single_support") "Unexpected analysis review_id."
Assert-True ($analysis.themes_detected -contains "sav") "Expected SAV theme for support review."
Write-Host "Analysis sentiment: $($analysis.global_sentiment), themes: $($analysis.themes_detected -join ', ')"

Write-Host "`n[3/10] Functional CSV batch through API"
$rows = Import-Csv $FunctionalCsv
Assert-True ($rows.Count -ge 10) "Functional CSV should contain at least 10 rows."
$batchResults = @()
foreach ($row in $rows) {
  $text = "$($row.review_title) $($row.review_body)".Trim()
  $result = Request-Json POST (Join-Url $ApiBase "/v1/analyze") @{
    review_id = $row.review_id
    review_text = $text
    threshold = 0.34
  }
  $batchResults += $result
}
Assert-True ($batchResults.Count -eq $rows.Count) "Batch result count mismatch."
Write-Host "Batch analyzed rows: $($batchResults.Count)"

Write-Host "`n[4/10] Data service profile and evaluation"
$profile = Request-Json GET (Join-Url $DataBase "/v1/datasets/default/profile")
Assert-True ($profile.rows -ge 1) "Default dataset profile has no rows."
$evaluation = Request-Json GET (Join-Url $DataBase "/v1/evaluate/default")
Assert-True ($evaluation.summary.rows -eq 40) "Reference evaluation should contain 40 rows."
Assert-True ($null -ne $evaluation.summary.sentiment_macro_f1) "Evaluation should expose sentiment_macro_f1."
Assert-True ($null -ne $evaluation.summary.theme_f1_macro) "Evaluation should expose theme_f1_macro."
Write-Host "Evaluation: sentiment_accuracy=$($evaluation.summary.sentiment_accuracy), theme_f1=$($evaluation.summary.theme_f1_macro)"

Write-Host "`n[5/10] Human feedback loop"
$feedback = Request-Json POST (Join-Url $DataBase "/v1/feedback") @{
  review_id = "functional_single_support"
  theme = "sav"
  corrected_theme_present = 1
  corrected_sentiment = "negative"
  reviewer = "functional_smoke"
  notes = "Smoke test feedback."
  source = "script"
}
Assert-True ($feedback.status -eq "recorded") "Feedback was not recorded."
$recentFeedback = Request-Json GET (Join-Url $DataBase "/v1/feedback/recent?limit=10")
Assert-True ($recentFeedback.rows -ge 1) "Recent feedback should contain at least one record."
Write-Host "Recent feedback rows: $($recentFeedback.rows)"

Write-Host "`n[6/10] API metrics JSON"
$metrics = Request-Json GET (Join-Url $ApiBase "/metrics")
Assert-True ($metrics.total_requests -ge $rows.Count) "API metrics total_requests too low."
Assert-True ($null -ne $metrics.http_requests_total) "API metrics should expose http_requests_total."
Assert-True ($null -ne $metrics.theme_distribution) "API metrics should expose theme_distribution."
Write-Host "API requests: $($metrics.total_requests), HTTP requests: $($metrics.http_requests_total)"

Write-Host "`n[7/10] Monitoring gateway JSON and Prometheus text"
$monitoringMetrics = Request-Json GET (Join-Url $MonitoringBase "/v1/api/metrics")
Assert-True ($monitoringMetrics.total_requests -ge $rows.Count) "Monitoring gateway metrics too low."
$headers = @{}
if ($ApiKey) {
  $headers["X-API-Key"] = $ApiKey
}
$prometheus = Invoke-WebRequest -Uri (Join-Url $MonitoringBase "/metrics") -Headers $headers -UseBasicParsing
Assert-True ($prometheus.Content -like "*review_insights_requests_total*") "Prometheus text missing requests metric."
Assert-True ($prometheus.Content -like "*review_insights_http_requests_total*") "Prometheus text missing HTTP metric."
Write-Host "Prometheus metrics exposed."

Write-Host "`n[8/10] Frontend reachability"
if (-not $SkipFrontend) {
  $frontend = Invoke-WebRequest -Uri $FrontendBase -UseBasicParsing
  Assert-True ($frontend.StatusCode -eq 200) "Frontend did not return HTTP 200."
  Write-Host "Frontend HTTP 200."
} else {
  Write-Host "Skipped."
}

Write-Host "`n[9/10] Local CLI pipelines"
if (-not $SkipPipelines) {
  py -3 pipelines/prepare_annotation_batch.py $FunctionalCsv --data-root tests_runtime/functional_data --dataset-version functional_cli --output-dir tests_runtime/functional_annotation | Out-Host
  py -3 pipelines/build_model_release_report.py --output-json tests_runtime/functional_release.json --output-md tests_runtime/functional_release.md | Out-Host
  Assert-True (Test-Path "tests_runtime/functional_annotation/annotation_queue_functional_cli.csv") "Annotation queue was not generated."
  Assert-True (Test-Path "tests_runtime/functional_release.json") "Release report was not generated."
  Write-Host "CLI pipelines ok."
} else {
  Write-Host "Skipped."
}

Write-Host "`n[10/10] Summary"
Write-Host "Functional smoke tests passed."
