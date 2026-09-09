"""Squelette de traçage distribué OpenTelemetry.

Objectif : que l'activation du traçage côté M5 tienne en une ligne, le jour où
l'API existera, sans que Nouhaila ait à apprendre OpenTelemetry.

    from monitoring.instrumentation.tracing import activer_tracage

    app = FastAPI()
    activer_tracage(app, service="assistant-api")

Le module est volontairement inerte tant qu'aucun collecteur n'est configuré :
sans la variable ``OTEL_EXPORTER_OTLP_ENDPOINT``, les traces sont produites en
mémoire et jetées. Cela permet d'appeler ``activer_tracage`` dès maintenant
sans dépendre du déploiement d'un collecteur par M4.

Le champ ``trace_id`` du journal d'audit (contrat §2.2) provient d'ici : c'est
lui qui permet de relier un événement d'audit à la trace technique
correspondante sans stocker le contenu de la requête.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import FastAPI

__all__ = ["activer_tracage", "identifiant_trace_courant"]

_logger = logging.getLogger(__name__)

# Étapes de la chaîne RAG à tracer, dans l'ordre. Utiliser ces noms tels quels
# des deux côtés : une trace n'a de valeur que si ses segments sont nommés de
# façon stable d'un service à l'autre.
SEGMENTS = ("rag.retrieve", "rag.rerank", "rag.generate", "rag.cite")


def activer_tracage(app: "FastAPI", service: str, version: str = "0.0.0") -> bool:
    """Active le traçage distribué sur une application FastAPI.

    Retourne ``True`` si le traçage est réellement actif, ``False`` si les
    dépendances OpenTelemetry sont absentes ou si aucun collecteur n'est
    configuré. Ne lève jamais : l'observabilité ne doit pas être une cause de
    panne du service qu'elle observe.
    """
    point_de_collecte = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not point_de_collecte:
        _logger.info(
            "Traçage inactif : OTEL_EXPORTER_OTLP_ENDPOINT n'est pas défini."
        )
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        _logger.warning(
            "Traçage inactif : dépendances OpenTelemetry absentes. "
            "Installer opentelemetry-sdk, opentelemetry-exporter-otlp-proto-http "
            "et opentelemetry-instrumentation-fastapi."
        )
        return False

    fournisseur = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service,
                "service.version": version,
                "deployment.environment": os.environ.get("ENVIRONNEMENT", "local"),
            }
        )
    )
    fournisseur.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(fournisseur)

    # `/metrics` est exclu : tracer la collecte de métriques produirait un
    # volume de traces sans aucune valeur d'analyse.
    FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics")

    _logger.info("Traçage actif vers %s", point_de_collecte)
    return True


def identifiant_trace_courant() -> str | None:
    """Identifiant de la trace en cours, au format hexadécimal.

    Destiné au champ ``trace_id`` du journal d'audit. Retourne ``None`` si
    aucun traçage n'est actif — l'appelant doit alors omettre le champ, qui
    est facultatif au contrat.
    """
    try:
        from opentelemetry import trace
    except ImportError:
        return None

    contexte = trace.get_current_span().get_span_context()
    if not contexte.is_valid:
        return None
    return format(contexte.trace_id, "032x")
