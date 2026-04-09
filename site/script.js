const data = {
  metrics: [
    { label: "Accuracy sentiment", value: "0.75", detail: "Evaluation offline sur dataset demo" },
    { label: "Theme exact match", value: "1.00", detail: "Detection thematique tres solide" },
    { label: "Tests automatiques", value: "14", detail: "Verification locale passee" },
    { label: "Backend actif", value: "project_models_v1", detail: "Artefacts reels charges" },
  ],
  architecture: [
    {
      index: "01",
      title: "Frontend",
      type: "Streamlit",
      text: "Interface de demo orientee soutenance, lecture rapide et export batch."
    },
    {
      index: "02",
      title: "API",
      type: "FastAPI",
      text: "Endpoints stables pour /health, /metrics et /v1/analyze avec protections minimales."
    },
    {
      index: "03",
      title: "Service metier",
      type: "Orchestration",
      text: "Point d'entree unique qui choisit le backend, enregistre le monitoring et gere l'evaluation."
    },
    {
      index: "04",
      title: "Inference",
      type: "Model backend",
      text: "Chargement des vrais modeles du projet avec fallback heuristique si les artefacts sont absents."
    },
    {
      index: "05",
      title: "MLOps",
      type: "Eval + CI/CD",
      text: "Rapports, pipelines, Docker, GitHub Actions et livrables documentes pour la soutenance."
    }
  ],
  phases: [
    {
      title: "Phase 1 • Fondations",
      summary: "Structurer le projet pour qu'il soit lisible, testable et relancable sans bricolage.",
      chips: ["code modulaire", "configuration centralisee", "tests", "documentation", "API + UI"]
    },
    {
      title: "Phase 2 • Microservices & versioning",
      summary: "Separer les responsabilites et rendre les artefacts modeles explicites dans le depot.",
      chips: ["service layer", "manifest.json", "model backend", "variables d'environnement", "contrats stables"]
    },
    {
      title: "Phase 3 • Orchestration & deploiement",
      summary: "Raconter une vraie histoire de mise en production, meme a l'echelle POC.",
      chips: ["Dockerfile", "compose.yaml", "healthcheck", "GitHub Actions", "scripts pipelines"]
    },
    {
      title: "Phase 4 • Monitoring & maintenance",
      summary: "Prouver que l'on sait mesurer, surveiller et preparer la suite du cycle de vie modele.",
      chips: ["metrics runtime", "evaluation offline", "human review rate", "reporting", "roadmap retraining"]
    }
  ],
  demos: [
    {
      title: "Cas 1 • SAV negatif",
      review: "Customer support never answered my refund request and the process was frustrating.",
      sentiment: "negative",
      badges: ["service client", "negative", "human review: non"],
      outputs: [
        "Theme detecte: SAV",
        "Signal operationnel: escalation support",
        "Evidence: Service client model",
        "Utilite demo: montrer une lecture actionnable immediate"
      ]
    },
    {
      title: "Cas 2 • Livraison + produit positifs",
      review: "Fast delivery, excellent quality and perfect fit. I am very happy with the purchase.",
      sentiment: "positive",
      badges: ["livraison", "produit", "positive"],
      outputs: [
        "Themes detectes: livraison et produit",
        "Signal operationnel: points forts a valoriser",
        "Confiance exploitable pour reporting CX",
        "Utilite demo: montrer le multi-theme"
      ]
    },
    {
      title: "Cas 3 • Cas ambigu",
      review: "The return was accepted but the refund process was slow and a bit confusing.",
      sentiment: "neutral",
      badges: ["livraison", "service client", "human review: oui"],
      outputs: [
        "Cas borderline avec confiance plus faible",
        "Flag human review active",
        "Illustration de la prudence metier",
        "Utilite demo: montrer la gouvernance du risque"
      ]
    }
  ],
  deliverables: [
    {
      title: "Application",
      items: ["Streamlit pour la demo", "FastAPI pour l'exposition API", "UX claire pour la soutenance"]
    },
    {
      title: "MLOps",
      items: ["Modeles reels branches", "Evaluation offline", "Monitoring runtime", "Rapports JSON et Markdown"]
    },
    {
      title: "Exploitation",
      items: ["Dockerfile", "compose.yaml", "CI GitHub Actions", "Configuration par env"]
    }
  ],
  faq: [
    {
      q: "Pourquoi presenter un POC production-shaped ?",
      a: "Parce que la valeur du projet est autant dans l'architecture et l'exploitabilite que dans le modele lui-meme."
    },
    {
      q: "Pourquoi la documentation est-elle en francais et les reviews en anglais ?",
      a: "Le cadre projet est francophone, mais les modeles et les donnees actuellement disponibles sont calibres pour l'anglais."
    },
    {
      q: "Quel est le principal axe de progression apres la soutenance ?",
      a: "Industrialiser la pipeline d'entrainement, figer le mapping de classes de sentiment et evaluer sur un vrai jeu de validation."
    }
  ]
};

