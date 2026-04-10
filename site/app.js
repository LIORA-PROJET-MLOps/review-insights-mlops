const DEFAULT_API_BASE = "https://francescogiraldi-review-insights-api.hf.space";

const SAMPLE_REVIEWS = {
  delivery: "the order arrived three days late and the tracking updates were unreliable",
  support: "customer support never answered and the refund process was slow",
  mixed: "great product quality but delivery was delayed and support was hard to reach",
};

const state = {
  batchRows: [],
  batchResults: [],
};

function qs(id) {
  return document.getElementById(id);
}

function getApiBase() {
  return qs("apiBase").value.trim().replace(/\/$/, "") || DEFAULT_API_BASE;
}

function getHeaders() {
  const headers = { "Content-Type": "application/json" };
  const apiKey = qs("apiKey").value.trim();
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  return headers;
}

function toJsonBlock(nodeId, payload) {
  qs(nodeId).textContent = JSON.stringify(payload, null, 2);
}

function card(label, value) {
  return `<article class="stat-card"><strong>${value}</strong><span>${label}</span></article>`;
}

function pill(label, variant = "neutral") {
  return `<span class="pill pill-${variant}">${label}</span>`;
}

async function callApi(path, options = {}) {
  const response = await fetch(`${getApiBase()}${path}`, {
    ...options,
    headers: {
      ...getHeaders(),
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }

  return response.json();
}

async function loadHealth() {
  const payload = await callApi("/health", { method: "GET", headers: {} });
  qs("healthStats").innerHTML = [
    card("Statut", payload.status),
    card("Environnement", payload.environment),
    card("Backend", payload.inference_backend),
    card("Source modele", payload.model_source),
    card("Manifest", payload.models_manifest_present ? "Present" : "Absent"),
  ].join("");
  toJsonBlock("healthJson", payload);
}

async function loadMetrics() {
  const payload = await callApi("/metrics", { method: "GET", headers: {} });
  qs("metricsStats").innerHTML = [
    card("Requetes", payload.total_requests),
    card("Human review", payload.human_review_requests),
    card("Taux review humaine", payload.human_review_rate),
  ].join("");

  const sentiment = Object.entries(payload.sentiment_distribution || {}).map(([key, value]) =>
    `<div class="chip"><strong>${key}</strong><div>${value}</div></div>`
  );
  const themes = Object.entries(payload.theme_distribution || {}).map(([key, value]) =>
    `<div class="chip"><strong>${key}</strong><div>${value}</div></div>`
  );
  qs("metricDistributions").innerHTML = [...sentiment, ...themes].join("");
  toJsonBlock("metricsJson", payload);
}

function renderAnalyze(payload) {
  const sentimentVariant =
    payload.global_sentiment === "positive"
      ? "positive"
      : payload.global_sentiment === "negative"
        ? "negative"
        : "neutral";

  qs("resultCards").innerHTML = [
    `<article class="result-card"><strong>${payload.global_sentiment}</strong><span>Sentiment global</span></article>`,
    `<article class="result-card"><strong>${payload.score_global}</strong><span>Score global</span></article>`,
    `<article class="result-card"><strong>${payload.needs_human_review ? "Oui" : "Non"}</strong><span>Human review</span></article>`,
  ].join("");

  const themes = payload.themes_detected.length
    ? payload.themes_detected.map((theme) => pill(theme)).join("")
    : pill("aucun theme", "warning");

  const insightBlocks = payload.insights.length
    ? payload.insights
        .map(
          (insight) => `
            <article class="insight">
              <h3>${insight.topic}</h3>
              <div class="pill-row">
                ${pill(insight.sentiment, insight.sentiment === "negative" ? "negative" : insight.sentiment === "positive" ? "positive" : "neutral")}
                ${pill(`Confiance ${insight.confidence}`, "neutral")}
              </div>
              <p><strong>Evidence:</strong> ${insight.evidence}</p>
              <p><strong>Action:</strong> ${insight.actionable_text}</p>
            </article>
          `
        )
        .join("")
    : `<div class="empty">Aucun insight detaille disponible.</div>`;

  qs("insights").innerHTML = `
    <article class="insight">
      <h3>Synthese</h3>
      <div class="pill-row">
        ${pill(payload.global_sentiment, sentimentVariant)}
        ${themes}
        ${payload.needs_human_review ? pill("human review", "warning") : ""}
      </div>
    </article>
    ${insightBlocks}
  `;

  toJsonBlock("analyzeJson", payload);
}

async function runAnalyze() {
  const payload = await callApi("/v1/analyze", {
    method: "POST",
    body: JSON.stringify({
      review_id: qs("reviewId").value.trim() || "web_runtime_001",
      review_text: qs("reviewText").value.trim(),
      threshold: Number(qs("threshold").value || "0.34"),
    }),
  });
  renderAnalyze(payload);
}

function parseCsv(text) {
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  if (!lines.length) {
    return [];
  }
  const headers = lines[0].split(",").map((item) => item.trim());
  return lines.slice(1).map((line) => {
    const values = line.split(",");
    return headers.reduce((row, header, index) => {
      row[header] = (values[index] || "").trim();
      return row;
    }, {});
  });
}

function getReviewTextFromRow(row) {
  if (row.review_text) {
    return row.review_text;
  }
  if (row.review_body && row.review_title) {
    return `${row.review_title} ${row.review_body}`.trim();
  }
  return row.review_body || row.text || "";
}

function renderBatchTable(results) {
  const tbody = qs("batchTable").querySelector("tbody");
  tbody.innerHTML = results
    .map(
      (item) => `
        <tr>
          <td>${item.review_id}</td>
          <td>${item.global_sentiment}</td>
          <td>${item.themes_detected.join(", ") || "aucun"}</td>
          <td>${item.score_global}</td>
          <td>${item.needs_human_review ? "oui" : "non"}</td>
        </tr>
      `
    )
    .join("");
}

async function runBatch() {
  if (!state.batchRows.length) {
    return;
  }
  qs("batchStatus").textContent = "Analyse en cours...";
  const results = [];
  for (const [index, row] of state.batchRows.entries()) {
    const reviewText = getReviewTextFromRow(row);
    if (!reviewText) {
      continue;
    }
    const payload = await callApi("/v1/analyze", {
      method: "POST",
      body: JSON.stringify({
        review_id: row.review_id || `batch_${index + 1}`,
        review_text: reviewText,
      }),
    });
    results.push(payload);
    qs("batchStatus").textContent = `Analyse en cours... ${results.length}/${state.batchRows.length}`;
  }
  state.batchResults = results;
  renderBatchTable(results);
  qs("batchStatus").textContent = `${results.length} review(s) analysee(s).`;
  qs("exportBatch").disabled = !results.length;
}

function exportBatchCsv() {
  if (!state.batchResults.length) {
    return;
  }
  const lines = [
    "review_id,global_sentiment,themes_detected,score_global,needs_human_review",
    ...state.batchResults.map(
      (row) =>
        `${row.review_id},${row.global_sentiment},"${row.themes_detected.join("|")}",${row.score_global},${row.needs_human_review}`
    ),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "review_insights_batch_results.csv";
  link.click();
  URL.revokeObjectURL(url);
}

async function runEvaluation() {
  const payload = await callApi("/v1/evaluate/default", { method: "GET", headers: {} });
  qs("evaluationStats").innerHTML = [
    card("Sentiment accuracy", payload.sentiment_accuracy),
    card("Theme exact match", payload.theme_exact_match),
    card("Precision macro", payload.theme_precision_macro),
    card("Recall macro", payload.theme_recall_macro),
  ].join("");
  toJsonBlock("evaluationJson", payload);
}

async function refreshAll() {
  await Promise.all([loadHealth(), loadMetrics()]);
}

function wireEvents() {
  qs("refreshAll").addEventListener("click", () => refreshAll().catch(showError));
  qs("refreshHealth").addEventListener("click", () => loadHealth().catch(showError));
  qs("refreshMetrics").addEventListener("click", () => loadMetrics().catch(showError));
  qs("runAnalyze").addEventListener("click", () => runAnalyze().catch(showError));
  qs("runEvaluation").addEventListener("click", () => runEvaluation().catch(showError));
  qs("runBatch").addEventListener("click", () => runBatch().catch(showError));
  qs("exportBatch").addEventListener("click", exportBatchCsv);

  document.querySelectorAll(".sample-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const sample = button.getAttribute("data-sample");
      qs("reviewText").value = SAMPLE_REVIEWS[sample] || SAMPLE_REVIEWS.support;
    });
  });

  qs("batchFile").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      state.batchRows = [];
      qs("runBatch").disabled = true;
      qs("batchStatus").textContent = "Aucun fichier charge.";
      return;
    }
    const text = await file.text();
    state.batchRows = parseCsv(text);
    qs("runBatch").disabled = !state.batchRows.length;
    qs("batchStatus").textContent = `${state.batchRows.length} ligne(s) detectee(s).`;
  });
}

function showError(error) {
  const message = String(error);
  ["healthJson", "metricsJson", "analyzeJson", "evaluationJson"].forEach((id) => {
    const node = qs(id);
    if (node && !node.textContent) {
      node.textContent = message;
    }
  });
  qs("batchStatus").textContent = message;
}

document.addEventListener("DOMContentLoaded", async () => {
  qs("apiBase").value = DEFAULT_API_BASE;
  wireEvents();
  try {
    await refreshAll();
    await runAnalyze();
  } catch (error) {
    showError(error);
  }
});
