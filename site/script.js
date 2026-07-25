const resultFilters = document.querySelectorAll("[data-result-filter]");
const resultCards = document.querySelectorAll("[data-result-kind]");

resultFilters.forEach((button) => {
  button.addEventListener("click", () => {
    resultFilters.forEach((item) => item.classList.toggle("is-active", item === button));
    const filter = button.dataset.resultFilter;
    resultCards.forEach((card) => {
      card.classList.toggle("is-hidden", filter !== "all" && card.dataset.resultKind !== filter);
    });
  });
});

const trajectoryContent = {
  current: [
    ["Expérience", "Analyse, batch et exploration dans une interface unique"],
    ["Modèles", "Pipeline thématique et sentiment spécialisé"],
    ["Gouvernance", "Évaluation, monitoring et correction humaine tracée"],
  ],
  target: [
    ["Expérience", "Parcours intégrés aux outils produit, CX et support"],
    ["Modèles", "Versionnement, promotion et réentraînement automatisés"],
    ["Gouvernance", "SLA, alerting, audit et pilotage continu de la qualité"],
  ],
};

const trajectoryButtons = document.querySelectorAll("[data-trajectory]");
const trajectoryPanel = document.querySelector("[data-trajectory-panel]");

trajectoryButtons.forEach((button) => {
  button.addEventListener("click", () => {
    trajectoryButtons.forEach((item) => item.setAttribute("aria-selected", String(item === button)));
    trajectoryPanel.innerHTML = trajectoryContent[button.dataset.trajectory]
      .map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`)
      .join("");
  });
});
