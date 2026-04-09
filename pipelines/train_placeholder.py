from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    artifacts_dir = ROOT_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    note_path = artifacts_dir / "TRAINING_PLACEHOLDER.md"
    note_path.write_text(
        "\n".join(
            [
                "# Training Placeholder",
                "",
                "Ce script sert de point d'entree pour la future pipeline d'entrainement reproductible.",
                "",
                "Etapes cibles a implementer:",
                "",
                "1. Chargement dataset d'entrainement",
                "2. Nettoyage / normalisation",
                "3. Entrainement modele thematique",
                "4. Entrainement modeles de sentiment par theme",
                "5. Evaluation offline",
                "6. Versionnement des artefacts",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Training placeholder written to: {note_path}")


if __name__ == "__main__":
    main()
