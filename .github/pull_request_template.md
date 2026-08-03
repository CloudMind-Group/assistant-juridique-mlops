## Objectif

<!-- Que fait cette PR, en une ou deux phrases ? -->

## Module concerné

<!-- Cochez le module ; le pilote (colonne A de la matrice RACI) sera relecteur. -->

- [ ] M1 — Data Pipeline & Preprocessing (Douae)
- [ ] M2 — Model Engineering & Fine-Tuning (Imane)
- [ ] M3 — Experiment Tracking & Model Registry (Amal)
- [ ] M4 — CI/CD & Infrastructure (Salma)
- [ ] M5 — API & Serving Layer (Nouhaila)
- [ ] M6 — UI/UX & Frontend Integration (Oumaima)
- [ ] M7 — Model Monitoring & Observability (Youssef)
- [ ] M8 — Security, Governance & Compliance (Taha)

## Type

- [ ] `feat` — nouvelle fonctionnalité
- [ ] `fix` — correction
- [ ] `docs` — documentation
- [ ] `refactor` / `style` / `chore`

## Branche cible (GitFlow)

- [ ] `develop` — depuis une branche `feature/*` (cas courant)
- [ ] `main` — depuis une branche `release/*` ou `hotfix/*` uniquement
- [ ] report d'une `release/*` ou `hotfix/*` vers `develop`

## Vérifications

- [ ] La CI passe au vert
- [ ] Testé localement (`python -m http.server` ou ouverture directe de `index.html`)
- [ ] Aucune donnée personnelle ni document juridique réel n'est ajouté au dépôt
- [ ] `docs/` mis à jour si le comportement ou l'architecture change
- [ ] Moins de 400 lignes modifiées (sinon, expliquer pourquoi)
- [ ] Si fusion dans `main` : un tag `vX.Y.Z` sera posé, et la branche sera reportée dans `develop`

## Impact sur le tableau de bord

<!-- Si assets/js/data.js est modifié : quelles valeurs changent et pourquoi ? -->

## Issue liée

Closes #
