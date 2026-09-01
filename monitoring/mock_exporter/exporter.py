"""Simulateur de métriques conforme au contrat M5 → M7.

Ce module n'est pas une décoration de démonstration : il applique à la lettre
le contrat défini dans ``docs/OBSERVABILITE.md`` §1.3 — mêmes noms, mêmes
types, mêmes étiquettes, mêmes intervalles d'histogramme. Il sert à deux
choses tant que l'API de M5 n'existe pas :

1. vérifier que la pile d'observabilité fonctionne de bout en bout
   (collecte → règles d'alerte → tableaux de bord) ;
2. servir de référence exécutable : si l'implémentation de M5 diverge du
   contrat, la comparaison avec ce fichier tranche.

Le jour où M5 expose ``/metrics``, ce service est simplement retiré du
``docker-compose.yml``.

Lancement :
    python -m monitoring.mock_exporter.exporter
    ou :  docker compose up mock-exporter
"""

from __future__ import annotations

import logging
import os
import random
import time

from prometheus_client import Counter, Gauge, Histogram, start_http_server

# --- Intervalles : identiques au contrat §1.4 --------------------------------

HTTP_BUCKETS = (0.1, 0.25, 0.5, 1, 2, 2.5, 5, 10)
RETRIEVAL_BUCKETS = (0.01, 0.05, 0.1, 0.12, 0.25, 0.5, 1)
LLM_BUCKETS = (0.25, 0.5, 1, 2, 4, 8, 16)
DOCS_BUCKETS = (1, 2, 4, 8, 12, 16, 24)

# --- Séries : identiques au contrat §1.3 -------------------------------------

http_requests_total = Counter(
    "http_requests_total",
    "Nombre total de requêtes HTTP servies",
    ["method", "route", "status"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Durée de traitement d'une requête HTTP",
    ["method", "route"],
    buckets=HTTP_BUCKETS,
)
rag_retrieval_duration_seconds = Histogram(
    "rag_retrieval_duration_seconds",
    "Durée de la phase de récupération",
    buckets=RETRIEVAL_BUCKETS,
)
rag_documents_retrieved = Histogram(
    "rag_documents_retrieved",
    "Nombre de passages remontés par requête",
    buckets=DOCS_BUCKETS,
)
llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "Durée de génération par le modèle",
    ["model"],
    buckets=LLM_BUCKETS,
)
llm_tokens_total = Counter(
    "llm_tokens_total",
    "Jetons consommés",
    ["model", "type"],
)
llm_requests_failed_total = Counter(
    "llm_requests_failed_total",
    "Échecs de génération",
    ["model", "reason"],
)
cache_lookups_total = Counter(
    "cache_lookups_total",
    "Consultations du cache sémantique",
    ["result"],
)
app_info = Gauge(
    "app_info",
    "Version déployée — permet de corréler un incident à une livraison",
    ["version", "commit"],
)

# --- Profil de trafic simulé -------------------------------------------------

ROUTES = ("/v1/ask", "/v1/documents", "/v1/health")
MODEL = "legal-fr-v2"

# `random` suffit ici : ces valeurs alimentent un simulateur, elles n'ont
# aucun usage cryptographique.
_rng = random.Random(20260830)


def _une_requete() -> None:
    """Simule une requête complète et met à jour toutes les séries."""
    route = _rng.choices(ROUTES, weights=(70, 20, 10))[0]

    if route == "/v1/health":
        http_request_duration_seconds.labels("GET", route).observe(
            _rng.uniform(0.001, 0.01)
        )
        http_requests_total.labels("GET", route, "200").inc()
        return

    # Récupération.
    retrieval = _rng.gauss(0.09, 0.03)
    retrieval = max(retrieval, 0.005)
    rag_retrieval_duration_seconds.observe(retrieval)
    rag_documents_retrieved.observe(_rng.randint(4, 16))

    # Cache : environ 40 % de succès, au-dessus de l'objectif de 35 %.
    touche = _rng.random() < 0.40
    cache_lookups_total.labels("hit" if touche else "miss").inc()

    # Génération — court-circuitée en cas de succès du cache.
    generation = 0.02 if touche else max(_rng.gauss(1.4, 0.6), 0.1)
    if not touche:
        llm_request_duration_seconds.labels(MODEL).observe(generation)
        llm_tokens_total.labels(MODEL, "prompt").inc(_rng.randint(600, 2400))
        llm_tokens_total.labels(MODEL, "completion").inc(_rng.randint(80, 600))

    # Répartition des statuts : environ 0,5 % d'erreurs serveur, donc sous le
    # seuil d'alerte de 1 % — la pile doit rester silencieuse au repos.
    tirage = _rng.random()
    if tirage < 0.005:
        statut = "500"
        llm_requests_failed_total.labels(MODEL, "timeout").inc()
    elif tirage < 0.02:
        statut = "422"
    else:
        statut = "200"

    http_request_duration_seconds.labels("POST", route).observe(
        retrieval + generation + _rng.uniform(0.01, 0.08)
    )
    http_requests_total.labels("POST", route, statut).inc()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    port = int(os.environ.get("PORT", "8000"))
    # Écoute sur toutes les interfaces : obligatoire pour être joignable
    # depuis le réseau Docker. Le service n'est pas exposé hors de ce réseau.
    adresse = os.environ.get("BIND_ADDR", "0.0.0.0")  # nosec B104

    app_info.labels(version="0.2.0-mock", commit="local").set(1)
    start_http_server(port, addr=adresse)
    # Message volontairement en ASCII : la console Windows utilise cp1252 par
    # defaut et leve UnicodeEncodeError sur un caractere hors de cette table.
    logging.info("Simulateur de metriques M5 sur http://%s:%s/metrics", adresse, port)

    while True:
        for _ in range(_rng.randint(2, 8)):
            _une_requete()
        time.sleep(1)


if __name__ == "__main__":
    main()
