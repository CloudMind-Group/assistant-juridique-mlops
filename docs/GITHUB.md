# Gouvernance GitHub — CloudMind Group

Rôles, permissions et règles de collaboration sur le dépôt.
Projet contraint à **4 semaines** : les règles ci-dessous sont volontairement légères,
mais non négociables sur la branche `main`.

---

## 1. Comptes de l'équipe

> À compléter par chaque membre avant la fin de la semaine 1, puis à répercuter dans
> [`.github/CODEOWNERS`](../.github/CODEOWNERS).

| Membre | Pseudo GitHub (à confirmer) | Module piloté | Rôle sur le dépôt |
|---|---|---|---|
| Salma El Ouarrate | `@salma-elouarrate` | M4 — CI/CD & Infrastructure | **Admin** |
| Youssef El Alem | `@youssefelalem` | M7 — Monitoring & Observability | **Maintain** |
| Taha Kachmar | `@taha-kachmar` | M8 — Security & Compliance | **Maintain** |
| Douae Moussaoui | `@douae-moussaoui` | M1 — Data Pipeline | Write |
| Imane Ibnchakroune | `@imane-ibnchakroune` | M2 — Model Engineering | Write |
| Amal El Guerdani | `@amal-elguerdani` | M3 — Tracking & Registry | Write |
| Nouhaila Fadli | `@nouhaila-fadli` | M5 — API & Serving | Write |
| Oumaima Jeraidi | `@oumaima-jeraidi` | M6 — UI/UX & Frontend | Write |
| Encadrant / référent métier | `@encadrant` | — | Read (+ Triage) |

## 2. Signification des rôles GitHub

| Rôle | Ce qu'il permet | Attribué à | Pourquoi |
|---|---|---|---|
| **Admin** | Tout, y compris les réglages du dépôt, les règles de protection, les secrets et la suppression | Salma (M4) | Elle pilote la CI/CD et l'infrastructure : un seul point de responsabilité sur les réglages |
| **Maintain** | Gérer les issues, les PR, les milestones, les paramètres non destructifs — sans accès aux secrets ni suppression | Youssef (M7), Taha (M8) | Supervision et sécurité : ils arbitrent les fusions quand Salma est indisponible |
| **Write** | Pousser des branches, ouvrir et réviser des PR, gérer les issues | Les 5 autres pilotes | Suffisant pour contribuer ; empêche toute modification des règles |
| **Triage** | Trier les issues et PR sans droit d'écriture sur le code | Encadrant | Suivi pédagogique sans risque |
| **Read** | Lecture, clone, discussions | Observateurs | — |

> **Règle des deux administrateurs :** en cas d'absence de Salma, Youssef est promu Admin
> temporairement. Ne jamais laisser le dépôt avec un seul administrateur joignable.

## 3. Protection de la branche `main`

À activer dans `Settings → Branches → Add branch protection rule`, motif `main` :

- [x] **Require a pull request before merging** — aucun `push` direct sur `main`
- [x] **Require approvals : 1** (2 pour `assets/js/data.js` et `.github/`)
- [x] **Require review from Code Owners** — s'appuie sur `.github/CODEOWNERS`
- [x] **Dismiss stale approvals when new commits are pushed**
- [x] **Require status checks to pass** → job `validate` du workflow CI
- [x] **Require conversation resolution before merging**
- [x] **Require linear history** — fusion en *squash* uniquement
- [ ] *Allow force pushes* — désactivé
- [ ] *Allow deletions* — désactivé

Dans `Settings → General → Pull Requests` : ne laisser que **Squash merging**,
et cocher *Automatically delete head branches*.

### État actuel

Le ruleset **« Protection de main »** est **déjà actif** sur le dépôt
(`Settings → Rules → Rulesets`). Il applique les cinq règles suivantes :

| Règle | Effet |
|---|---|
| `pull_request` | 1 approbation, revue des Code Owners, résolution des conversations, squash uniquement |
| `required_status_checks` | le job `Validation du site statique` doit être vert, branche à jour |
| `required_linear_history` | pas de commit de fusion |
| `non_fast_forward` | force push interdit |
| `deletion` | suppression de `main` interdite |

> ⚠️ **Dérogation temporaire :** le rôle *Repository admin* dispose actuellement d'un
> bypass (`bypass_mode: always`). Sans lui, le dépôt serait bloqué tant qu'un seul
> compte y a accès : personne ne peut approuver sa propre PR.
> **À supprimer dès que les huit membres sont ajoutés comme collaborateurs**
> (`Settings → Rules → Rulesets → Protection de main → Bypass list`).

