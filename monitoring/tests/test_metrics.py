"""Tests du module d'instrumentation — contrat docs/OBSERVABILITE.md §1.

Ce module est celui que M5 importera tel quel. Une régression ici est
silencieuse : l'API continue de servir, les tableaux de bord se vident, et
personne ne s'en aperçoit avant l'incident suivant. D'où ces tests.

Le plus important est `test_le_label_route_porte_le_gabarit` : c'est la seule
règle du contrat dont la violation ne casse rien immédiatement, mais fait
exploser la base de séries temporelles à mesure que le trafic arrive.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="FastAPI requis pour ces tests")

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from prometheus_client import REGISTRY  # noqa: E402

from monitoring.instrumentation.metrics import (  # noqa: E402
    declarer_version,
    enregistrer_cache,
    enregistrer_echec_modele,
    enregistrer_generation,
    instrumenter,
    mesurer_recuperation,
)


def _valeur(nom: str, **labels: str) -> float:
    """Valeur courante d'une série, ou 0.0 si elle n'existe pas encore."""
    v = REGISTRY.get_sample_value(nom, labels or None)
    return 0.0 if v is None else v


@pytest.fixture
def client() -> TestClient:
    """Application minimale instrumentée, représentative des routes de M5."""
    app = FastAPI()

    @app.post("/v1/ask")
    async def ask() -> dict[str, str]:
        return {"reponse": "..."}

    # Route paramétrée : c'est elle qui révèle une violation de cardinalité.
    @app.get("/v1/documents/{doc_id}")
    async def document(doc_id: str) -> dict[str, str]:
        return {"doc_id": doc_id}

    @app.get("/v1/boom")
    async def boom() -> None:
        raise RuntimeError("panne simulee")

    @app.get("/v1/refus")
    async def refus() -> None:
        raise HTTPException(status_code=422, detail="hors perimetre")

    instrumenter(app)
    return TestClient(app, raise_server_exceptions=False)


# --- exposition ---------------------------------------------------------------


def test_endpoint_metrics_expose_le_format_prometheus(client: TestClient) -> None:
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "# TYPE http_requests_total counter" in r.text


def test_les_neuf_series_du_contrat_sont_declarees(client: TestClient) -> None:
    """Le contrat §1.3 énumère neuf séries. Aucune ne doit manquer."""
    client.post("/v1/ask")
    enregistrer_cache(touche=True)
    enregistrer_generation("legal-fr-v2", 1.2, 900, 210)
    enregistrer_echec_modele("legal-fr-v2", "timeout")
    declarer_version("0.2.0", "abc1234")
    with mesurer_recuperation() as ctx:
        ctx.documents(5)

    corps = client.get("/metrics").text
    for serie in (
        "http_requests_total",
        "http_request_duration_seconds",
        "rag_retrieval_duration_seconds",
        "rag_documents_retrieved",
        "llm_request_duration_seconds",
        "llm_tokens_total",
        "llm_requests_failed_total",
        "cache_lookups_total",
        "app_info",
    ):
        assert serie in corps, f"série absente du contrat : {serie}"


# --- règle de cardinalité : le test le plus important -------------------------


def test_le_label_route_porte_le_gabarit_et_non_le_chemin(client: TestClient) -> None:
    """Trois documents distincts ne doivent produire qu'UNE seule série.

    Si le label portait le chemin concret, chaque identifiant créerait une
    série : la cardinalité deviendrait celle du corpus.
    """
    for doc in ("8f3a", "91c2", "4d7e"):
        client.get(f"/v1/documents/{doc}")

    gabarit = _valeur(
        "http_requests_total",
        method="GET",
        route="/v1/documents/{doc_id}",
        status="200",
    )
    assert gabarit == 3.0, "les trois appels doivent s'agréger sur le gabarit"

    for doc in ("8f3a", "91c2", "4d7e"):
        concret = REGISTRY.get_sample_value(
            "http_requests_total",
            {"method": "GET", "route": f"/v1/documents/{doc}", "status": "200"},
        )
        assert concret is None, f"violation de cardinalité : série créée pour {doc}"


# --- comptage des statuts ------------------------------------------------------


def test_une_requete_reussie_est_comptee_avec_son_statut(client: TestClient) -> None:
    avant = _valeur("http_requests_total", method="POST", route="/v1/ask", status="200")
    client.post("/v1/ask")
    apres = _valeur("http_requests_total", method="POST", route="/v1/ask", status="200")
    assert apres == avant + 1


def test_une_exception_non_rattrapee_est_comptee_en_500(client: TestClient) -> None:
    """Sans cela le taux d'erreur serait sous-estimé — le pire des biais.

    Le client reçoit un 500 ; la métrique doit dire la même chose.
    """
    avant = _valeur("http_requests_total", method="GET", route="/v1/boom", status="500")
    reponse = client.get("/v1/boom")
    assert reponse.status_code == 500
    apres = _valeur("http_requests_total", method="GET", route="/v1/boom", status="500")
    assert apres == avant + 1


def test_une_erreur_metier_n_est_pas_comptee_en_500(client: TestClient) -> None:
    """Un 422 est un refus légitime, pas une panne : il ne doit pas alerter."""
    client.get("/v1/refus")
    assert _valeur("http_requests_total", method="GET", route="/v1/refus", status="422") >= 1.0
    assert _valeur("http_requests_total", method="GET", route="/v1/refus", status="500") == 0.0


def test_l_endpoint_metrics_ne_se_compte_pas_lui_meme(client: TestClient) -> None:
    """Compter la collecte fausserait le débit : Prometheus scrute toutes les 15 s."""
    client.get("/metrics")
    client.get("/metrics")
    assert _valeur("http_requests_total", method="GET", route="/metrics", status="200") == 0.0


# --- durées --------------------------------------------------------------------


def test_la_duree_est_observee_dans_l_histogramme(client: TestClient) -> None:
    avant = _valeur("http_request_duration_seconds_count", method="POST", route="/v1/ask")
    client.post("/v1/ask")
    apres = _valeur("http_request_duration_seconds_count", method="POST", route="/v1/ask")
    assert apres == avant + 1


def test_la_duree_est_observee_meme_quand_la_route_leve(client: TestClient) -> None:
    """Une panne lente est précisément ce qu'on cherche à voir."""
    avant = _valeur("http_request_duration_seconds_count", method="GET", route="/v1/boom")
    client.get("/v1/boom")
    apres = _valeur("http_request_duration_seconds_count", method="GET", route="/v1/boom")
    assert apres == avant + 1


