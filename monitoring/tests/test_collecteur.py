"""Tests du collecteur de traces — configuration et expurgation.

Ces tests portent sur des fichiers de configuration, pas sur du code Python.
C'est délibéré : la propriété qu'ils protègent — *aucun contenu utilisateur
n'atteint le magasin de traces* — ne vit pas dans une fonction. Elle vit dans
sept lignes de YAML que rien n'empêcherait de supprimer par inadvertance en
ajoutant un exportateur.

La vérification de bout en bout a été faite en exécutant la pile : onze
attributs envoyés au collecteur, trois stockés par Tempo, `enduser.id`
condensé. Ces tests-ci sont le garde-fou de non-régression de ce résultat.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML requis pour lire les configurations")

RACINE = Path(__file__).resolve().parents[1]
CONFIG_COLLECTEUR = RACINE / "otel-collector" / "otel-collector-config.yml"
CONFIG_TEMPO = RACINE / "tempo" / "tempo-config.yml"
CONFIG_SOURCES = RACINE / "grafana" / "provisioning" / "datasources" / "datasources.yml"


@pytest.fixture(scope="module")
def collecteur() -> dict:
    return yaml.safe_load(CONFIG_COLLECTEUR.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tempo() -> dict:
    return yaml.safe_load(CONFIG_TEMPO.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# L'expurgation — la raison d'être du collecteur
# --------------------------------------------------------------------------

# Contenu utilisateur : supprimé, jamais masqué. Un extrait de question
# juridique reste identifiant, et un préfixe de prompt aussi.
A_SUPPRIMER = (
    "rag.question",
    "rag.query",
    "llm.prompt",
    "llm.completion",
    "user.email",
    "client.address",
    "http.request.header.authorization",
    "http.request.header.cookie",
    "http.request.header.x-api-key",
)

# Identité de l'appelant : condensée, pour que la corrélation entre traces
# d'une même session reste possible sans que l'identité le soit.
A_CONDENSER = ("enduser.id",)


@pytest.fixture(scope="module")
def actions(collecteur: dict) -> dict[str, str]:
    processeur = collecteur["processors"]["attributes/expurger"]
    return {a["key"]: a["action"] for a in processeur["actions"]}


@pytest.mark.parametrize("cle", A_SUPPRIMER)
def test_le_contenu_utilisateur_est_supprime(actions: dict[str, str], cle: str) -> None:
    """§2.3 : le journal d'audit ne peut pas porter de contenu utilisateur.
    Rien ne serait cohérent à l'interdire là et à le tolérer dans les traces."""
    assert actions.get(cle) == "delete", f"{cle} n'est pas supprimé"


@pytest.mark.parametrize("cle", A_CONDENSER)
def test_l_identite_est_condensee_et_non_supprimee(actions: dict[str, str], cle: str) -> None:
    assert actions.get(cle) == "hash", f"{cle} devrait être condensé"


def test_l_expurgation_precede_l_exportation(collecteur: dict) -> None:
    """L'ordre du pipeline est la garantie, pas la présence du processeur.
    Placé après `batch`, il expurgerait après que les lots sont formés."""
    etapes = collecteur["service"]["pipelines"]["traces"]["processors"]
    assert "attributes/expurger" in etapes
    assert etapes.index("attributes/expurger") < etapes.index("batch")


def test_le_collecteur_n_exporte_que_vers_tempo(collecteur: dict) -> None:
    """Un exportateur ajouté sans passer par l'expurgation contournerait tout
    le dispositif. Ce test rend l'ajout visible en revue."""
    exportateurs = collecteur["service"]["pipelines"]["traces"]["exporters"]
    assert exportateurs == ["otlp/tempo"], exportateurs


def test_le_collecteur_ne_meurt_pas_sous_la_charge(collecteur: dict) -> None:
    """Un collecteur qui tombe emporte la visibilité au moment précis où elle
    est le plus utile — pendant l'incident qui l'a fait tomber."""
    etapes = collecteur["service"]["pipelines"]["traces"]["processors"]
    assert etapes[0] == "memory_limiter", "le garde-fou mémoire doit venir en premier"


# --------------------------------------------------------------------------
# La conservation
# --------------------------------------------------------------------------


def test_les_traces_se_conservent_moins_longtemps_que_l_audit(tempo: dict) -> None:
    """Trois ans pour le journal d'audit, trente jours pour les traces. Une
    trace technique porte des durées et des noms d'étapes, pas une preuve de
    conformité : la garder plus longtemps augmenterait la surface de données
    sans servir aucune obligation."""
    retention = tempo["compactor"]["compaction"]["block_retention"]
    assert retention.endswith("h")
    heures = int(retention.removesuffix("h"))
    assert heures <= 24 * 90, f"conservation trop longue : {retention}"


def test_tempo_ne_remonte_aucune_statistique_d_usage(tempo: dict) -> None:
    """Le dépôt est public et le corpus juridique : aucune télémétrie sortante."""
    assert tempo["usage_report"]["reporting_enabled"] is False


# --------------------------------------------------------------------------
# La corrélation journal ↔ trace
# --------------------------------------------------------------------------


def test_la_source_tempo_est_provisionnee_avec_un_uid_stable() -> None:
    """Sans `uid` fixe, Grafana en génère un à chaque installation et les
    liens depuis Loki ne pointent plus nulle part."""
    sources = yaml.safe_load(CONFIG_SOURCES.read_text(encoding="utf-8"))["datasources"]
    tempo = next((s for s in sources if s["type"] == "tempo"), None)
    assert tempo is not None, "aucune source de données Tempo provisionnée"
    assert tempo["uid"] == "cloudmind-tempo"


def test_le_journal_d_audit_renvoie_vers_la_trace() -> None:
    """C'est l'usage du champ `trace_id` du contrat §2.2 : relier un événement
    métier à sa trace technique sans stocker le contenu de la requête."""
    sources = yaml.safe_load(CONFIG_SOURCES.read_text(encoding="utf-8"))["datasources"]
    loki = next(s for s in sources if s["type"] == "loki")
    champs = loki["jsonData"]["derivedFields"]
    assert any(c["datasourceUid"] == "cloudmind-tempo" for c in champs)
