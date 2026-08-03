# Équipe, rôles et matrice RACI

CloudMind Group — 8 ingénieurs, 8 modules MLOps.

---

## 1. Convention RACI

| Lettre | Signification | Implication concrète |
|---|---|---|
| **A** | *Accountable* — pilote du module | Responsable unique du livrable, des arbitrages techniques et du respect des seuils de qualité. Une seule personne par module. |
| **C** | *Contributor* — contributeur | Travaille effectivement sur le module, détient une interface technique avec le pilote. |
| **I** | *Informed* — informé | Consulté aux revues de sprint, sans charge de travail directe. |

> Règle d'équipe : **une modification touchant un module doit être validée par son pilote (A).**

## 2. Matrice RACI

| Membre \ Module | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 | Charge |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Douae Moussaoui      | **A** | C | I | C | I | I | I | C | 4 |
| Imane Ibnchakroune   | C | **A** | C | I | C | I | I | I | 4 |
| Amal El Guerdani     | I | C | **A** | C | I | I | C | I | 4 |
| Salma El Ouarrate    | C | I | I | **A** | C | I | C | C | 5 |
| Nouhaila Fadli       | I | C | I | I | **A** | C | C | C | 5 |
| Oumaima Jeraidi      | I | C | I | I | C | **A** | C | I | 4 |
| Youssef El Alem      | C | I | C | C | C | I | **A** | I | 5 |
| Taha Kachmar         | C | I | I | C | C | I | C | **A** | 5 |

Chaque module possède exactement un pilote ; aucun module n'est orphelin et chaque ingénieur
intervient sur 4 à 5 modules, ce qui garantit la continuité en cas d'absence.

## 3. Fiches de rôle

### M1 — Data Pipeline & Preprocessing · Douae Moussaoui

**Rôle :** Data Engineer, pilote du socle de données.
**Mission :** garantir qu'aucun texte juridique n'entre dans le système sans être nettoyé,
segmenté, versionné et contrôlé.

- Connecteurs d'ingestion multi-sources et pipeline OCR
- Nettoyage, dé-duplication, segmentation par articles et alinéas
- Chunking sémantique et génération des embeddings
- Versioning DVC, stockage S3/MinIO, Data Cards
- Tests de qualité de données automatisés dans la CI

**Interfaces :** fournit les datasets à M2 · applique les règles d'anonymisation de M8 ·
conteneurise ses DAG avec M4 · reçoit les jeux de ré-entraînement de M7.

### M2 — Model Engineering & Fine-Tuning · Imane Ibnchakroune

**Rôle :** ML/LLM Engineer, pilote de la modélisation.
**Mission :** transformer un corpus indexé en réponses juridiques exactes et sourcées.

- Retriever hybride, re-ranking, architecture RAG complète
- Indexation Qdrant/ChromaDB, filtres par juridiction
- Ingénierie des prompts, garde-fous anti-hallucination
- Fine-tuning LoRA/QLoRA, optimisation d'inférence

**Interfaces :** consomme les datasets de M1 · publie ses runs dans MLflow avec M3 ·
expose une interface d'inférence stable à M5.

### M3 — Experiment Tracking & Model Registry · Amal El Guerdani

**Rôle :** MLOps Engineer, pilote de l'expérimentation.
**Mission :** rendre chaque résultat reproductible et chaque promotion de modèle justifiable.

- Serveur MLflow partagé, conventions de nommage
- Registre de modèles et gouvernance de promotion
- Suite d'évaluation RAGAS et benchmark « LLM-as-a-judge »
- Rapports de régression automatiques par pull request, Model Cards

**Interfaces :** arbitre la promotion des modèles de M2 · publie les seuils consommés par la CI de M4 ·
alimente les tableaux de bord de M7.

### M4 — CI/CD & Infrastructure · Salma El Ouarrate

**Rôle :** DevOps / Platform Engineer, pilote de la plateforme.
**Mission :** rendre tout déploiement automatique, reproductible et réversible.

- Images Docker multi-stage, pipelines GitHub Actions
- Environnements dev/staging/production, orchestration Kubernetes et Helm
- Infrastructure as Code (Terraform), gestion des secrets
- Déploiement canari, retour arrière automatique, pipeline de ré-entraînement

**Interfaces :** conteneurise M1 et M5 · applique les portes de qualité de M3 ·
intègre les contrôles de sécurité de M8 · déploie l'instrumentation de M7.

### M5 — API & Serving Layer · Nouhaila Fadli

**Rôle :** Backend Engineer, pilote du service.
**Mission :** exposer le modèle de façon rapide, sûre et documentée.

- Endpoints FastAPI asynchrones, streaming SSE
- Authentification JWT/OAuth2, rôles et sessions
- Cache sémantique Redis, file de tâches Celery
- Limitation de débit, documentation OpenAPI, tests de charge

**Interfaces :** encapsule les chaînes d'inférence de M2 · sert le frontend de M6 ·
expose ses métriques à M7 · applique les règles d'accès de M8.

### M6 — UI/UX & Frontend Integration · Oumaima Jeraidi

**Rôle :** Frontend Engineer, pilote de l'expérience utilisateur.
**Mission :** rendre la réponse juridique lisible, vérifiable et exploitable.

- Système de design et maquettes haute-fidélité
- Interface conversationnelle en flux, historique persistant
- Dépôt de documents, affichage des sources citées
- Accessibilité RGAA/WCAG 2.1 AA, internationalisation FR/AR, widget de feedback

**Interfaces :** consomme l'API de M5 · restitue les citations produites par M2 ·
transmet les retours utilisateurs à M7.

### M7 — Model Monitoring & Observability · Youssef El Alem

**Rôle :** SRE / ML Observability, pilote de la supervision.
**Mission :** détecter la dégradation avant l'utilisateur et refermer la boucle.

- Instrumentation Prometheus, tableaux de bord Grafana
- Détection de dérive des données et des embeddings (Evidently)
- Surveillance de la qualité des réponses en production
- Traçage distribué OpenTelemetry, alerting, boucle de rétroaction

**Interfaces :** instrumente M5 et l'infrastructure de M4 · corrèle avec les métriques de M3 ·
renvoie les jeux de ré-entraînement à M1 · fournit les journaux auditables à M8.

### M8 — Security, Governance & Compliance · Taha Kachmar

**Rôle :** Security & Compliance Officer, pilote de la gouvernance.
**Mission :** garantir qu'aucune donnée sensible ne fuite et que le système reste défendable.

- Cartographie des données personnelles, registre RGPD, AIPD
- Anonymisation avant indexation (Presidio)
- Contrôle d'accès par rôles, cloisonnement multi-cabinets, chiffrement
- Journal d'audit immuable, analyse AI Act, documentation d'ensemble

**Interfaces :** définit les règles appliquées par M1 · valide les accès de M5 ·
intègre les scans dans la CI de M4 · audite les journaux de M7.

## 4. Rituels d'équipe

| Rituel | Fréquence | Participants |
|---|---|---|
| Point d'avancement | quotidien, 15 min | toute l'équipe |
| Revue de sprint | bimensuelle | toute l'équipe + référent métier |
| Revue d'architecture | par jalon | pilotes concernés (A) et contributeurs (C) |
| Comité de promotion de modèle | à la demande | M2, M3, M4, M8 |
| Revue de sécurité | mensuelle | M8 + pilotes concernés |