function renderHeroMetrics() {
  const root = document.getElementById("hero-metrics");
  root.innerHTML = data.metrics
    .map(
      (metric) => `
        <article class="metric-card reveal">
          <span class="metric-label">${metric.label}</span>
          <span class="metric-value">${metric.value}</span>
          <p>${metric.detail}</p>
        </article>
      `
    )
    .join("");
}

function renderArchitecture() {
  const root = document.getElementById("architecture-grid");
  root.innerHTML = data.architecture
    .map(
      (item) => `
        <article class="architecture-card reveal">
          <div class="architecture-index">${item.index}</div>
          <div class="architecture-type">${item.type}</div>
          <h3>${item.title}</h3>
          <p>${item.text}</p>
        </article>
      `
    )
    .join("");
}

function renderPhases() {
  const controls = document.getElementById("phase-controls");
  const detail = document.getElementById("phase-detail");

  function updatePhase(index) {
    controls.querySelectorAll("button").forEach((button, buttonIndex) => {
      button.classList.toggle("active", buttonIndex === index);
    });
    const phase = data.phases[index];
    detail.innerHTML = `
      <h3>${phase.title}</h3>
      <p>${phase.summary}</p>
      <div class="chip-row">
        ${phase.chips.map((chip) => `<span class="chip">${chip}</span>`).join("")}
      </div>
    `;
  }

  controls.innerHTML = data.phases
    .map((phase, index) => `<button class="phase-button" type="button">${phase.title}</button>`)
    .join("");

  controls.querySelectorAll("button").forEach((button, index) => {
    button.addEventListener("click", () => updatePhase(index));
  });

  updatePhase(0);
}

function renderDemo() {
  const list = document.getElementById("demo-list");
  const preview = document.getElementById("demo-preview");

  function badgeClass(sentiment) {
    if (sentiment === "positive") return "badge-positive";
    if (sentiment === "negative") return "badge-negative";
    return "badge-neutral";
  }

  function updateDemo(index) {
    list.querySelectorAll(".demo-item").forEach((item, itemIndex) => {
      item.classList.toggle("active", itemIndex === index);
    });
    const demo = data.demos[index];
    preview.innerHTML = `
      <h3>${demo.title}</h3>
      <div class="badge-row">
        ${demo.badges
          .map((badge) => `<span class="badge ${badgeClass(demo.sentiment)}">${badge}</span>`)
          .join("")}
      </div>
      <div class="review-box">
        <strong>Review example</strong>
        <p>${demo.review}</p>
      </div>
      <div class="output-box">
        <strong>Sortie attendue</strong>
        <ul class="output-list">
          ${demo.outputs.map((item) => `<li>${item}</li>`).join("")}
        </ul>
      </div>
      <div class="bar-track">
        <div class="bar-fill" style="width:${index === 0 ? 78 : index === 1 ? 82 : 56}%"></div>
      </div>
    `;
  }

  list.innerHTML = data.demos
    .map(
      (demo) => `
        <article class="demo-item reveal">
          <h3>${demo.title}</h3>
          <p>${demo.review}</p>
        </article>
      `
    )
    .join("");

  list.querySelectorAll(".demo-item").forEach((item, index) => {
    item.addEventListener("click", () => updateDemo(index));
  });

  updateDemo(0);
}

function renderMetrics() {
  const root = document.getElementById("metrics-grid");
  root.innerHTML = data.metrics
    .map(
      (metric) => `
        <article class="metric-card reveal">
          <span class="metric-label">${metric.label}</span>
          <span class="metric-value">${metric.value}</span>
          <p>${metric.detail}</p>
        </article>
      `
    )
    .join("");
}

function renderDeliverables() {
  const root = document.getElementById("deliverables-grid");
  root.innerHTML = data.deliverables
    .map(
      (block) => `
        <article class="deliverable-card reveal">
          <h3>${block.title}</h3>
          <ul>
            ${block.items.map((item) => `<li>${item}</li>`).join("")}
          </ul>
        </article>
      `
    )
    .join("");
}

function renderFaq() {
  const root = document.getElementById("faq-list");
  root.innerHTML = data.faq
    .map(
      (item, index) => `
        <details class="faq-item reveal" ${index === 0 ? "open" : ""}>
          <summary>${item.q}</summary>
          <p>${item.a}</p>
        </details>
      `
    )
    .join("");
}

function setupReveal() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  document.querySelectorAll(".reveal").forEach((element) => observer.observe(element));
}

renderHeroMetrics();
renderArchitecture();
renderPhases();
renderDemo();
renderMetrics();
renderDeliverables();
renderFaq();
setupReveal();
