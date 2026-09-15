"""M8 — tests du journal d'audit.

Vérifient le contrat de `docs/OBSERVABILITE.md` §2, et surtout ses
interdictions : c'est la partie qu'un test protège le mieux, parce qu'une
violation ne casse rien et ne se voit qu'à la relecture, trois ans plus tard.
"""

from __future__ import annotations

import json

import pytest

from src.m8_compliance.audit import (
    CHEMIN_DEFAUT,
    ROLES,
    TYPES_EVENEMENT,
    VARIABLE_CLE,
    ContratAuditError,
    construire,
    empreinte,
    journaliser,
)


@pytest.fixture(autouse=True)
def cle(monkeypatch):
    """Clé d'essai fabriquée, propre à chaque test."""
    monkeypatch.setenv(VARIABLE_CLE, "cle-d-essai-pour-les-tests-uniquement")


BASE = {
    "type_evenement": "answer.generated",
    "acteur": "utilisateur-4821",
    "role": "juriste",
}


# --------------------------------------------------------------------------
# La clé
# --------------------------------------------------------------------------


def test_sans_cle_le_journal_refuse_d_ecrire(monkeypatch):
    """Mieux vaut ne pas journaliser que journaliser sous une clé publique."""
    monkeypatch.delenv(VARIABLE_CLE, raising=False)
    with pytest.raises(ContratAuditError, match=VARIABLE_CLE):
        construire(**BASE)


def test_l_empreinte_est_stable_et_ne_rend_pas_l_original():
    valeur = "utilisateur-4821"
    assert empreinte(valeur) == empreinte(valeur)
    assert valeur not in empreinte(valeur)
    assert len(empreinte(valeur)) == 32


def test_deux_cles_donnent_deux_empreintes(monkeypatch):
    """C'est ce qui distingue un HMAC d'un condensé nu : sans la clé, aucun
    candidat ne peut être testé."""
    a = empreinte("utilisateur-4821")
    monkeypatch.setenv(VARIABLE_CLE, "une-autre-cle-d-essai")
    assert empreinte("utilisateur-4821") != a


# --------------------------------------------------------------------------
# Le pseudonymat est calculé par le module, pas par l'appelant
# --------------------------------------------------------------------------


def test_l_identifiant_reel_n_apparait_jamais():
    evenement = construire(**BASE)
    assert "utilisateur-4821" not in json.dumps(evenement)
    assert evenement["actor_id"] == empreinte("utilisateur-4821")


def test_le_texte_de_la_question_n_apparait_jamais():
    """§2.3 — le texte brut d'une question est interdit. L'appelant passe la
    question, le module n'en garde qu'une empreinte."""
    evenement = construire(**BASE, question="quelles sont les conditions de rupture ?")
    rendu = json.dumps(evenement, ensure_ascii=False)
    assert "rupture" not in rendu
    assert "conditions" not in rendu
    assert evenement["query_hash"]


def test_deux_formulations_equivalentes_donnent_la_meme_empreinte():
    """Sans normalisation, la détection d'usage anormal ne verrait que du bruit."""
    a = construire(**BASE, question="Conditions de   rupture ?")
    b = construire(**BASE, question="conditions de rupture ?")
    assert a["query_hash"] == b["query_hash"]


# --------------------------------------------------------------------------
# §2.3 — les interdictions, refusées et non nettoyées
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "champ, valeur",
    [
        ("code_erreur", "echec pour ahmed.benali@exemple.ma"),
        ("code_erreur", "refus depuis 192.168.1.42"),
        ("code_erreur", "jeton eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."),  # m8:autorise jeton fabrique, sujet meme du test
        ("modele", "modele-2001:0db8:85a3:0000:0000:8a2e:0370:7334"),
    ],
)
def test_un_contenu_interdit_est_refuse(champ, valeur):
    """Refus, jamais nettoyage : un événement silencieusement expurgé est un
    événement que personne n'ira examiner, et l'appel fautif resterait."""
    champs = dict(BASE, resultat="error", code_erreur="E_TEST")
    champs[champ] = valeur
    with pytest.raises(ContratAuditError):
        construire(**champs)


def test_l_interdiction_couvre_les_listes():
    with pytest.raises(ContratAuditError, match="adresse électronique"):
        construire(**BASE, sources_citees=["jur-1234", "ahmed.benali@exemple.ma"])


