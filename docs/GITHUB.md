# Gouvernance GitHub — CloudMind Group

Rôles, permissions et règles de collaboration sur le dépôt.
Projet contraint à **4 semaines**. Modèle de branches retenu : **GitFlow**.
Les règles ci-dessous ne sont pas négociables sur `main` et `develop`.

---

## 1. Comptes de l'équipe

Le dépôt appartient à l'organisation **[CloudMind-Group](https://github.com/CloudMind-Group)**.
Les huit membres y sont invités et rattachés à une équipe : les droits découlent de
l'équipe, jamais d'un accès individuel.

| Membre | Compte GitHub | Module piloté | Équipe |
|---|---|---|---|
| Salma El Ouarrate | `@salmaelouarrate` | M4 — CI/CD & Infrastructure | `platform` |
| Youssef El Alem | `@youssefelalem` | M7 — Monitoring & Observability | `platform` |
| Douae Moussaoui | `@DOUAEM449` | M1 — Data Pipeline | `data` |
| Imane Ibnchakroune | `@ima-cs` | M2 — Model Engineering | `data` |
| Amal El Guerdani | `@amal4567` | M3 — Tracking & Registry | `data` |
| Nouhaila Fadli | `@nouhailafad` | M5 — API & Serving | `app` |
| Oumaima Jeraidi | `@Oumaimajeraidi` | M6 — UI/UX & Frontend | `app` |
| Taha Kachmar | `@taha588` | M8 — Security & Compliance | `security` |

## 1 bis. Équipes de l'organisation

Quatre équipes portent les droits. C'est le seul endroit à modifier quand quelqu'un
rejoint ou quitte le projet : [`CODEOWNERS`](../.github/CODEOWNERS) référence les
équipes, jamais les personnes.

| Équipe | Périmètre | Membres | Droit sur le dépôt |
|---|---|---|---|
| `@CloudMind-Group/platform` | M4 + M7 — CI/CD, infrastructure, observabilité | salmaelouarrate *(mainteneuse)*, youssefelalem *(mainteneur)* | **Admin** |
| `@CloudMind-Group/data` | M1 + M2 + M3 — données, RAG, expérimentation | DOUAEM449, ima-cs, amal4567 | Write |
| `@CloudMind-Group/app` | M5 + M6 — API, serving, interface | nouhailafad, Oumaimajeraidi | Write |
| `@CloudMind-Group/security` | M8 — sécurité, gouvernance, conformité | taha588 *(mainteneur)*, youssefelalem | Maintain |

**Ajouter un membre :**

```bash
gh api -X PUT orgs/CloudMind-Group/teams/<equipe>/memberships/<pseudo> -f role=member
```

**Retirer un membre :** le sortir de l'équipe suffit — aucun fichier à modifier.

### Le propriétaire de l'organisation est membre implicite de toutes les équipes

GitHub inscrit automatiquement le propriétaire de l'organisation comme *mainteneur* de
chaque équipe, sans qu'on l'y ajoute. Vérifiable à tout moment :

```bash
gh api orgs/CloudMind-Group/teams/data/memberships/youssefelalem
# -> role=maintainer, state=active — alors qu'il n'a jamais été ajouté à `data`
```

**Conséquence :** il satisfait à lui seul la revue des Code Owners de n'importe quel
chemin du dépôt. Pratique au démarrage, dangereux ensuite — la revue croisée se réduit
à un tampon unique.

> **Règle d'équipe :** le propriétaire n'use de ce droit que si aucun membre de l'équipe
> concernée n'a relu la pull request **sous 24 h**. Le relecteur par défaut reste le
> pilote du module, conformément à la colonne **A** de la matrice RACI.

Corollaire à ne pas oublier : le propriétaire ne peut pas approuver ses propres pull
requests. Tout ce qu'il écrit doit être relu par quelqu'un d'autre — c'est la seule
garantie que le principe des quatre yeux tienne aussi pour lui.

> Les accès individuels hérités du transfert (`DOUAEM449`, `ima-cs` en collaborateurs
> directs) deviennent redondants une fois les invitations d'organisation acceptées :
> les retirer alors depuis `Settings → Collaborators`, afin que l'appartenance à une
> équipe reste l'unique source de droits.

