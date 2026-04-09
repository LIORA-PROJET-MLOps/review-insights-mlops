const capabilityData = [
  {
    label: "Analyse unitaire",
    title: "Une lecture immediate d'une review individuelle",
    description:
      "Le produit accepte un texte, detecte les themes presents, calcule un sentiment global, detaille la lecture par theme et expose un niveau de confiance exploitable.",
    bullets: [
      "Detection multi-theme sur livraison, service client et produit",
      "Sentiment global et sentiment par theme",
      "Evidence hints et texte actionnable pour les equipes metier",
      "Flag human review quand le signal reste ambigu",
    ],
  },
  {
    label: "Batch intelligence",
    title: "Une analyse industrialisable sur des jeux de reviews",
    description:
      "La meme logique est disponible en mode batch pour enrichir un dataset, exporter des sorties tabulaires et alimenter un pipeline de reporting ou de triage.",
    bullets: [
      "Preparation dataset et normalisation des colonnes",
      "Export CSV et JSON des resultats enrichis",
      "Evaluation offline batch a partir d'un dataset de reference",
      "Compatibilite avec des flux ulterieurs type dashboard ou ticketing",
    ],
  },
  {
    label: "Monitoring",
    title: "Une supervision native des usages et des predictions",
    description:
      "La plateforme expose les compteurs essentiels pour suivre l'activite, la qualite percue et les besoins de revue humaine.",
    bullets: [
      "Healthcheck applicatif et backend actif",
      "Distribution des sentiments et des themes detectes",
      "Taux de human review",
      "Base saine pour brancher Prometheus ou Grafana ensuite",
    ],
  },
  {
    label: "Gouvernance",
    title: "Des garde-fous techniques et un chemin clair vers la prod",
    description:
      "Review Insights+ est pense comme un produit supervisable, testable et versionnable. Cela reduit le risque de dette technique des les premieres iterations.",
    bullets: [
      "Manifest d'artefacts et selection automatique du backend",
      "CI GitHub Actions et conteneurisation Docker",
      "Permissions API et headers de securite",
      "Trajectoire explicite vers retraining, drift et observabilite etendue",
    ],
  },
];

const processData = [
  {
    step: "01",
    title: "Ingestion",
    text: "La review entre via API ou interface et est encapsulee dans un schema stable.",
  },
  {
    step: "02",
    title: "Preparation",
    text: "Le texte est normalise et prepare dans un format compatible pour inference et export.",
  },
  {
    step: "03",
    title: "Theme detection",
    text: "Le classifieur thematique detecte la presence des sujets livraison, SAV et produit.",
  },
  {
    step: "04",
    title: "Sentiment routing",
    text: "Des modeles de sentiment specialises par theme affinent la lecture et le niveau de confiance.",
  },
  {
    step: "05",
    title: "Decision layer",
    text: "Le service consolide score global, evidence, insights et besoin eventuel de revue humaine.",
  },
  {
    step: "06",
    title: "Delivery and ops",
    text: "Les resultats sont exposes dans les sorties API, les exports, les metriques et les rapports.",
  },
];

const faqData = [
  {
    question: "Pourquoi cette architecture est-elle differenciante ?",
    answer:
      "Parce qu'elle separe clairement la logique produit, la logique de service et la logique modele. Cette separation permet de faire evoluer l'inference sans casser les contrats front, API ou reporting.",
  },
  {
    question: "Pourquoi un modele thematique puis des modeles de sentiment par theme ?",
    answer:
      "Parce qu'une review peut melanger plusieurs sujets. Un pipeline multi-etapes permet de distinguer la nature du probleme puis de qualifier le sentiment de facon plus utile pour l'action metier.",
  },
  {
    question: "Quel est l'avantage pour une equipe produit ou CX ?",
    answer:
      "Le gain principal est la reduction du temps entre feedback brut et decision. Les reviews sont traduites en signaux priorisables, partageables et monitorables.",
  },
  {
    question: "Que reste-t-il a faire pour aller vers une version plus industrielle ?",
    answer:
      "La prochaine etape est d'ajouter une pipeline de training reproductible, un meilleur versionnement du mapping de classes, du drift monitoring et une observabilite externe plus complete.",
  },
];

function renderCapabilityTabs() {
  const tabRoot = document.getElementById("capability-tabs");
  const panel = document.getElementById("capability-panel");

  function update(index) {
    const item = capabilityData[index];
    tabRoot.querySelectorAll("button").forEach((button, buttonIndex) => {
      button.classList.toggle("active", buttonIndex === index);
    });
    panel.innerHTML = `
      <p class="eyebrow dark">Focus</p>
      <h3>${item.title}</h3>
      <p>${item.description}</p>
      <ul>
        ${item.bullets.map((bullet) => `<li>${bullet}</li>`).join("")}
      </ul>
    `;
  }

  tabRoot.innerHTML = capabilityData
    .map((item) => `<button class="tab-button" type="button">${item.label}</button>`)
    .join("");

  tabRoot.querySelectorAll("button").forEach((button, index) => {
    button.addEventListener("click", () => update(index));
  });

  update(0);
}

function renderProcess() {
  const root = document.getElementById("process-grid");
  root.innerHTML = processData
    .map(
      (item) => `
        <article class="process-card">
          <span>${item.step}</span>
          <h3>${item.title}</h3>
          <p>${item.text}</p>
        </article>
      `
    )
    .join("");
}

function renderFaq() {
  const root = document.getElementById("faq-list");
  root.innerHTML = faqData
    .map(
      (item, index) => `
        <details class="faq-item" ${index === 0 ? "open" : ""}>
          <summary>${item.question}</summary>
          <p>${item.answer}</p>
        </details>
      `
    )
    .join("");
}

renderCapabilityTabs();
renderProcess();
renderFaq();