def test_un_doc_id_normal_n_est_pas_confondu_avec_une_adresse_ip():
    """Non-régression : `jurisprudence-0b2de421019f4dda` ne doit pas déclencher
    la règle IP, sans quoi le contrôle serait inutilisable."""
    evenement = construire(
        **BASE, sources_citees=["jurisprudence-0b2de421019f4dda", "BO-2019-4821"]
    )
    assert len(evenement["sources_cited"]) == 2


# --------------------------------------------------------------------------
# La forme imposée par §2.2 et §2.4
# --------------------------------------------------------------------------


def test_les_champs_obligatoires_sont_presents():
    evenement = construire(**BASE)
    for champ in ("ts", "event_id", "event_type", "actor_id", "actor_role", "outcome"):
        assert champ in evenement, champ


def test_l_horodatage_est_en_utc_rfc3339():
    assert construire(**BASE)["ts"].endswith("Z")


@pytest.mark.parametrize("type_evenement", TYPES_EVENEMENT)
def test_les_cinq_types_du_contrat_sont_acceptes(type_evenement):
    assert construire(**dict(BASE, type_evenement=type_evenement))


@pytest.mark.parametrize("role", ROLES)
def test_les_quatre_roles_de_la_matrice_sont_acceptes(role):
    assert construire(**dict(BASE, role=role))


def test_un_type_hors_contrat_est_refuse():
    with pytest.raises(ContratAuditError, match="type d'événement inconnu"):
        construire(**dict(BASE, type_evenement="answer.deleted"))


def test_un_role_hors_matrice_est_refuse():
    """Un rôle inconnu rend l'audit inexploitable : c'est le rôle qui dit si un
    accès était légitime."""
    with pytest.raises(ContratAuditError, match="rôle inconnu"):
        construire(**dict(BASE, role="superadmin"))


def test_une_erreur_sans_code_est_refusee():
    with pytest.raises(ContratAuditError, match="code_erreur"):
        construire(**dict(BASE, resultat="error"))


def test_les_champs_absents_ne_sont_pas_ecrits():
    """Un champ vide dans un journal se lit comme une valeur manquante, pas
    comme un champ sans objet."""
    evenement = construire(**BASE)
    for champ in ("query_hash", "sources_cited", "model", "error_code", "trace_id"):
        assert champ not in evenement


# --------------------------------------------------------------------------
# L'écriture — ajout seul
# --------------------------------------------------------------------------


def test_l_ecriture_ajoute_sans_remplacer(tmp_path):
    journal = tmp_path / "audit.jsonl"
    journaliser(chemin=journal, **BASE)
    journaliser(chemin=journal, **dict(BASE, type_evenement="corpus.read"))

    lignes = journal.read_text(encoding="utf-8").strip().split("\n")
    assert len(lignes) == 2
    assert json.loads(lignes[0])["event_type"] == "answer.generated"
    assert json.loads(lignes[1])["event_type"] == "corpus.read"


def test_chaque_ligne_est_un_json_autonome(tmp_path):
    """JSON Lines — §2.1. Une ligne tronquée ne doit pas rendre le reste
    illisible."""
    journal = tmp_path / "audit.jsonl"
    for _ in range(3):
        journaliser(chemin=journal, **BASE)
    for ligne in journal.read_text(encoding="utf-8").strip().split("\n"):
        assert json.loads(ligne)["event_id"]


def test_les_identifiants_d_evenement_sont_uniques(tmp_path):
    journal = tmp_path / "audit.jsonl"
    ids = {journaliser(chemin=journal, **BASE)["event_id"] for _ in range(20)}
    assert len(ids) == 20


def test_le_module_n_expose_aucune_suppression():
    """L'immuabilité tient à ce qui n'existe pas, pas à une promesse."""
    from src.m8_compliance import audit

    interdits = [n for n in dir(audit) if any(
        m in n.lower() for m in ("delete", "supprim", "remove", "purge", "update")
    )]
    assert not interdits, interdits


def test_le_chemin_par_defaut_est_celui_que_promtail_suit():
    assert CHEMIN_DEFAUT.parts[:2] == ("monitoring", "audit")
