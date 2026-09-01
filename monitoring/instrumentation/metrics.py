"""Instrumentation Prometheus prête à l'emploi pour l'API de M5.

Ce module est la mise en œuvre de référence du contrat
``docs/OBSERVABILITE.md`` §1. Il existe pour que M5 n'ait pas à réimplémenter
— ni à réinterpréter — le contrat : deux lignes suffisent à instrumenter le
service, et les noms, types, étiquettes et intervalles sont garantis conformes.

Intégration côté M5 (FastAPI) ::

    from monitoring.instrumentation.metrics import instrumenter

    app = FastAPI()
    instrumenter(app)          # expose /metrics et mesure toutes les routes

Instrumentation des étapes internes de la chaîne RAG ::

    from monitoring.instrumentation.metrics import (
        mesurer_recuperation, enregistrer_generation, enregistrer_cache,
    )

    with mesurer_recuperation() as ctx:
        passages = retriever.search(question)
        ctx.documents(len(passages))

    enregistrer_cache(touche=False)
    enregistrer_generation(
        modele="legal-fr-v2", duree=1.4, jetons_prompt=1200, jetons_reponse=310,
    )

Règle de cardinalité (contrat §1.2) : aucune étiquette ne doit contenir un
identifiant d'utilisateur, un identifiant de session ni le texte d'une
question. Le label ``route`` porte le gabarit de route, jamais le chemin
concret — c'est pourquoi l'intergiciel lit ``request.scope["route"].path`` et
non ``request.url.path``.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

if TYPE_CHECKING:  # pragma: no cover - uniquement pour l'analyse statique
    from fastapi import FastAPI

__all__ = [
    "instrumenter",
    "mesurer_recuperation",
    "enregistrer_generation",
    "enregistrer_cache",
    "enregistrer_echec_modele",
    "declarer_version",
]

# --- Intervalles : contrat §1.4 ----------------------------------------------

HTTP_BUCKETS = (0.1, 0.25, 0.5, 1, 2, 2.5, 5, 10)
RETRIEVAL_BUCKETS = (0.01, 0.05, 0.1, 0.12, 0.25, 0.5, 1)
LLM_BUCKETS = (0.25, 0.5, 1, 2, 4, 8, 16)
DOCS_BUCKETS = (1, 2, 4, 8, 12, 16, 24)

# --- Séries : contrat §1.3 ---------------------------------------------------

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Nombre total de requêtes HTTP servies",
    ["method", "route", "status"],
)
HTTP_DUREE = Histogram(
    "http_request_duration_seconds",
    "Durée de traitement d'une requête HTTP",
    ["method", "route"],
    buckets=HTTP_BUCKETS,
)
RAG_DUREE = Histogram(
    "rag_retrieval_duration_seconds",
    "Durée de la phase de récupération",
    buckets=RETRIEVAL_BUCKETS,
)
RAG_DOCUMENTS = Histogram(
    "rag_documents_retrieved",
    "Nombre de passages remontés par requête",
    buckets=DOCS_BUCKETS,
)
LLM_DUREE = Histogram(
    "llm_request_duration_seconds",
    "Durée de génération par le modèle",
    ["model"],
    buckets=LLM_BUCKETS,
)
LLM_JETONS = Counter("llm_tokens_total", "Jetons consommés", ["model", "type"])
LLM_ECHECS = Counter(
    "llm_requests_failed_total", "Échecs de génération", ["model", "reason"]
)
CACHE = Counter(
    "cache_lookups_total", "Consultations du cache sémantique", ["result"]
)
APP_INFO = Gauge(
    "app_info",
    "Version déployée — permet de corréler un incident à une livraison",
    ["version", "commit"],
)


# --- API destinée à M5 -------------------------------------------------------


def declarer_version(version: str, commit: str) -> None:
    """Publie la version déployée, à appeler une fois au démarrage."""
    APP_INFO.labels(version=version, commit=commit).set(1)


class _ContexteRecuperation:
    """Poignée retournée par :func:`mesurer_recuperation`."""

    def __init__(self) -> None:
        self._documents: int | None = None

    def documents(self, nombre: int) -> None:
        """Déclare le nombre de passages remontés."""
        self._documents = nombre


@contextmanager
def mesurer_recuperation() -> Iterator[_ContexteRecuperation]:
    """Mesure la durée de la phase de récupération.

    La durée est enregistrée même si le bloc lève : une récupération qui
    échoue lentement est précisément ce qu'on cherche à voir.
    """
    contexte = _ContexteRecuperation()
    depart = time.perf_counter()
    try:
        yield contexte
    finally:
        RAG_DUREE.observe(time.perf_counter() - depart)
        if contexte._documents is not None:
            RAG_DOCUMENTS.observe(contexte._documents)


def enregistrer_generation(
    modele: str, duree: float, jetons_prompt: int, jetons_reponse: int
) -> None:
    """Enregistre une génération réussie."""
    LLM_DUREE.labels(model=modele).observe(duree)
    LLM_JETONS.labels(model=modele, type="prompt").inc(jetons_prompt)
    LLM_JETONS.labels(model=modele, type="completion").inc(jetons_reponse)


def enregistrer_echec_modele(modele: str, motif: str) -> None:
    """Enregistre un échec de génération.

    ``motif`` doit appartenir à un ensemble fini et court (``timeout``,
    ``rate_limit``, ``invalid_response``…). Ne jamais y passer un message
    d'exception : le cardinal exploserait.
    """
    LLM_ECHECS.labels(model=modele, reason=motif).inc()


def enregistrer_cache(touche: bool) -> None:
    """Enregistre une consultation du cache sémantique."""
    CACHE.labels(result="hit" if touche else "miss").inc()


def instrumenter(app: "FastAPI", chemin: str = "/metrics") -> "FastAPI":
    """Instrumente une application FastAPI et expose l'endpoint de collecte.

    Mesure automatiquement toutes les routes. Les requêtes vers ``chemin``
    lui-même sont exclues : compter la collecte fausserait le débit.
    """
    from fastapi import Request, Response

    @app.middleware("http")
    async def _mesurer(request: "Request", appel_suivant):  # type: ignore[no-untyped-def]
        if request.url.path == chemin:
            return await appel_suivant(request)

        depart = time.perf_counter()
        try:
            reponse = await appel_suivant(request)
            statut = reponse.status_code
        except Exception:
            # Une exception non rattrapée deviendra un 500 pour le client :
            # elle doit apparaître comme telle dans les métriques, sinon le
            # taux d'erreur est sous-estimé.
            statut = 500
            raise
        finally:
            # Gabarit de route et non chemin concret — contrat §1.2.
            portee = request.scope.get("route")
            gabarit = getattr(portee, "path", "inconnue")
            duree = time.perf_counter() - depart
            HTTP_DUREE.labels(request.method, gabarit).observe(duree)
            HTTP_REQUESTS.labels(request.method, gabarit, str(statut)).inc()

        return reponse

    @app.get(chemin, include_in_schema=False)
    async def _metriques() -> "Response":  # type: ignore[no-untyped-def]
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app
