"""M8 — le rapport d'ingestion ne doit nommer aucun fichier source.

`ingestion_report.json` est ecrit dans `data/processed/`, une sortie DVC
poussee sur le remote partage. Le nom d'un fichier brut est choisi par qui
collecte le document et porte regulierement le nom d'une partie : c'est le
raisonnement deja applique au `doc_id` et au `title` (ecart E-R3), et qui
manquait ici (ecart E-10).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.m1_ingestion.ingest import diagnostic_ref, redact_paths

RAW = Path("data/raw")
# Nom fabrique, du genre que produit une collecte reelle.
FICHIER = RAW / "jurisprudence" / "jugement_El_Amrani_2024.pdf"


def test_la_reference_ne_contient_pas_le_nom():
    ref = diagnostic_ref(FICHIER, RAW)
    assert "El_Amrani" not in ref
    assert "Amrani" not in ref.replace("-", "")


def test_la_reference_conserve_la_source_et_le_format():
    """Utile au diagnostic : une extraction qui echoue est presque toujours
    une question de format, et la source oriente la recherche."""
    ref = diagnostic_ref(FICHIER, RAW)
    assert ref.startswith("jurisprudence-")
    assert ref.endswith(".pdf")


def test_la_reference_est_deterministe():
    """Qui a besoin du vrai nom recalcule la correspondance en local."""
    assert diagnostic_ref(FICHIER, RAW) == diagnostic_ref(FICHIER, RAW)


def test_deux_fichiers_distincts_ont_des_references_distinctes():
    autre = RAW / "jurisprudence" / "jugement_Benali_2024.pdf"
    assert diagnostic_ref(FICHIER, RAW) != diagnostic_ref(autre, RAW)


def test_toute_cle_file_est_substituee_quelle_que_soit_sa_place():
    """La substitution est faite a la serialisation, pas a chaque site
    d'enregistrement : un champ ajoute plus tard est couvert sans que son
    auteur ait a connaitre la regle."""
    rapport = {
        "errors": [{"file": str(FICHIER), "error": "extraction failed"}],
        # Champ qui n'existe pas encore sur cette branche : il arrive avec la
        # PR #38. Il doit etre couvert d'avance.
        "duplicate_files": [{"file": str(FICHIER), "duplicate_of": "x-1234"}],
        "champ_futur": {"imbrique": [{"file": str(FICHIER)}]},
    }
    rendu = json.dumps(redact_paths(rapport, RAW), ensure_ascii=False)
    assert "El_Amrani" not in rendu
    assert rendu.count("jurisprudence-") == 3


def test_le_chemin_dans_un_message_d_erreur_est_aussi_substitue():
    """Trouve en executant le pipeline, pas en lisant le code : le message
    d'une erreur d'extraction porte le chemin. Substituer le champ ou le nom
    est attendu, et pas le texte libre a cote, ne serait pas un controle."""
    rapport = {
        "errors": [
            {
                "file": str(FICHIER),
                "error": f"Failed to extract text from {FICHIER}: bad format",
            }
        ]
    }
    rendu = json.dumps(redact_paths(rapport, RAW), ensure_ascii=False)
    assert "El_Amrani" not in rendu
    assert "bad format" in rendu


def test_les_autres_champs_sont_intacts():
    rapport = {"processed": 12, "raw_dir": "data/raw", "success_rate": 0.98}
    assert redact_paths(rapport, RAW) == rapport
