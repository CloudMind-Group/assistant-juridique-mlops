"""Tests du DAG Airflow `legal_ingest_v2`.

Ce DAG n'avait aucun test : il importe `airflow`, qui n'est pas installé en
CI (la dépendance est commentée dans requirements.txt, ~200 Mo pour un seul
fichier orchestré). Le réflexe serait `pytest.importorskip("airflow")` — mais
un test systématiquement ignoré en CI ne protège de rien, il donne juste
l'impression d'une couverture.

On installe donc un **double d'Airflow** : quatre classes minimales qui
enregistrent les `task_id`, le chaînage `>>` et les arguments. Le fichier du
DAG est ensuite importé tel quel. Ce qui est testé est le vrai code du DAG —
la structure de la chaîne et la logique de notification de M2 — sans la
dépendance.

Ce que ce double ne teste PAS, et qu'il ne faut pas croire testé : la
sémantique réelle d'Airflow (planification, reprises, dates d'exécution).
Pour ça, le dernier test fait un vrai `DagBag` quand Airflow est présent.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHEMIN_DAG = REPO_ROOT / "dags" / "legal_ingest_v2.py"


class _FauxOperateur:
    """Enregistre ce que le DAG déclare, et supporte l'opérateur `>>`."""

    def __init__(self, task_id: str, **kwargs):
        self.task_id = task_id
        self.kwargs = kwargs
        self.aval: list[_FauxOperateur] = []

    def __rshift__(self, autre: "_FauxOperateur") -> "_FauxOperateur":
        self.aval.append(autre)
        return autre


class _FauxDAG:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.taches: dict[str, _FauxOperateur] = {}

    def __enter__(self) -> "_FauxDAG":
        return self

    def __exit__(self, *exc) -> bool:
        return False


class _FauxEchecAirflow(Exception):
    """Tient lieu de airflow.exceptions.AirflowFailException."""


def _installer_double_airflow(monkeypatch) -> None:
    airflow = types.ModuleType("airflow")
    airflow.DAG = _FauxDAG

    exceptions = types.ModuleType("airflow.exceptions")
    exceptions.AirflowFailException = _FauxEchecAirflow

    operators = types.ModuleType("airflow.operators")
    bash = types.ModuleType("airflow.operators.bash")
    bash.BashOperator = _FauxOperateur
    python_mod = types.ModuleType("airflow.operators.python")
    python_mod.PythonOperator = _FauxOperateur

    for nom, module in {
        "airflow": airflow,
        "airflow.exceptions": exceptions,
        "airflow.operators": operators,
        "airflow.operators.bash": bash,
        "airflow.operators.python": python_mod,
    }.items():
        monkeypatch.setitem(sys.modules, nom, module)


@pytest.fixture
def dag_module(monkeypatch):
    """Importe le fichier du DAG avec le double d'Airflow en place."""
    _installer_double_airflow(monkeypatch)
    spec = importlib.util.spec_from_file_location("legal_ingest_v2_sous_test", CHEMIN_DAG)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- Structure de la chaîne ---------------------------------------------


def test_les_quatre_taches_sont_declarees(dag_module):
    identifiants = {
        dag_module.run_ingestion.task_id,
        dag_module.run_quality_check.task_id,
        dag_module.run_expectations.task_id,
        dag_module.notify_m2_imane.task_id,
    }

    assert identifiants == {
        "run_ingestion",
        "run_quality_check",
        "run_expectations",
        "notify_m2_imane",
    }


def test_la_chaine_est_sequentielle_et_dans_le_bon_ordre(dag_module):
    """L'ordre porte le sens : on ne notifie M2 qu'après avoir validé, et on
    ne valide qu'après avoir ingéré. Une tâche déplacée casse la garantie
    sans casser le DAG."""
    assert dag_module.run_ingestion.aval == [dag_module.run_quality_check]
    assert dag_module.run_quality_check.aval == [dag_module.run_expectations]
    assert dag_module.run_expectations.aval == [dag_module.notify_m2_imane]
    assert dag_module.notify_m2_imane.aval == []


def test_les_deux_controles_qualite_sont_bloquants(dag_module):
    """Sans `--fail-on-error`, les contrôles écrivent leur rapport, sortent en
    code 0, et M2 reçoit un corpus non conforme avec un rapport qui dit qu'il
    ne l'est pas. C'est le drapeau, pas le contrôle, qui bloque la chaîne."""
    for tache in (dag_module.run_quality_check, dag_module.run_expectations):
        assert "--fail-on-error" in tache.kwargs["bash_command"], tache.task_id


def test_le_dag_ne_rattrape_pas_l_historique(dag_module):
    """`catchup=True` sur un DAG quotidien démarré au 01/01/2025 déclencherait
    des centaines d'exécutions de rattrapage au premier déploiement."""
    assert dag_module.dag.kwargs["catchup"] is False
    assert dag_module.dag.kwargs["max_active_runs"] == 1