def test_le_bucket_25s_existe(client: TestClient) -> None:
    """L'objectif publié est P95 < 2,5 s : sans borne à 2.5, le quantile est interpolé."""
    client.post("/v1/ask")
    assert (
        REGISTRY.get_sample_value(
            "http_request_duration_seconds_bucket",
            {"method": "POST", "route": "/v1/ask", "le": "2.5"},
        )
        is not None
    ), "la borne 2.5 doit encadrer l'objectif de latence"


# --- étapes internes de la chaîne RAG -----------------------------------------


def test_mesurer_recuperation_enregistre_duree_et_documents() -> None:
    avant_duree = _valeur("rag_retrieval_duration_seconds_count")
    avant_docs = _valeur("rag_documents_retrieved_count")
    with mesurer_recuperation() as ctx:
        ctx.documents(7)
    assert _valeur("rag_retrieval_duration_seconds_count") == avant_duree + 1
    assert _valeur("rag_documents_retrieved_count") == avant_docs + 1


def test_mesurer_recuperation_enregistre_la_duree_meme_si_le_bloc_leve() -> None:
    """Une récupération qui échoue lentement doit rester visible."""
    avant = _valeur("rag_retrieval_duration_seconds_count")
    with pytest.raises(ValueError):
        with mesurer_recuperation():
            raise ValueError("index indisponible")
    assert _valeur("rag_retrieval_duration_seconds_count") == avant + 1


def test_les_jetons_sont_separes_prompt_et_completion() -> None:
    """Leur rapport révèle une dérive de prompt système, invisible autrement."""
    avant_p = _valeur("llm_tokens_total", model="m", type="prompt")
    avant_c = _valeur("llm_tokens_total", model="m", type="completion")
    enregistrer_generation("m", 1.0, 100, 30)
    assert _valeur("llm_tokens_total", model="m", type="prompt") == avant_p + 100
    assert _valeur("llm_tokens_total", model="m", type="completion") == avant_c + 30


def test_le_cache_distingue_hit_et_miss() -> None:
    avant = _valeur("cache_lookups_total", result="hit")
    enregistrer_cache(touche=True)
    enregistrer_cache(touche=False)
    assert _valeur("cache_lookups_total", result="hit") == avant + 1
    assert _valeur("cache_lookups_total", result="miss") >= 1.0


def test_app_info_permet_de_correler_un_incident_a_une_livraison() -> None:
    declarer_version("1.2.3", "deadbee")
    assert _valeur("app_info", version="1.2.3", commit="deadbee") == 1.0
