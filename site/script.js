const pipeline = [
  {
    step: "01",
    title: "Reception",
    text: "La review entre via API ou interface avec un contrat d'entree stabilise.",
  },
  {
    step: "02",
    title: "Preparation",
    text: "Le texte est normalise et prepare pour la couche d'inference et les exports.",
  },
  {
    step: "03",
    title: "Theme detection",
    text: "Le moteur thematique detecte les sujets actifs: livraison, SAV et produit.",
  },
  {
    step: "04",
    title: "Sentiment analysis",
    text: "Des modeles specialises par theme qualifient la polarite et le niveau de confiance.",
  },
  {
    step: "05",
    title: "Decision output",
    text: "Le service consolide les scores, les insights et le flag de revue humaine.",
  },
];

const root = document.getElementById("pipeline-grid");

if (root) {
  root.innerHTML = pipeline
    .map(
      (item) => `
        <article class="pipeline-card card">
          <span class="pipeline-step">${item.step}</span>
          <h3>${item.title}</h3>
          <p>${item.text}</p>
        </article>
      `
    )
    .join("");
}
