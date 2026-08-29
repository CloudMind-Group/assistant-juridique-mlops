# Architecture MLOps — Assistant Juridique Intelligent

Document de référence technique. Décrit le cycle de vie complet, du corpus juridique brut
jusqu'à la réponse supervisée en production.

---

## 1. Vue d'ensemble

```
                    ┌──────────────────────────────────────────────┐
                    │        COUCHES TRANSVERSES (M7 · M8)         │
                    │  Observabilité · Sécurité · Automatisation   │
                    └──────────────────────────────────────────────┘
                                       ▲
   ┌────────┐   ┌──────────┐   ┌───────┴────┐   ┌──────────┐   ┌──────────┐
   │ 01 M1  │──▶│  02 M1   │──▶│  03 M2     │──▶│ 04 M2    │──▶│ 05 M3    │
   │Ingest. │   │Nettoyage │   │Embeddings  │   │RAG +     │   │Tracking  │
   │ + OCR  │   │+ Chunking│   │+ Index     │   │Fine-tune │   │+ Registry│
   └────────┘   └──────────┘   └────────────┘   └──────────┘   └────┬─────┘
                                                                     │
   ┌──────────┐   ┌──────────┐   ┌──────────┐                        ▼
   │ 08 M6    │◀──│ 07 M5    │◀──│ 06 M4    │◀───────────────────────┘
   │Interface │   │API &     │   │CI/CD &   │
   │+ Feedback│   │Serving   │   │Build     │
   └────┬─────┘   └──────────┘   └──────────┘
        │
        └──────────── boucle de rétroaction ──────────▶ retour en 01/03/04
```

## 2. Étapes du pipeline

### 01 — Ingestion & OCR · *M1, Douae Moussaoui*

Collecte multi-sources (portails officiels, dépôts internes PDF/DOCX), extraction du texte,
OCR des documents scannés avec correction orthographique adaptée au vocabulaire juridique.

**Outils :** Apache Airflow, Tesseract/PaddleOCR, DAGsHub (remote DVC)
**Sortie :** documents bruts normalisés, horodatés et tracés

### 02 — Nettoyage, chunking & versioning · *M1, Douae Moussaoui*

Suppression des en-têtes et pieds de page, dé-duplication, segmentation par articles et alinéas,
découpage sémantique en fragments de 512 tokens avec chevauchement de 64. Chaque jeu de données
est versionné avec DVC et accompagné d'une *Data Card*.

**Contrôle qualité :** Great Expectations, exécuté dans la CI — un jeu non conforme bloque la chaîne.
**Sortie :** dataset versionné `v1..v14`, prêt à vectoriser

### 03 — Embeddings & indexation vectorielle · *M2, Imane Ibnchakroune*

Vectorisation par modèle d'embedding multilingue (FR/AR, dimension 1024) et indexation HNSW
avec filtres par juridiction, type de texte et date d'entrée en vigueur.

**Sortie :** collection Qdrant `legal_fr_1024`, ~1,9 M de vecteurs

### 04 — RAG & fine-tuning · *M2, Imane Ibnchakroune*

Retriever hybride (BM25 lexical + recherche dense) suivi d'un re-ranking par cross-encoder,
puis génération encadrée par des prompts système imposant la citation systématique des sources
et le refus explicite hors périmètre. Adaptation du modèle par LoRA/QLoRA sur corpus annoté.

**Garde-fou :** toute réponse non ancrée dans un passage récupéré est rejetée avant restitution.

### 05 — Suivi d'expérimentation & registre · *M3, Amal El Guerdani*

Chaque itération est tracée dans MLflow (paramètres, métriques, artefacts). L'évaluation combine
métriques RAGAS (fidélité, pertinence du contexte) et un juge automatique sur 1 200 questions
annotées par des experts métier.

**Promotion :** `Staging → Production` sous double validation, avec Model Card obligatoire.

### 06 — CI/CD & build · *M4, Salma El Ouarrate*

Lint, tests unitaires et d'intégration, analyse de vulnérabilités (Trivy, Bandit), construction
d'images Docker multi-stage, publication au registre, déploiement Helm progressif de type canari
avec retour arrière automatique sur échec des sondes de santé.

**Portes de qualité :** les seuils publiés par M3 conditionnent le passage en production.

### 07 — API & serving · *M5, Nouhaila Fadli*

Service FastAPI asynchrone : requêtes conversationnelles, dépôt de documents, streaming SSE
jeton par jeton, cache sémantique Redis, authentification JWT/OAuth2, limitation de débit et
traitement asynchrone des documents volumineux via Celery.

### 08 — Interface & feedback · *M6, Oumaima Jeraidi*

