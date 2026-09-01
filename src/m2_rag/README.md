# M2 — Model Engineering / RAG & Fine-Tuning

Owner: **Imane Ibnchakroune**. M2 transforme les documents propres produits
par M1 en passages retrouvables et expose une interface Python stable à M5.

## État réellement livré

- chargement et validation du contrat M1 ;
- chunking juridique déterministe, cible 512 tokens et overlap 64 ;
- embeddings injectables, avec `BAAI/bge-m3` comme configuration initiale ;
- index exact en mémoire pour tests/mode léger et backend Qdrant ;
- upsert stable et suppression Qdrant ciblée par filtre payload `doc_id` ;
- retrieval BM25 + dense, fusion RRF, reranker optionnel ;
- prompts versionnés, citations dérivées des passages récupérés et refus des
  générations sans citation autorisée ;
- interface `RAGService` destinée à M5 ;
- hooks optionnels destinés à M3, sans import MLflow ;
- contrats d'évaluation et de préparation LoRA/QLoRA.

Ce module ne contient ni serveur FastAPI, ni intégration MLflow, ni poids de
modèle, ni entraînement réalisé.

## Contrat M1 → M2 et contradiction documentaire

Le contrat exécutable actuel est :

```text
data/processed/documents/<doc_id>.txt
data/processed/metadata.jsonl
data/processed/ingestion_report.json
data/processed/quality_report.json
```

Chaque texte est un document complet déjà extrait, nettoyé, anonymisé et
validé. M2 ne lit jamais `data/raw` et traite `doc_id` comme une valeur opaque.

`docs/ARCHITECTURE.md` et `docs/TEAM.md` attribuent historiquement le chunking
à M1. Le README M1 et ses sorties réelles livrent au contraire des documents
complets et demandent à M2 de les chunker. Pour ce contrat, le chunking est donc
réalisé dans M2. La documentation transverse devra être alignée avec les
responsables concernés ; elle n'a pas été modifiée ici.

Les seuls filtres publics acceptés sont les champs réellement disponibles :
`doc_id`, `source`, `date`, `category`, `language`. M2 ne fabrique pas de
`jurisdiction` ou `effective_date`.

## Chunking et identifiants

Le chunker reconnaît notamment `Article`, `Section`, `Chapitre`, `Titre` et
leurs équivalents arabes `المادة`, `القسم`, `الفصل`, `الباب`. Il préfère ces
frontières puis applique une fenêtre contrôlée aux sections trop longues.

La configuration par défaut est `512/64`, version `legal-v1`. En CI, « token »
désigne le proxy déterministe séparé par espaces. En production, un tokenizer
du modèle peut être injecté afin que les limites correspondent aux vrais tokens
de l'embedder. Le `chunk_id` est un SHA-256 déterministe de la version du
chunker, du `doc_id`, de la position, de la section et du texte normalisés.

## Embeddings et Qdrant

`BAAI/bge-m3` est le choix initial configurable : modèle multilingue et vecteur
1024 natif. Ce choix n'est pas considéré comme supérieur pour le français et
l'arabe tant qu'un benchmark représentatif n'existe pas. La collection par
défaut est `legal_fr_1024`, mais sa dimension est toujours obtenue depuis
l'embedder actif ; M2 ne complète ni ne tronque artificiellement un vecteur.

Les tests utilisent `DeterministicFakeEmbedder` et ne téléchargent aucun poids.
Le modèle réel n'est chargé que lors de l'instanciation explicite de
`SentenceTransformerEmbedder`.

Chaque point Qdrant conserve `doc_id` dans son payload. L'effacement appelle
`delete_document(doc_id)`, qui envoie un `FilterSelector` sur ce champ sans
recréer la collection. Un index payload keyword est créé pour `doc_id`.

## Retrieval et génération

Le pipeline est :

```text
question → BM25 + dense → RRF → candidate_k
         → cross-encoder optionnel → top_k → génération
```

RRF fusionne les rangs et ne compare jamais directement les scores BM25 et
cosinus. `candidate_k`, `top_k`, les deux poids, la constante RRF, le modèle et
l'activation du reranker sont configurables. Le reranker est désactivé par
défaut afin que le mode CPU/light reste utilisable.

Le générateur doit retourner le texte et les `chunk_id` cités séparément. M2
rejette une réponse sans citation ou citant un identifiant absent du contexte.
Ce contrôle empêche une référence libre non récupérée ; il ne constitue pas à
lui seul une preuve logique parfaite que chaque phrase est soutenue par le
passage. Toute réponse rappelle qu'il ne s'agit pas d'un conseil juridique.

