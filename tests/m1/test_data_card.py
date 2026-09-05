"""Tests de la génération de Data Card (M1).

L'enjeu de ces tests n'est pas la mise en forme : c'est que la carte ne
puisse pas raconter mieux que ce que le pipeline a réellement produit. On
vérifie donc en priorité les endroits où une Data Card ment habituellement —
les documents oubliés, les sources vides, les garanties de confidentialité.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.m1_ingestion.data_card import (
    CORPUS_STATUS_CHOICES,
    build_data_card,
    render_markdown,
    summarize_composition,
    summarize_privacy,
    summarize_segments,
    write_card,
)


def _ecrire_corpus(tmp_path: Path, *, records, segments, ingestion=None, quality=None):
    """Fabrique un data/processed minimal mais complet."""
    processed = tmp_path / "processed"
    processed.mkdir()

    (processed / "metadata.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    (processed / "segments.jsonl").write_text(
        "\n".join(json.dumps(s, ensure_ascii=False) for s in segments) + "\n"
        if segments
        else "",
        encoding="utf-8",
    )
    (processed / "ingestion_report.json").write_text(
        json.dumps(
            ingestion
            or {
                "total_files_discovered": len(records),
                "processed": len(records),
                "skipped": 0,
                "failed": 0,
                "success_rate": 1.0,
                "duplicates": 0,
                "pii_masked": 0,
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    (processed / "quality_report.json").write_text(
        json.dumps(
            quality
            or {
                "total_documents": len(records),
                "passed": len(records),
                "failed": 0,
                "pass_rate": 1.0,
                "results": [
                    {"doc_id": r["doc_id"], "passed": True, "errors": [], "warnings": []}
                    for r in records
                ],
            }
        ),
        encoding="utf-8",
    )
    return processed


def _doc(doc_id: str, **overrides):
    base = {
        "doc_id": doc_id,
        "title": f"Titre {doc_id}",
        "source": "Bulletin Officiel",
        "date": "2024-01-01",
        "category": "Droit du travail",
        "language": "fr",
        "file_path": f"data/processed/documents/{doc_id}.txt",
        "source_format": ".txt",
        "extraction_method": "text",
        "char_count_clean": 300,
        "word_count_clean": 50,
        "anonymized": False,
    }
    base.update(overrides)
    return base


def test_un_document_sans_segment_reste_compte():
    """Le piège classique : compter les segments par document en ne regardant
    que segments.jsonl. Les documents à zéro segment n'y figurent pas — ils
    disparaîtraient du bilan et la moyenne remonterait toute seule."""
    records = [_doc("a"), _doc("b"), _doc("c")]
    segments = [
        {"doc_id": "a", "kind": "article", "text": "Article 1 ..."},
        {"doc_id": "b", "kind": "article", "text": "Article 1 ..."},
    ]

    resume = summarize_segments(segments, records)

    assert resume["documents_sans_segment"] == 1
    assert resume["segments_par_document"]["n"] == 3, (
        "les 3 documents doivent entrer dans la distribution, pas seulement "
        "les 2 qui ont produit des segments"
    )
    assert resume["segments_par_document"]["min"] == 0


def test_une_source_declaree_sans_document_est_signalee():
    """Un connecteur déclaré mais qui n'a rien collecté est un trou de
    couverture. La carte doit le dire, pas laisser croire que la source est
    servie parce que le code existe."""
    composition = summarize_composition([_doc("a", source="Bulletin Officiel")])

    absentes = composition["sources_declarees_sans_document"]
    assert "Portail Officiel" in absentes
    assert "Dépôt Interne" in absentes
    assert "Bulletin Officiel" not in absentes


def test_la_carte_ne_promet_aucun_rappel_pii():
    """Garde-fou de fond : personne ne doit pouvoir ajouter un chiffre de
    rappel dans cette section sans une mesure derrière."""
    confidentialite = summarize_privacy([_doc("a")], {"pii_masked": 7})

    assert confidentialite["occurrences_masquees"] == 7
    assert confidentialite["garantie_de_rappel"] is None
    assert "pas de NER" in confidentialite["methode"]


def test_le_statut_synthetique_apparait_en_toutes_lettres(tmp_path):
    """Le corpus est fabriqué. Un lecteur pressé doit le lire avant les
    chiffres, pas dans une note de bas de page."""
    processed = _ecrire_corpus(
        tmp_path,
        records=[_doc("a")],
        segments=[{"doc_id": "a", "kind": "article", "text": "Article 1 ..."}],
    )

    markdown = render_markdown(build_data_card(processed))

    assert "synthétique" in markdown
    assert "valeur juridique" in markdown
    assert markdown.index("Nature du corpus") < markdown.index("Composition")


def test_un_statut_de_corpus_inconnu_est_refuse(tmp_path):
    processed = _ecrire_corpus(tmp_path, records=[_doc("a")], segments=[])

    with pytest.raises(ValueError, match="statut de corpus inconnu"):
        build_data_card(processed, corpus_status="presque_vrai")

    assert "synthetique" in CORPUS_STATUS_CHOICES


def test_un_metadata_jsonl_corrompu_fait_echouer_la_generation(tmp_path):
    """Même choix que quality.py : une Data Card calculée sur un fichier
    tronqué serait fausse sans le dire. Mieux vaut ne pas la produire."""
    processed = _ecrire_corpus(tmp_path, records=[_doc("a")], segments=[])
    (processed / "metadata.jsonl").write_text(
        '{"doc_id": "a"}\n{ceci ne parse pas\n', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="JSON invalide ligne 2"):
        build_data_card(processed)


def test_les_deux_sorties_sont_ecrites_et_concordent(tmp_path):
    processed = _ecrire_corpus(
        tmp_path,
        records=[_doc("a"), _doc("b", language="ar")],
        segments=[{"doc_id": "a", "kind": "article", "text": "Article 1 ..."}],
    )

    json_path, md_path = write_card(build_data_card(processed), processed)

    charge = json.loads(json_path.read_text(encoding="utf-8"))
    assert charge["composition"]["documents"] == 2
    assert charge["composition"]["par_langue"] == {"ar": 1, "fr": 1}
    assert "**2 documents.**" in md_path.read_text(encoding="utf-8")


def test_les_comptages_sont_ordonnes_de_maniere_stable():
    """Un ordre de clés instable ferait apparaître la carte comme modifiée à
    chaque `dvc repro`, pour rien."""
    records = [_doc("a", category="Zèbre"), _doc("b", category="Alpha")]

    par_categorie = summarize_composition(records)["par_categorie"]

    assert list(par_categorie) == sorted(par_categorie)


def test_un_document_en_echec_est_nomme_dans_la_carte(tmp_path):
    """Un taux de réussite de 95 % sans dire quels documents ont échoué est
    inexploitable pour celui qui doit corriger."""
    records = [_doc("a"), _doc("b")]
    quality = {
        "total_documents": 2,
        "passed": 1,
        "failed": 1,
        "pass_rate": 0.5,
        "results": [
            {"doc_id": "a", "passed": True, "errors": [], "warnings": []},
            {
                "doc_id": "b",
                "passed": False,
                "errors": ["text file is empty"],
                "warnings": [],
            },
        ],
    }
    processed = _ecrire_corpus(tmp_path, records=records, segments=[], quality=quality)

    markdown = render_markdown(build_data_card(processed))

    assert "`b`" in markdown
    assert "text file is empty" in markdown
