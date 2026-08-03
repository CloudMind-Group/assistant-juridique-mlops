# Assistant Juridique Intelligent — Architecture MLOps

> Tableau de bord de pilotage de **CloudMind Group** : répartition des rôles, architecture MLOps
> de bout en bout, matrice RACI et métriques cibles du projet d'assistant juridique augmenté par IA générative.

![statut](https://img.shields.io/badge/sprint-3%20·%20actif-22d3ee)
![modules](https://img.shields.io/badge/modules-8-6366f1)
![équipe](https://img.shields.io/badge/ingénieurs-8-e879f9)
![dépendances](https://img.shields.io/badge/dépendances-0-34d399)

---

## Sommaire

- [Contexte](#contexte)
- [Aperçu de l'application](#aperçu-de-lapplication)
- [Démarrage rapide](#démarrage-rapide)
- [Structure du dépôt](#structure-du-dépôt)
- [Équipe et modules](#équipe-et-modules)
- [Stack technique du projet](#stack-technique-du-projet)
- [Modifier le contenu](#modifier-le-contenu)
- [Conventions de contribution](#conventions-de-contribution)
- [Documentation](#documentation)

---

## Contexte

Le projet consiste à industrialiser un **assistant juridique intelligent** reposant sur une
architecture **RAG** (Retrieval-Augmented Generation) appliquée à un corpus de textes de loi,
de jurisprudence et de contrats types.

Ce dépôt héberge le **site de pilotage** du projet : une application web autonome, sans dépendance
ni étape de build, qui documente de façon vivante la répartition des tâches entre les huit
ingénieurs de l'équipe, le flux de données MLOps et les objectifs mesurables.

## Aperçu de l'application

| Section | Contenu |
|---|---|
| **En-tête** | Identité de l'équipe, statut du sprint, indicateurs calculés dynamiquement |
| **Matrice des tâches** | 8 cartes membre : module piloté, sous-tâches, outils, contributions transverses, livrables |
| **Matrice RACI** | Croisement membres × modules — un pilote unique (A), des contributeurs identifiés (C) |
| **Stack technique** | Technologies par couche avec responsable désigné |
| **Workflow MLOps** | Flux en 8 étapes, boucle de rétroaction et 3 couloirs transverses |
| **Métriques & SLO** | Qualité du modèle, latence, conformité, volumétrie, feuille de route |
| **Livrables** | Les 8 artefacts conditionnant la clôture du projet |

Fonctionnalités : thème sombre/clair persistant, vues **Grille** et **Kanban**, recherche plein-texte
multi-mots, filtres par membre et par statut, accordéons, export PDF, raccourcis clavier
(`/` pour rechercher, `Échap` pour effacer), animations respectant `prefers-reduced-motion`.

## Démarrage rapide

Aucune installation, aucun gestionnaire de paquets, aucune compilation.

```bash
git clone <url-du-depot>
cd assistant-juridique-mlops
```

**Option 1 — ouverture directe :** double-cliquez sur `index.html`.
Tout fonctionne en `file://` (scripts classiques, sprite SVG inline).

**Option 2 — serveur local (recommandé pour le développement) :**

```bash
python -m http.server 8000
# puis http://localhost:8000
```

> Les polices sont chargées depuis Google Fonts. Hors connexion, la page bascule
> automatiquement sur les polices système sans perte de mise en page.

## Structure du dépôt

```
.
├── index.html                 # Structure sémantique + sprite SVG (aucune logique)
├── assets/
│   ├── css/
│   │   ├── tokens.css         # Variables de design : couleurs, thèmes, typographie, rayons
│   │   ├── base.css           # Reset, typographie, primitives, utilitaires, feuille d'impression
│   │   ├── components.css     # Barre de navigation, hero, filtres, cartes, kanban
│   │   └── sections.css       # Diagramme de workflow, tableau de bord, RACI, pied de page
│   └── js/
│       ├── data.js            # Source de vérité : membres, modules, RACI, métriques
│       ├── render.js          # Fonctions pures données -> HTML (aucun effet de bord)
│       └── app.js             # État, filtrage, événements, animations
├── docs/
│   ├── ARCHITECTURE.md        # Architecture MLOps détaillée, flux et décisions
│   └── TEAM.md                # Rôles, périmètres et matrice RACI complète
├── .editorconfig
├── .gitignore
├── LICENSE
└── README.md
```

**Principe de séparation :** `data.js` contient l'information métier, `render.js` la transforme en
HTML sans jamais toucher au DOM, `app.js` orchestre l'état et les événements. Modifier le contenu
du projet ne demande donc de toucher **qu'un seul fichier**.

## Équipe et modules

| Module | Périmètre | Pilote (A) | Statut |
|---|---|---|---|
| **M1** | Data Pipeline & Preprocessing | Douae Moussaoui | Terminé — 100 % |
| **M2** | Model Engineering & Fine-Tuning | Imane Ibnchakroune | En cours — 78 % |
| **M3** | Experiment Tracking & Model Registry | Amal El Guerdani | En cours — 72 % |
| **M4** | CI/CD & Infrastructure | Salma El Ouarrate | En cours — 65 % |
| **M5** | API & Serving Layer | Nouhaila Fadli | En cours — 70 % |
| **M6** | UI/UX & Frontend Integration | Oumaima Jeraidi | En cours — 58 % |
| **M7** | Model Monitoring & Observability | Youssef El Alem | Planifié — 34 % |
| **M8** | Security, Governance & Compliance | Taha Kachmar | Planifié — 30 % |

Chaque membre pilote un module **et** contribue à trois ou quatre modules adjacents.
Le détail des interfaces figure dans [`docs/TEAM.md`](docs/TEAM.md).

## Stack technique du projet

| Couche | Technologies |
|---|---|
| Données & ingestion | Airflow · DVC · Pandas · Tesseract · MinIO |
| Vectorisation & RAG | Qdrant · ChromaDB · LangChain · LlamaIndex |
| Modélisation | Hugging Face · PyTorch · PEFT/LoRA |
| Expérimentation | MLflow · RAGAS · Optuna |
| CI/CD & infrastructure | Docker · GitHub Actions · Kubernetes · Terraform |
| Serving & API | FastAPI · Redis · Celery · PostgreSQL |
| Frontend | React · Next.js · TypeScript · Tailwind CSS |
| Observabilité | Prometheus · Grafana · Evidently · OpenTelemetry |
| Sécurité & gouvernance | Presidio · Vault · OPA · Trivy · MkDocs |

## Modifier le contenu

Tout le contenu éditorial vit dans [`assets/js/data.js`](assets/js/data.js).

**Faire évoluer l'avancement d'un module :**

```js
// assets/js/data.js
{
  id:'M7', name:'Youssef El Alem', /* ... */
  status:'progress',   // 'done' | 'progress' | 'planned'
  progress:55,         // 0-100 — les indicateurs globaux se recalculent seuls
  subs:[
    ['Instrumentation Prometheus : latence, débit, taux d\'erreur', 1],  // 1 = terminé
    ['Détection de dérive des embeddings (Evidently)', 0],               // 0 = à faire
  ]
}
```

Les KPI de l'en-tête, la jauge d'avancement global, les compteurs par statut et les colonnes du
Kanban sont **dérivés** de ces valeurs : aucune donnée n'est dupliquée dans le HTML.

**Ajuster les rôles transverses :** modifiez l'objet `SUPPORTS` en bas de `data.js`.
La matrice RACI et le bloc « rôle transverse » de chaque carte se régénèrent automatiquement.

## Conventions de contribution

- **Branches :** `feat/<module>-<sujet>`, `fix/<sujet>`, `docs/<sujet>` — par exemple `feat/m7-drift-dashboard`.
- **Commits :** [Conventional Commits](https://www.conventionalcommits.org/fr/) — `feat:`, `fix:`, `docs:`, `style:`, `refactor:`, `chore:`.
- **Revue :** toute modification de `data.js` touchant un module doit être validée par son pilote (colonne A de la matrice RACI).
- **Style :** 2 espaces d'indentation, UTF-8, fins de ligne LF — appliqués par `.editorconfig`.
- **Zéro dépendance :** aucune bibliothèque externe ni étape de build ne doit être introduite sans décision d'équipe.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture MLOps, flux de données, décisions techniques.
- [`docs/TEAM.md`](docs/TEAM.md) — rôles détaillés, matrice RACI et interfaces entre modules.

---

<sub>© 2026 CloudMind Group — Document interne de pilotage projet.</sub>