## Interface M5

```python
from src.m2_rag import RAGRequest, RAGService

response = service.query(RAGRequest(
    question="Que prévoit l'article récupéré ?",
    filters={"language": "fr"},
))

print(response.answer)
print(response.citations)
print(response.retrieved_chunks)
print(response.prompt_version, response.model_version, response.latencies)
```

M5 injecte le générateur/LLM et n'a pas besoin de connaître les détails BM25 ou
Qdrant. Aucune clé API n'est lue ou stockée par M2.

## Interface M3

`tracking.experiment_parameters()` expose modèle/dimension d'embedding,
chunking, retrieval, top-k, reranker, prompt et LLM. Un objet conforme à
`TrackingHook` peut recevoir paramètres, métriques et requêtes. L'absence de
hook est un fonctionnement normal ; M2 n'importe jamais MLflow.

## Évaluation et fine-tuning

`evaluation.recall_at_k()` refuse de calculer Recall@k sans exemples annotés.
Le dépôt ne contient aucune ground truth : **Recall@8 n'est donc pas mesuré et
la cible ≥ 0,89 n'est pas déclarée atteinte**.

Les rapports de latence indiquent système/Python, backend, taille du corpus et
nombre de runs. Une mesure sur le backend mémoire et les 60 documents
synthétiques n'est pas une mesure Qdrant de production.

`finetuning/` valide seulement le format d'un futur dataset QA sourcé et une
configuration LoRA/QLoRA. Aucun dataset annoté réel n'existe : **aucun modèle
n'a été entraîné**.

## Limitation critique du corpus arabe

L'audit a observé des passages arabes ordinaires remplacés par `[NOM]`, ce qui
indique un faux positif possible de l'anonymisation M1. M2 ne corrige pas M1.
Aucune conclusion sérieuse sur les performances FR/AR ne doit être tirée de ce
corpus avant validation/correction par M1 et Sécurité.

## Installation et commandes

Socle et tests :

```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -q
```

Backend Qdrant M2, optionnel :

```bash
python -m pip install -r requirements-m2.txt
```

Validation et statistiques locales, sans embedding lourd :

```bash
python -m src.m2_rag.cli validate-corpus
python -m src.m2_rag.cli chunk-stats --chunk-size 512 --chunk-overlap 64
```

Ces commandes lisent `data/processed` sans exécuter ni modifier le pipeline DVC.

## Clôture technique — état vérifié le 2026-09-01

| Classe | Composants | Preuve ou limite |
|---|---|---|
| A — opérationnel et testé | corpus, chunking FR/AR long, embeddings déterministes, index mémoire, BM25, dense, RRF, reranker léger, scope guard injectable, prompts, citations, grounding structurel, `RAGService`, évaluation artificielle, tracking M3, validation/split fine-tuning, CLI | tests et smoke M1 complet |
| A — intégration réelle | Qdrant local : collection, dimension, upsert, query, filtres `doc_id/language/category/source`, suppression ciblée | `qdrant-client 1.19.0`, sans serveur ni Docker |
| B — adapter testé sans poids | `SentenceTransformerEmbedder`, `CrossEncoderReranker`, `TransformersGenerator` | doubles injectés ; runtime réel importé |
| C — préparé | LLM juridique configurable, vérification sémantique/NLI future, LoRA/QLoRA | aucun choix ou entraînement ne peut être justifié sans données |
| D — externe | benchmark annoté, validation juridique, correction arabe M1, serveur Qdrant de production, poids BGE-M3/reranker | ressources externes détaillées ci-dessous |

Le téléchargement de `BAAI/bge-m3` et du reranker multilingue
`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` a été tenté sans jeton. Le Hub a
créé les métadonnées, mais les poids sont restés à 0 octet avec avertissement de
requêtes non authentifiées ; Xet et HTTP standard ont été essayés. La machine
est CPU-only (`torch 2.13.0+cpu`, CUDA indisponible). Aucun cache n'est committé.
BGE-M3 n'est donc pas déclaré exécuté et sa dimension attendue de 1024 n'est pas
présentée comme une mesure locale.

### Grounding, scope et contrat M5