## 2. Signification des rôles GitHub

| Rôle | Ce qu'il permet | Attribué à | Pourquoi |
|---|---|---|---|
| **Admin** | Tout, y compris les réglages du dépôt, les règles de protection, les secrets et la suppression | équipe `platform` | Elle pilote la CI/CD et l'infrastructure : un seul point de responsabilité sur les réglages |
| **Maintain** | Gérer les issues, les PR, les milestones, les paramètres non destructifs — sans accès aux secrets ni suppression | équipe `security` | Supervision et sécurité : ils arbitrent les fusions quand Salma est indisponible |
| **Write** | Pousser des branches, ouvrir et réviser des PR, gérer les issues | équipes `data` et `app` | Suffisant pour contribuer ; empêche toute modification des règles |
| **Triage** | Trier les issues et PR sans droit d'écriture sur le code | encadrant, à inviter en `outside collaborator` | Suivi pédagogique sans risque |
| **Read** | Lecture, clone, discussions | Observateurs | — |

> **Règle des deux administrateurs :** l'équipe `platform` compte deux mainteneurs
> (Salma et Youssef). Ne jamais laisser l'organisation avec un seul propriétaire joignable.

## 3. Protection des branches

Deux branches sont permanentes et protégées par des *rulesets*
(`Settings → Rules → Rulesets`), tous deux **actifs**.

### `main` — branche de production

Ne reçoit **que** des branches `release/*` et `hotfix/*`. Chaque fusion correspond à
une version livrée et doit être suivie d'un tag `vX.Y.Z`.

| Règle | Effet |
|---|---|
| `pull_request` | 1 approbation, revue des Code Owners, conversations résolues, **merge commit** uniquement |
| `required_status_checks` | le job `Validation du site statique` doit être vert, branche à jour |
| `non_fast_forward` | force push interdit |
| `deletion` | suppression interdite |

> `required_linear_history` est **volontairement absent** : GitFlow impose des commits de
> fusion (`--no-ff`) pour conserver la trace de chaque branche intégrée.

### `develop` — branche d'intégration

Branche par défaut du dépôt : c'est là que partent et que reviennent toutes les
branches `feature/*`. Elle doit rester en état de fonctionner en permanence.

| Règle | Effet |
|---|---|
| `pull_request` | 1 approbation, revue des Code Owners, conversations résolues, merge ou squash |
| `required_status_checks` | le job `Validation du site statique` doit être vert, branche à jour |
| `non_fast_forward` | force push interdit |
| `deletion` | suppression interdite |

> ⚠️ **Dérogation temporaire :** le rôle *Repository admin* dispose d'un bypass
> (`bypass_mode: always`) sur les deux rulesets. Sans lui, le dépôt serait bloqué tant
> qu'un seul compte y a accès : personne ne peut approuver sa propre PR.
> **À supprimer dès que les huit membres sont ajoutés comme collaborateurs.**

### Réglages de fusion

`Settings → General → Pull Requests` : *Merge commits* et *Squash merging* activés,
*Rebase merging* désactivé, *Automatically delete head branches* coché.

### Rappel CODEOWNERS

