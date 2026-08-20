# Rapport final du cycle POC sur données réelles

Date d'exécution : 20 août 2026

## Décision

Le modèle `hybrid_lr_c4` a franchi tous les seuils POC sur le test aveugle réel. Il est enregistré dans MLflow sous la version `8` et promu avec l'alias `champion`. La version `7` reste disponible sous l'alias `previous_champion` pour un retour arrière contrôlé.

## Traçabilité des données

La source réelle est FABSA (`jordiclive/FABSA`), figée à la révision `40abb500cd7688529cb831c8c2c2a90d06264379`. Elle contient des avis réels en anglais issus de Trustpilot, Google Play et Apple Store, avec des annotations humaines multi-étiquettes d'aspect et de sentiment.

| Jeu de données enregistré | Lignes | Utilisation |
|---|---:|---|
| `fabsa_real_gold_900_v1` | 900 | Gold set stratifié : 600 entraînement, 150 validation, 150 test aveugle |
| `fabsa_real_gold_expanded_v1` | 6 111 | Extension réelle : 5 811 entraînement, 150 validation, 150 test aveugle |
| `fabsa_real_plus_synthetic_train_v1` | 10 311 | Entraînement final : 5 811 avis réels annotés et 4 500 ancrages synthétiques équilibrés |

Les contrôles ont relevé zéro doublon normalisé entre les partitions, zéro ligne rejetée dans les jeux publiés, zéro PII probable et aucune fuite exacte vers les ensembles de validation et de test. Ces deux ensembles contiennent exclusivement des avis réels et n'ont jamais servi à l'entraînement.

La fiche publique FABSA ne déclare pas de licence explicite. Les textes des avis ne sont donc pas redistribués dans Git ; seuls les scripts reproductibles, les manifestes, les empreintes et les résultats agrégés sont versionnés. Toute redistribution ou exploitation commerciale nécessite une vérification juridique séparée.

## Sélection sur la validation réelle

| Variante | Macro-F1 sentiment | Exactitude thèmes | Précision thèmes | Rappel thèmes | Macro-F1 thèmes |
|---|---:|---:|---:|---:|---:|
| `word_lr_c4` | 0,8319 | 0,6933 | 0,8577 | 0,8060 | 0,8294 |
| `hybrid_lr_c1` | 0,8620 | 0,7067 | 0,8734 | 0,7685 | 0,8162 |
| `hybrid_lr_c2` | 0,8620 | 0,6933 | 0,8634 | 0,7870 | 0,8209 |
| `hybrid_lr_c4` | 0,8563 | 0,7133 | 0,8840 | 0,8017 | 0,8385 |

`hybrid_lr_c4` a été choisi avant l'ouverture du test aveugle, car il présentait le meilleur compromis conjoint entre exactitude, précision et rappel des thèmes.

## Résultats sur le test aveugle réel

Le test contient 150 avis réels et figés.

| KPI | Résultat | Seuil POC v2 | Décision |
|---|---:|---:|---|
| Exactitude sentiment | 0,8600 | ≥ 0,82 | PASS |
| Macro-F1 sentiment | 0,8473 | ≥ 0,80 | PASS |
| Exactitude stricte thèmes | 0,6600 | ≥ 0,62 | PASS |
| Précision macro thèmes | 0,8895 | ≥ 0,85 | PASS |
| Rappel macro thèmes | 0,8032 | ≥ 0,78 | PASS |
| Macro-F1 thèmes | 0,8359 | ≥ 0,82 | PASS |
| Taux de revue humaine | 0,0200 | ≤ 0,10 | PASS |

Les F1 par thème sont de 0,7857 pour `livraison`, 0,8404 pour `sav` et 0,8817 pour `produit`. Le rappel `livraison` de 0,66 reste le principal indicateur de vigilance.

Le taux de 0,0200 est la métrique du modèle utilisée par le gate de registre. Une contre-évaluation via le parcours API complet, qui ajoute le garde-fou de conflits de sentiment, conserve les mêmes métriques de qualité et porte ce taux à 0,0400. Les deux valeurs restent sous le plafond de 0,10.

## Compatibilité avec le domaine historique

Sur les 40 avis physiques du référentiel historique POC, le champion atteint une précision thèmes de 0,9269, un rappel de 0,8221 et une macro-F1 de 0,8690. La macro-F1 sentiment est de 0,5809, principalement pénalisée par la classe neutre. Cette mesure constitue un garde-fou de compatibilité et non l'estimation principale de généralisation.

## Registre, déploiement et observabilité

- Modèle MLflow : `review-insights-project-models`
- Run de publication : `123177698e004d16a4025bc8913ea35e`
- Version : `8`
- Alias : `champion=8`, `candidate=8`, `previous_champion=7`
- Politique : `2.0.0-real-blind`
- Backend API : `project_models_v1`, sans erreur de chargement ni fallback
- Artefacts actifs : cinq modèles sérialisés, seuils thèmes et manifeste avec SHA-256 dans `models/`

Les 126 tests passent et Ruff ne signale aucune erreur. La pile Docker Compose complète a été vérifiée, avec les tableaux de bord Grafana API & Inférence, Qualité métier, Données & Modèles et Système & Orchestration correctement rendus. Le tableau Données & Modèles affiche `READY`, 10 311 lignes, les métriques aveugles et le gate `APPROUVÉ`.

Deux alertes de dérive historiques restent valides : elles proviennent de 66 événements de prédiction et 14 feedbacks antérieurs au champion v8. Elles ne sont pas remises à zéro artificiellement ; une nouvelle évaluation doit attendre suffisamment de feedbacks propres à v8.

## Cycle suivant recommandé

Collecter 100 à 200 feedbacks réels explicitement rattachés au champion v8, en suréchantillonnant les avis neutres et les formulations implicites de livraison. Ensuite seulement, exécuter la détection de dérive, le minage de cas difficiles et un nouveau test sur un holdout immuable. Le test aveugle actuel ne doit plus être utilisé pour ajuster le modèle.