Le prompt exige un JSON `{"answer": ..., "citation_ids": [...]}` et des
marqueurs visibles `[chunk_id:IDENTIFIANT]`. Le service refuse le contexte vide,
les citations absentes, inconnues ou non récupérées, et tout désaccord entre la
liste et les marqueurs. Cela prouve la provenance structurelle, pas l'entailment
sémantique de chaque phrase. Un vérificateur NLI pourra être injecté plus tard.

`KeywordScopeGuard` est une baseline FR/AR remplaçable, fondée sur des tokens ;
ce n'est pas un classifieur juridique fiable. Une requête hors domaine ou une
recherche sans passage est refusée. `TransformersGenerator` charge un pipeline
Hugging Face local configurable et `CallableGenerator` accepte un provider
externe, sans changement de `RAGService` et sans secret dans M2.

Exemple minimal exécutable :

```python
from src.m2_rag import RAGRequest, build_light_service
from src.m2_rag.corpus import load_m1_corpus

service = build_light_service(load_m1_corpus())
response = service.query(RAGRequest("Quelle règle de droit est décrite ?"))
print(response.answer, response.citations, response.refused)
```

`RAGResponse` fournit `answer`, `citations`, `retrieved_chunks`,
`prompt_version`, `model_version`, `latencies`, `refused` et `refusal_reason`.
Une citation publique utilise uniquement `doc_id`, `chunk_id`, `title`,
`source`, `date`, `category` et `language` (plus extrait/score). `file_path`
reste interne. M2 n'invente jamais juridiction, date d'effet, numéro d'article
ou numéro de décision.

### Installation, commandes et mesures

Le socle léger est dans `requirements.txt`. Qdrant est séparé dans
`requirements-m2.txt`, et le runtime lourd dans
`requirements-m2-models.txt` :

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-m2.txt
python -m pip install -r requirements-m2-models.txt
python -m src.m2_rag.cli validate-corpus
python -m src.m2_rag.cli chunk-stats --chunk-size 512 --chunk-overlap 64
python -m src.m2_rag.cli smoke-light
python -m src.m2_rag.cli smoke-qdrant-local
python -m pytest tests/m2 -q
```

L'installation du runtime lourd ne télécharge pas de poids. Les rapports de
latence exposent runs, min, moyenne, P50, P95, backend, embedder, corpus, chunks
et environnement. DEV TEST mesuré sur Qdrant in-memory, embedder déterministe,
60 chunks synthétiques M1, Windows 10/Python 3.12.5, 5 runs : min 1,257 ms,
moyenne 1,324 ms, P50 1,296 ms, P95 1,477 ms. Ce résultat indicatif ne valide
aucun SLO de production.

`experiment_parameters()` expose modèle/dimension d'embedding, taille/overlap,
`chunker_version`, méthode, top-k/candidate-k, reranker, prompt, LLM, latences et
métriques disponibles. M2 reste totalement fonctionnel sans MLflow.

Recall@k est testé sur de petites fixtures artificielles, y compris plusieurs
pertinents et zéro résultat : c'est un **DEV TEST**, jamais un **BENCHMARK
OFFICIEL**. Recall@8 ≥ 0,89 reste une cible non validée.

### Dépendances externes exhaustives

- **BGE-M3 et reranker réel** : transfert de poids Hub bloqué et machine
  CPU-only ; nécessite un accès Hugging Face fonctionnel ou cache préchargé,
  bande passante/espace et calcul validés par l'infrastructure/M4.
- **Qualité retrieval / Recall@8** : nécessite un benchmark QA annoté, des
  jugements de pertinence doc/chunk et des experts juridiques ; M2 ne fabrique
  aucune ground truth.
- **Fine-tuning LoRA/QLoRA** : nécessite un dataset QA sourcé et approuvé, des
  ressources GPU et le tracking convenu avec M3/M4. **Not trained — annotated
  dataset unavailable.**
- **LLM juridique de production** : nécessite décision de modèle/provider,
  licence, ressources ou credentials gérés hors M2, et validation juridique et
  sécurité. L'interface injectable est terminée.
- **Corpus arabe** : nécessite validation/correction par M1 et Sécurité du faux
  positif probable d'anonymisation. Cela ne bloque pas le développement
  technique, mais invalide une évaluation sérieuse FR/AR.
- **Qdrant serveur** : le client local est validé ; persistance, capacité,
  disponibilité, observabilité et SLO relèvent de M4. L'index payload local
  avertit normalement qu'il n'a d'effet que sur un serveur.
- **MLflow, API et UI** : relèvent de M3, M5 et des modules de serving/UI ; M2
  fournit leurs contrats sans les implémenter.