`CODEOWNERS` ne référence que des équipes de l'organisation, toutes dotées d'un accès
en écriture : la revue des Code Owners est donc satisfaite dès qu'un membre de l'équipe
concernée approuve. État des lieux à tout moment sur
[`/codeowners/errors`](https://github.com/CloudMind-Group/assistant-juridique-mlops/codeowners/errors).

## 4. Modèle de branches — GitFlow

```
main      ──●───────────────────────●──────────●──▶   production, taggée vX.Y.Z
             \                     /          /
              \        release/1.0.0         /
               \      /          \          /
develop   ──●───●────●────●────────●────────●──▶      intégration continue
             \      /     \      /
              feature/m1-ocr      feature/m5-cache
                                              ▲
                                       hotfix/1.0.1 ──▶ main + develop
```

| Branche | Part de | Retourne vers | Durée de vie |
|---|---|---|---|
| `main` | — | — | permanente |
| `develop` | `main` | — | permanente |
| `feature/<module>-<sujet>` | `develop` | `develop` | quelques jours |
| `release/<version>` | `develop` | `main` **et** `develop` | fin de semaine |
| `hotfix/<version>` | `main` | `main` **et** `develop` | quelques heures |

Exemples : `feature/m1-ingestion-pdf`, `feature/m5-cache-redis`,
`release/0.2.0`, `hotfix/0.2.1`.

Le préfixe de module (`m1`…`m8`) reste obligatoire sur les branches `feature/*` :
il rattache la branche à son pilote dans la matrice RACI et rend le tableau
GitHub Projects lisible d'un coup d'œil.

### Cycle d'une fonctionnalité

```bash
git checkout develop && git pull
git checkout -b feature/m2-reranking
# ... commits ...
git push -u origin feature/m2-reranking
gh pr create --base develop            # revue du pilote M2, CI verte, fusion
```

### Cycle d'une livraison hebdomadaire

Chaque fin de semaine (S1 à S4) correspond à une version. La branche `release/*`
gèle le périmètre : seules les corrections y sont admises, jamais de nouveauté.

```bash
git checkout develop && git pull
git checkout -b release/0.2.0
# corrections de dernière minute uniquement
gh pr create --base main --title "release: 0.2.0"    # après fusion :
git tag -a v0.2.0 -m "Semaine 2 — RAG & API v1" && git push origin v0.2.0
gh pr create --base develop --head release/0.2.0     # report des corrections
```

### Correctif urgent

```bash
git checkout main && git pull
git checkout -b hotfix/0.2.1
# correction minimale
gh pr create --base main      # puis report obligatoire vers develop
```

> **Règle d'or :** toute branche `release/*` ou `hotfix/*` fusionnée dans `main`
> doit **aussi** être fusionnée dans `develop`, sinon la correction est perdue
> à la version suivante.

### Versionnage

[SemVer](https://semver.org/lang/fr/) : `MAJEUR.MINEUR.CORRECTIF`.
Sur ce projet d'un mois, une **version mineure par semaine** (`v0.1.0` → `v0.4.0`),
la `v1.0.0` étant posée à la soutenance.

## 5. Commits

[Conventional Commits](https://www.conventionalcommits.org/fr/) avec portée = module :

```
feat(m2): ajoute le re-ranking par cross-encoder
fix(m5): corrige la fuite de connexion Redis sur timeout
docs(m8): complète le registre RGPD
chore(ci): met en cache les dépendances du workflow
```

## 6. Cycle de vie d'une pull request

1. Créer la branche depuis `develop` à jour (ou depuis `main` pour un `hotfix/*`).
2. Ouvrir la PR **en brouillon** dès le premier commit — la visibilité prime sur la perfection.
3. Renseigner le gabarit ([`pull_request_template.md`](../.github/pull_request_template.md)).
4. Passer la PR en « Ready for review » et demander la revue du pilote concerné (colonne **A** de la matrice RACI).
5. Le pilote relit sous **24 h maximum** — planning d'un mois, aucune PR ne doit dormir.
6. Fusion par l'auteur une fois la CI verte et l'approbation obtenue :
   *squash* vers `develop`, **merge commit** vers `main`.

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
| `S1 — Cadrage & socle` → `v0.1.0` | J+7 | Corpus initial, squelette CI/Docker, maquettes, règles RGPD |
| `S2 — RAG & API v1` → `v0.2.0` | J+14 | Index vectoriel, chaîne RAG tracée, API et interface reliées |
| `S3 — Qualité & optimisation` → `v0.3.0` | J+21 | Évaluation RAGAS, citations, cache et streaming, métriques |
| `S4 — Durcissement & livraison` → `v1.0.0` | J+28 | Observabilité, sécurité, tests de charge, déploiement, soutenance |

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

`Settings → Pages → Source: Deploy from a branch → **main** / (root)` —
la page publiée reflète donc toujours la dernière version livrée, jamais `develop`.
Le site étant statique et sans étape de build, il est publié tel quel sur
`https://<organisation>.github.io/<depot>/`.