Interface conversationnelle avec rendu en flux, dépôt documentaire, affichage des sources citées
renvoyant à l'extrait exact du texte de loi, tableau de bord utilisateur et widget de retour
alimentant directement la boucle d'amélioration.

## 3. Couches transverses

### Observabilité · *M7, Youssef El Alem*

Instrumentation Prometheus (latence, débit, taux d'erreur, consommation de jetons), tableaux de
bord Grafana par domaine, traçage distribué OpenTelemetry sur l'ensemble de la chaîne RAG,
détection de dérive des données et des embeddings avec Evidently, alerting routé vers Slack.

### Sécurité & gouvernance · *M8, Taha Kachmar*

Anonymisation des données personnelles avant indexation (Presidio), contrôle d'accès par rôles
et cloisonnement multi-cabinets, chiffrement au repos et en transit, journal d'audit immuable,
registre RGPD et analyse de risque au titre de l'AI Act.

### Automatisation MLOps · *M4, Salma El Ouarrate*

Orchestration, reproductibilité et déclenchement du ré-entraînement à partir des signaux de
production remontés par M7.

## 4. Boucle de rétroaction

1. Les retours utilisateurs (pouce haut/bas + commentaire) sont collectés par l'interface (M6).
2. Les alertes de dérive et les échantillons de faible qualité sont remontés par la supervision (M7).
3. Les cas problématiques sont re-labellisés et réinjectés dans le corpus (M1).
4. Le contenu concerné est ré-indexé (M2), une nouvelle expérimentation est lancée (M3).
5. Après validation des seuils, le déploiement est automatisé (M4).

Fenêtre cible entre la détection d'une dérive et le déploiement correctif : **moins de 24 heures**.

## 5. Décisions d'architecture

| Décision | Choix retenu | Justification |
|---|---|---|
| Base vectorielle | Qdrant (ChromaDB en local) | Filtrage par métadonnées natif, indispensable au cloisonnement par juridiction |
| Stratégie de chunking | Sémantique par article, 512/64 | La structure juridique porte le sens : découper au milieu d'un article détruit la citation |
| Adaptation du modèle | LoRA/QLoRA plutôt qu'un entraînement complet | Coût et empreinte mémoire réduits, itérations rapides, retour arrière trivial |
| Récupération | Hybride BM25 + dense | Les références légales exactes (« article 1134 ») échouent en recherche purement dense |
| Serving | FastAPI + SSE | Génération asynchrone et restitution progressive perçue comme instantanée |
| Cache | Redis sémantique | Forte récurrence des questions juridiques courantes, taux de cache visé ≥ 35 % |
| Ancrage des réponses | Citation obligatoire | Exigence métier : une réponse juridique non sourcée est inexploitable |

## 6. Objectifs mesurables

| Indicateur | Cible | Responsable |
|---|---|---|
| Exactitude des réponses (juge expert) | ≥ 92 % | M3 |
| Fidélité aux sources (RAGAS) | ≥ 0,94 | M3 |
| Rappel du contexte — Recall@8 | ≥ 0,89 | M2 |
| Latence P95 (réponse complète) | < 2,5 s | M5 |
| Latence P50 (recherche vectorielle) | < 120 ms | M2 |
| Débit soutenu | 80 req/s | M5 |
| Disponibilité mensuelle | 99,5 % | M4 |
| Taux d'hallucination | < 3 % | M3 |
| Rappel d'anonymisation PII | ≥ 98 % | M8 |
| Couverture de tests | ≥ 85 % | M4 |
| Détection de dérive | < 24 h | M7 |

## 7. Feuille de route

**Contrainte : le projet doit être livré en un mois.** Les huit modules avancent donc en
parallèle, avec des jalons hebdomadaires fermes.

| Semaine | Périmètre | Modules actifs | État |
|---|---|---|---|
| **S1** | Cadrage, corpus initial, squelette CI/Docker, maquettes, règles RGPD | M1 · M2 · M4 · M6 · M8 | En cours |
| **S2** | Index vectoriel, RAG v1 tracée dans MLflow, API et interface reliées | M1 · M2 · M3 · M4 · M5 · M6 · M8 | Planifié |
| **S3** | Évaluation RAGAS, citations, cache et streaming, premières métriques | M2 · M3 · M4 · M5 · M6 · M7 · M8 | Planifié |
| **S4** | Observabilité, sécurité, tests de charge, déploiement, soutenance | M3 · M4 · M6 · M7 · M8 | Planifié |

### Chemin critique

`M1 (corpus) → M2 (index + RAG) → M5 (API) → M6 (interface)`

Tout retard sur M1 en semaine 1 décale mécaniquement la démonstration de bout en bout.
M1 livre donc un **corpus réduit mais complet** dès J+4 pour débloquer M2, puis enrichit
le volume en semaine 2.
