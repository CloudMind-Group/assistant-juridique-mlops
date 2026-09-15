"""M1 — tests du connecteur local multi-formats.

`LocalDropConnector` ne lisait que `.txt`, alors que l'énoncé du module
annonce des « dépôts PDF/DOCX internes ». Ces tests verrouillent le support
des trois formats et, surtout, le fait que l'extraction passe bien par
`extract_text_from_file()` — sinon le repli OCR déjà en place serait
contourné et un PDF scanné ressortirait vide.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

import pytest

from src.m1_ingestion.collect import LocalDropConnector
from src.m1_ingestion.ingest import IngestionPipeline

fitz = pytest.importorskip("fitz", reason="PyMuPDF requis pour les cas PDF")
docx = pytest.importorskip("docx", reason="python-docx requis pour les cas DOCX")


@contextlib.contextmanager
def _sandbox():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            yield Path(tmp)
        finally:
            os.chdir(previous)


TEXTE_PDF = "Article 1 - Le present contrat regit les relations entre les parties."
TEXTE_DOCX = "Article 1 - Objet du contrat de prestation de services."
TEXTE_TXT = "Article 1 - Note interne relative aux conditions de travail."


def _dropzone_multiformat() -> Path:
    zone = Path("dropzone")
    zone.mkdir(parents=True, exist_ok=True)

    (zone / "note.txt").write_text(TEXTE_TXT, encoding="utf-8")

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), TEXTE_PDF)
    pdf.save(str(zone / "contrat.pdf"))
    pdf.close()

    document = docx.Document()
    document.add_paragraph(TEXTE_DOCX)
    document.save(str(zone / "accord.docx"))

    return zone


def test_les_trois_formats_sont_collectes():
    with _sandbox():
        written = LocalDropConnector(_dropzone_multiformat()).write_all(Path("raw"))

        assert written == 3
        collected = {p.stem for p in (Path("raw") / "depots_internes").glob("*.txt")}
        assert collected == {"note", "contrat", "accord"}


def test_le_contenu_du_pdf_est_reellement_extrait():
    """Un .txt vide généré à partir d'un PDF signifierait que l'extraction
    n'a pas été déléguée à extract_text_from_file()."""
    with _sandbox():
        LocalDropConnector(_dropzone_multiformat()).write_all(Path("raw"))
        contenu = (Path("raw/depots_internes/contrat.txt")).read_text(encoding="utf-8")

        assert "present contrat regit" in contenu


def test_le_contenu_du_docx_est_reellement_extrait():
    with _sandbox():
        LocalDropConnector(_dropzone_multiformat()).write_all(Path("raw"))
        contenu = (Path("raw/depots_internes/accord.txt")).read_text(encoding="utf-8")

        assert "prestation de services" in contenu


def test_les_sidecars_meta_json_ne_sont_pas_collectes():
    """Un .meta.json est une métadonnée, pas un document."""
    with _sandbox():
        zone = _dropzone_multiformat()
        (zone / "note.txt.meta.json").write_text('{"date": "2024-01-01"}', encoding="utf-8")

        assert LocalDropConnector(zone).write_all(Path("raw")) == 3


def test_un_format_non_supporte_est_ignore():
    with _sandbox():
        zone = _dropzone_multiformat()
        (zone / "tableau.xlsx").write_text("pas un format supporte", encoding="utf-8")

        assert LocalDropConnector(zone).write_all(Path("raw")) == 3


def test_un_fichier_corrompu_n_interrompt_pas_la_collecte():
    """Même politique que ingest.py : on saute, on continue."""
    with _sandbox():
        zone = _dropzone_multiformat()
        (zone / "casse.pdf").write_text("CECI N'EST PAS UN PDF", encoding="utf-8")

        assert LocalDropConnector(zone).write_all(Path("raw")) == 3


def test_un_document_sans_texte_extractible_est_ignore():
    """Sans Tesseract, un PDF scanné ressort vide : ne pas écrire un
    document vide qui échouerait plus loin dans quality.py."""
    with _sandbox():
        zone = Path("dropzone")
        zone.mkdir()
        pdf = fitz.open()
        pdf.new_page()  # page blanche, aucune couche texte
        pdf.save(str(zone / "scan.pdf"))
        pdf.close()

        assert LocalDropConnector(zone).write_all(Path("raw")) == 0


def test_bout_en_bout_multiformat_jusqu_a_l_ingestion():
    with _sandbox():
        LocalDropConnector(_dropzone_multiformat()).write_all(Path("raw"))

        result = IngestionPipeline(Path("raw"), Path("out")).run()

        assert result.processed == 3
        assert result.skipped == 0

        records = [
            json.loads(line)
            for line in Path("out/metadata.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert len(records) == 3
        assert {r["source"] for r in records} == {"Dépôt Interne"}