def test_les_reprises_sont_configurees(dag_module):
    assert dag_module.default_args["retries"] == 2
    assert dag_module.default_args["retry_delay"].total_seconds() > 0


# --- Notification de M2 --------------------------------------------------


def _ecrire_rapport(dossier: Path, **contenu) -> None:
    (dossier / "quality_report.json").write_text(
        json.dumps({"total_documents": 60, "passed": 60, "failed": 0, "pass_rate": 1.0} | contenu),
        encoding="utf-8",
    )


def test_m2_est_notifie_quand_le_corpus_est_conforme(dag_module, tmp_path, monkeypatch):
    monkeypatch.setattr(dag_module, "QUALITY_REPORT_PATH", tmp_path / "quality_report.json")
    monkeypatch.setattr(dag_module, "M2_READY_FLAG_PATH", tmp_path / "READY_FOR_M2.flag")
    _ecrire_rapport(tmp_path)

    dag_module._notify_m2_imane(run_id="manual__2026-09-05")

    signal = json.loads((tmp_path / "READY_FOR_M2.flag").read_text(encoding="utf-8"))
    assert signal["total_documents"] == 60
    assert signal["dag_run_id"] == "manual__2026-09-05"
    assert signal["metadata_index"].endswith("metadata.jsonl")
    # M2 lit cet horodatage. Il doit porter son fuseau, comme processed_at
    # et generated_at ailleurs dans le pipeline — sinon la conversion est
    # laissee au lecteur, qui la fera un jour de travers.
    assert datetime.fromisoformat(signal["notified_at"]).tzinfo is not None


def test_m2_n_est_pas_notifie_si_un_document_a_echoue(dag_module, tmp_path, monkeypatch):
    """Le cœur du garde-fou : un seul document non conforme et M2 n'est pas
    prévenu. Le drapeau ne doit surtout pas être écrit — M2 le lit en boucle."""
    monkeypatch.setattr(dag_module, "QUALITY_REPORT_PATH", tmp_path / "quality_report.json")
    monkeypatch.setattr(dag_module, "M2_READY_FLAG_PATH", tmp_path / "READY_FOR_M2.flag")
    _ecrire_rapport(tmp_path, failed=1, passed=59, pass_rate=0.9833)

    with pytest.raises(_FauxEchecAirflow, match="failed quality checks"):
        dag_module._notify_m2_imane(run_id="manual__2026-09-05")

    assert not (tmp_path / "READY_FOR_M2.flag").exists()


def test_un_rapport_absent_fait_echouer_la_notification(dag_module, tmp_path, monkeypatch):
    """Le contrôle qualité n'a pas tourné du tout. Sans ce garde-fou, M2
    serait notifié d'un corpus que personne n'a validé."""
    monkeypatch.setattr(dag_module, "QUALITY_REPORT_PATH", tmp_path / "absent.json")
    monkeypatch.setattr(dag_module, "M2_READY_FLAG_PATH", tmp_path / "READY_FOR_M2.flag")

    with pytest.raises(_FauxEchecAirflow, match="not found"):
        dag_module._notify_m2_imane(run_id="manual")

    assert not (tmp_path / "READY_FOR_M2.flag").exists()


def test_un_rapport_sans_champ_failed_est_traite_comme_un_echec(
    dag_module, tmp_path, monkeypatch
):
    """Rapport tronqué ou d'un format plus ancien : en l'absence de preuve que
    zéro document a échoué, on refuse de notifier plutôt que de supposer."""
    monkeypatch.setattr(dag_module, "QUALITY_REPORT_PATH", tmp_path / "quality_report.json")
    monkeypatch.setattr(dag_module, "M2_READY_FLAG_PATH", tmp_path / "READY_FOR_M2.flag")
    (tmp_path / "quality_report.json").write_text(
        json.dumps({"total_documents": 60}), encoding="utf-8"
    )

    with pytest.raises(_FauxEchecAirflow):
        dag_module._notify_m2_imane(run_id="manual")


# --- Vrai Airflow, quand il est là ---------------------------------------


def test_le_dag_se_charge_dans_un_vrai_airflow():
    """Le double ci-dessus ne connaît rien à la sémantique d'Airflow. Ce test
    la vérifie pour de bon — ignoré en CI, exécuté par qui a Airflow installé."""
    pytest.importorskip("airflow", reason="apache-airflow non installé (dépendance lourde)")
    from airflow.models import DagBag

    sac = DagBag(dag_folder=str(REPO_ROOT / "dags"), include_examples=False)

    assert sac.import_errors == {}
    dag = sac.get_dag("legal_ingest_v2")
    assert dag is not None
    assert {t.task_id for t in dag.tasks} == {
        "run_ingestion",
        "run_quality_check",
        "run_expectations",
        "notify_m2_imane",
    }
