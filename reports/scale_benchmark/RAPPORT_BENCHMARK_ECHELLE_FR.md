# Rapport du benchmark d'échelle

Date d'exécution : 20 août 2026

Trois profils synthétiques de 15 000 avis chacun ont été générés et validés, soit 45 000 lignes au total : `balanced_core`, `noisy_long_tail` et `multitheme_context`. Aucun rejet ni fuite exacte entre partitions n'a été détecté.

Les versions candidates v4, v5 et v6 ont obtenu des scores parfaits sur ce benchmark synthétique. Ces scores démontrent la reproductibilité technique et la tenue à l'échelle de la pipeline, mais ne prouvent pas la généralisation réelle. La candidate v6 a ensuite échoué sur trois seuils thèmes du référentiel historique indépendant de 40 avis : exactitude stricte, précision macro et macro-F1. Le déploiement a donc été annulé et la version v7 conservée.

Ce rejet a déclenché le cycle de données réelles décrit dans [le rapport final](../real_mixed_cycle/RAPPORT_FINAL_FR.md). Le modèle v8 issu de 5 811 avis réels annotés et de 4 500 ancrages synthétiques a ensuite franchi tous les seuils du test aveugle réel de 150 avis.

Décision méthodologique : les benchmarks synthétiques restent utiles pour tester la charge, les cas limites et les pipelines. Toute promotion doit cependant être conditionnée par un ensemble réel, indépendant, stratifié et verrouillé.
