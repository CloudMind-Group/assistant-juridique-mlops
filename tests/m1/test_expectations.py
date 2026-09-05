"""Tests de la suite Great Expectations du corpus M1.

Une attente qui n'a jamais échoué ne prouve rien : elle peut être mal
écrite, porter sur une colonne absente, ou être satisfaite par accident.
Chaque test ci-dessous **casse volontairement une règle** et vérifie que la
suite s'en aperçoit — c'est la seule façon de savoir que la barrière est
posée dans le bon sens.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.m1_ingestion.expectations import (
    COLONNES_INTERDITES,
    EXPECTED_COLUMNS,
    executer,
)


def _document(doc_id: str = "bo-art001", **remplacements) -> dict:
    """Un enregistrement conforme au contrat, que chaque test dégrade."""
    base = {
        "doc_id": doc_id,
        "title": f"Titre de {doc_id}",
        "source": "Bulletin Officiel",
        "date": "2024-01-02",
        "category": "Droit du travail",
        "language": "fr",
        "file_path": f"data/processed/documents/{doc_id}.txt",
        "source_format": ".txt",
        "extraction_method": "text",
        "char_count_raw": 322,
        "word_count_raw": 51,
        "char_count_clean": 322,
        "word_count_clean": 51,
        "anonymized": False,
        "status": "SUCCESS",
        "processed_at": "2026-09-05T19:09:21.131440+00:00",
        "segment_count": 1,
    }
    base.update(remplacements)
    return base


def _corpus(tmp_path: Path, documents: list[dict]) -> Path:
    processed = tmp_path / "processed"
    processed.mkdir(exist_ok=True)
    (processed / "metadata.jsonl").write_text(
        "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in documents),
        encoding="utf-8",
    )
    return processed


def _attentes_en_echec(rapport: dict) -> set[str]:
    return {echec["attente"] for echec in rapport["echecs"]}


# --- Le cas nominal -----------------------------------------------------


def test_un_corpus_conforme_passe(tmp_path):
    rapport = executer(_corpus(tmp_path, [_document("a"), _document("b")]))

    assert rapport["succes"] is True
    assert rapport["attentes_en_echec"] == 0
    assert rapport["documents"] == 2


# --- Ce que quality.py ne peut pas voir ---------------------------------


def test_deux_documents_de_meme_identifiant_font_echouer_le_jeu(tmp_path):
    """Le cas qui justifie ce module. Chaque document est valide isolément —
    quality.py les accepte tous les deux. C'est l'ensemble qui ne l'est pas :
    M2 en indexerait un seul, sans la moindre erreur."""
    rapport = executer(_corpus(tmp_path, [_document("meme-id"), _document("meme-id")]))

    assert rapport["succes"] is False
    assert "expect_column_values_to_be_unique" in _attentes_en_echec(rapport)


def test_un_corpus_vide_fait_echouer_le_jeu(tmp_path):
    """Zéro document passe tous les contrôles par document : il n'y en a
    aucun à contrôler. Sans cette attente, un pipeline qui n'a rien produit
    livrerait un corpus vide en silence."""
    rapport = executer(_corpus(tmp_path, []))

    assert rapport["succes"] is False
    assert "expect_table_row_count_to_be_between" in _attentes_en_echec(rapport)


# --- Garde-fou données personnelles -------------------------------------


@pytest.mark.parametrize("colonne_interdite", COLONNES_INTERDITES)
def test_une_colonne_interdite_fait_echouer_le_jeu(tmp_path, colonne_interdite):
    """Ce dépôt a déjà publié un nom de fichier brut dans metadata.jsonl
    (`original_filename`) : le nom d'un arrêt porte souvent le nom d'une
    partie. Toute colonne hors contrat doit bloquer la chaîne, qu'on ait
    pensé à la nommer ou non."""
    document = _document("a")
    document[colonne_interdite] = "arret_ahmed_benali_2024.txt"

    rapport = executer(_corpus(tmp_path, [document]))

    assert rapport["succes"] is False
    assert "expect_table_columns_to_match_set" in _attentes_en_echec(rapport)


def test_une_colonne_du_contrat_manquante_fait_echouer_le_jeu(tmp_path):
    """L'inverse : un champ du schéma que le pipeline cesse d'écrire. M2 lit
    ce schéma directement — la disparition doit se voir ici, pas chez Imane."""
    document = _document("a")
    del document["segment_count"]

    rapport = executer(_corpus(tmp_path, [document]))

    assert rapport["succes"] is False
    assert "expect_table_columns_to_match_set" in _attentes_en_echec(rapport)


def test_le_contrat_de_colonnes_suit_le_schema_pydantic():
    """La liste des colonnes est dérivée du schéma, pas recopiée : une copie
    diverge sans que personne ne le voie."""
    from src.m1_ingestion.metadata_schema import DocumentMetadata

    assert EXPECTED_COLUMNS == sorted(DocumentMetadata.model_fields)
    assert "doc_id" in EXPECTED_COLUMNS
    for interdite in COLONNES_INTERDITES:
        assert interdite not in EXPECTED_COLUMNS


# --- Fuite d'arborescence locale ----------------------------------------


@pytest.mark.parametrize(
    "chemin_absolu",
    [
        "/home/douae/corpus/arret.txt",
        "C:/Users/hp/Downloads/arret.txt",
        "C:\\Users\\hp\\Downloads\\arret.txt",
    ],
)
def test_un_chemin_absolu_fait_echouer_le_jeu(tmp_path, chemin_absolu):
    """Un chemin absolu dans le jeu livré, c'est l'arborescence de la machine
    qui a ingéré qui sort du dépôt — POSIX comme Windows."""
    rapport = executer(_corpus(tmp_path, [_document("a", file_path=chemin_absolu)]))

    assert rapport["succes"] is False
    assert "expect_column_values_to_match_regex" in _attentes_en_echec(rapport)


# --- Valeurs hors contrat ------------------------------------------------


def test_une_source_hors_nomenclature_fait_echouer_le_jeu(tmp_path):
    rapport = executer(_corpus(tmp_path, [_document("a", source="Blog juridique")]))

    assert rapport["succes"] is False
    assert "expect_column_values_to_be_in_set" in _attentes_en_echec(rapport)


def test_une_date_mal_formee_fait_echouer_le_jeu(tmp_path):
    rapport = executer(_corpus(tmp_path, [_document("a", date="02/01/2024")]))

    assert rapport["succes"] is False
    assert "expect_column_values_to_match_regex" in _attentes_en_echec(rapport)


def test_un_document_quasi_vide_fait_echouer_le_jeu(tmp_path):
    """Extraction qui a échoué à moitié : le fichier existe, il ne contient
    que trois mots. Le seuil est aligné sur celui de quality.py."""
    rapport = executer(
        _corpus(tmp_path, [_document("a", word_count_clean=3, char_count_clean=12)])
    )

    assert rapport["succes"] is False
    assert "expect_column_values_to_be_between" in _attentes_en_echec(rapport)


def test_un_document_en_echec_ne_doit_pas_figurer_dans_l_index(tmp_path):
    """Seuls les documents traités avec succès entrent dans metadata.jsonl.
    Un document en échec qui s'y trouve est un bug de pipeline, pas un
    document de mauvaise qualité — d'où le blocage."""
    rapport = executer(_corpus(tmp_path, [_document("a", status="FAILED")]))

    assert rapport["succes"] is False
    assert "expect_column_values_to_be_in_set" in _attentes_en_echec(rapport)


# --- Diagnostic ----------------------------------------------------------


def test_le_rapport_nomme_la_colonne_et_montre_un_exemple(tmp_path):
    """Un rapport qui dit « une attente a échoué » sans dire laquelle ni sur
    quoi oblige à rejouer le pipeline à la main pour comprendre."""
    rapport = executer(_corpus(tmp_path, [_document("a", source="Blog juridique")]))

    echec = next(
        e for e in rapport["echecs"] if e["attente"] == "expect_column_values_to_be_in_set"
    )
    assert echec["colonne"] == "source"
    assert echec["elements_en_echec"] == 1
    assert "Blog juridique" in echec["exemples"]


def test_un_metadata_jsonl_corrompu_fait_echouer_la_lecture(tmp_path):
    processed = _corpus(tmp_path, [_document("a")])
    (processed / "metadata.jsonl").write_text(
        '{"doc_id": "a"}\n{ceci ne parse pas\n', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="JSON invalide ligne 2"):
        executer(processed)