### Rappel CODEOWNERS

Tant que les pseudos `@prenom-nom` ne correspondent pas à des comptes réels **ayant
accès en écriture au dépôt**, GitHub signale une erreur par ligne et la revue des
Code Owners ne peut pas être satisfaite. Vérifiez l'état sur
`https://github.com/<owner>/<repo>/codeowners/errors` après avoir invité l'équipe.

## 4. Convention de branches

```
main                     ← protégée, toujours déployable
├── feat/m1-ingestion-pdf
├── feat/m5-cache-redis
├── fix/m6-citation-overflow
├── docs/architecture-rag
└── chore/ci-cache-node
```

Format : `<type>/<module>-<sujet-court>` en minuscules, avec `m1`…`m8` pour rattacher la
branche à son module — le rattachement rend le tableau de bord GitHub Projects lisible d'un coup d'œil.

Types autorisés : `feat`, `fix`, `docs`, `refactor`, `style`, `test`, `chore`.

## 5. Commits

[Conventional Commits](https://www.conventionalcommits.org/fr/) avec portée = module :

```
feat(m2): ajoute le re-ranking par cross-encoder
fix(m5): corrige la fuite de connexion Redis sur timeout
docs(m8): complète le registre RGPD
chore(ci): met en cache les dépendances du workflow
```

## 6. Cycle de vie d'une pull request

1. Créer la branche depuis `main` à jour.
2. Ouvrir la PR **en brouillon** dès le premier commit — la visibilité prime sur la perfection.
3. Renseigner le gabarit ([`pull_request_template.md`](../.github/pull_request_template.md)).
4. Passer la PR en « Ready for review » et demander la revue du pilote concerné (colonne **A** de la matrice RACI).
5. Le pilote relit sous **24 h maximum** — planning d'un mois, aucune PR ne doit dormir.
6. Fusion en *squash* par l'auteur une fois la CI verte et l'approbation obtenue.

**Taille cible d'une PR : moins de 400 lignes modifiées.** Au-delà, découper.

## 7. Étiquettes (labels)

| Étiquette | Couleur | Usage |
|---|---|---|
| `module: M1` … `module: M8` | `#6366f1` | Rattachement au module |
| `type: feature` | `#22d3ee` | Nouvelle fonctionnalité |
| `type: bug` | `#ef4444` | Anomalie |
| `type: docs` | `#a78bfa` | Documentation |
| `priority: high` | `#f59e0b` | Bloque un jalon hebdomadaire |
| `blocked` | `#64748b` | En attente d'une dépendance externe |
| `good first issue` | `#34d399` | Prise en main |

## 8. Milestones — un par semaine

| Milestone | Échéance | Contenu |
|---|---|---|
| `S1 — Cadrage & socle` | J+7 | Corpus initial, squelette CI/Docker, maquettes, règles RGPD |
| `S2 — RAG & API v1` | J+14 | Index vectoriel, chaîne RAG tracée, API et interface reliées |
| `S3 — Qualité & optimisation` | J+21 | Évaluation RAGAS, citations, cache et streaming, métriques |
| `S4 — Durcissement & livraison` | J+28 | Observabilité, sécurité, tests de charge, déploiement, soutenance |

Toute issue **doit** porter un module, un type et une milestone. Une issue sans milestone
n'entre pas dans le mois.

## 9. GitHub Projects

Tableau `Assistant Juridique — 4 semaines`, vue Board avec les colonnes :
`Backlog` → `Semaine en cours` → `En cours` → `En revue` → `Terminé`.

Champs personnalisés : `Module` (M1–M8), `Pilote`, `Semaine` (S1–S4), `Estimation` (h).

## 10. Secrets et sécurité

- Les secrets vivent dans `Settings → Secrets and variables → Actions`, **jamais** dans le dépôt.
- Seule l'administratrice (M4) crée ou fait tourner les secrets ; toute demande passe par une issue `type: chore`.
- `Settings → Actions → General` : permissions du `GITHUB_TOKEN` en **lecture seule** par défaut.
- Aucune donnée juridique réelle, aucun document client, aucune donnée personnelle dans le dépôt — y compris dans les issues et les captures d'écran. Responsable : M8.

## 11. Mise en ligne de la page

`Settings → Pages → Source: Deploy from a branch → main / (root)`.
Le site étant statique et sans étape de build, il est publié tel quel sur
`https://<organisation>.github.io/<depot>/`.
