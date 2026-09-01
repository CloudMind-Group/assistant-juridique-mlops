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

Backends/modèles M2 de production, optionnels :

```bash
python -m pip install -r requirements-m2.txt
```

Validation et statistiques locales, sans embedding lourd :

```bash
python -m src.m2_rag.cli validate-corpus
python -m src.m2_rag.cli chunk-stats --chunk-size 512 --chunk-overlap 64
```

Ces commandes lisent `data/processed` sans exécuter ni modifier le pipeline DVC.
