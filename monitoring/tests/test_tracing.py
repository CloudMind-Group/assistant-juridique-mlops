"""Tests du squelette de traçage — monitoring/instrumentation/tracing.py.

La propriété la plus importante de ce module n'est pas qu'il trace, mais
qu'il **ne casse jamais le service qu'il observe**. Il doit rester inerte et
silencieux tant qu'aucun collecteur n'est déployé — sans quoi M5 dépendrait
du calendrier de M4 pour simplement démarrer.

Les tests couvrent donc d'abord les chemins de dégradation, ensuite seulement
le chemin nominal.

Note sur la sortie : ces tests produisent en fin d'exécution des messages
``Transient error ... Failed to export span batch``. Ce bruit est **attendu et
démontre la propriété recherchée** : l'exportateur tente de joindre un
collecteur inexistant, échoue en tâche de fond, abandonne — et aucun test ne
casse. C'est exactement ce qui doit se produire en production le jour où le
collecteur tombe.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="FastAPI requis pour ces tests")

from fastapi import FastAPI  # noqa: E402

from monitoring.instrumentation.tracing import (  # noqa: E402
    SEGMENTS,
    activer_tracage,
    identifiant_trace_courant,
)


# --- dégradation : le comportement par défaut ---------------------------------


def test_inerte_sans_collecteur_configure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans OTEL_EXPORTER_OTLP_ENDPOINT, le traçage est désactivé sans bruit."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert activer_tracage(FastAPI(), service="test") is False


def test_ne_leve_jamais_meme_avec_une_configuration_absurde(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L'observabilité ne doit pas être une cause de panne du service."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collecteur-inexistant:4318")
    # Ne doit produire aucune exception, quel que soit le résultat.
    resultat = activer_tracage(FastAPI(), service="test", version="0.0.1")
    assert resultat in (True, False)


def test_identifiant_de_trace_est_none_hors_de_toute_trace() -> None:
    """Le champ trace_id du journal d'audit est facultatif : None doit être géré."""
    assert identifiant_trace_courant() is None


def test_les_segments_de_la_chaine_rag_sont_nommes_de_facon_stable() -> None:
    """Une trace n'a de valeur que si ses segments portent les mêmes noms
    d'un service à l'autre. Ces noms sont un contrat implicite avec M2 et M5."""
    assert SEGMENTS == ("rag.retrieve", "rag.rerank", "rag.generate", "rag.cite")


# --- chemin nominal ------------------------------------------------------------


def test_activation_reelle_et_production_d_un_identifiant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Avec le SDK présent et un point de collecte défini, le traçage s'active
    et produit un identifiant exploitable par le journal d'audit."""
    pytest.importorskip("opentelemetry.sdk", reason="SDK OpenTelemetry absent")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    assert activer_tracage(FastAPI(), service="assistant-api", version="0.2.0") is True

    from opentelemetry import trace

    with trace.get_tracer(__name__).start_as_current_span("rag.retrieve"):
        identifiant = identifiant_trace_courant()

    assert identifiant is not None
    # Format attendu : 32 caractères hexadécimaux, tel qu'inscrit au contrat §2.2.
    assert len(identifiant) == 32
    assert all(c in "0123456789abcdef" for c in identifiant)
    assert identifiant != "0" * 32, "identifiant nul = trace invalide"


def test_l_endpoint_metrics_est_exclu_du_tracage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tracer la collecte de métriques produirait un volume de traces sans
    aucune valeur d'analyse : une trace toutes les 15 secondes, à vie."""
    pytest.importorskip("opentelemetry.instrumentation.fastapi")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    import inspect

    from monitoring.instrumentation import tracing

    source = inspect.getsource(tracing.activer_tracage)
    assert 'excluded_urls="/metrics"' in source
