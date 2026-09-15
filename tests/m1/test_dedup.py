"""M1 — tests de dé-duplication du corpus.

Le test le plus important de ce fichier est
`test_deux_jugements_distincts_ne_sont_pas_dedupliques` : il verrouille
l'ordre dedup → anonymisation. Inversé, le masquage remplace les noms par
`[NOM]`, deux jugements qui ne diffèrent que par les parties deviennent
identiques, et le second serait supprimé silencieusement du corpus.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

from src.m1_ingestion.ingest import IngestionPipeline


@contextlib.contextmanager
def _sandbox():
    """cwd jetable : DocumentMetadata refuse les file_path absolus."""
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            yield Path(tmp)
        finally:
            os.chdir(previous)


def _write_doc(stem: str, text: str, raw_dir: Path = Path("raw")) -> None:
    folder = raw_dir / "jurisprudence"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{stem}.txt").write_text(text, encoding="utf-8")
    (folder / f"{stem}.txt.meta.json").write_text(
        json.dumps({"date": "2024-01-01", "category": "Droit du travail"}),
        encoding="utf-8",
    )


JUGEMENT = (
    "Attendu que la rupture est abusive ; Par ces motifs, la Cour condamne "
    "l'employeur au versement des indemnités légales prévues par la loi."
)


def test_document_identique_est_deduplique():
    with _sandbox():
        _write_doc("original", JUGEMENT)
        _write_doc("copie", JUGEMENT)

        result = IngestionPipeline(Path("raw"), Path("out")).run()

        assert result.processed == 1
        assert result.duplicates == 1
        assert len(result.duplicate_files) == 1
        assert result.duplicate_files[0]["duplicate_of"]


def test_dedup_ignore_les_differences_d_espacement():
    """Le hash porte sur le texte nettoyé, pas sur le brut."""
    with _sandbox():
        _write_doc("serre", JUGEMENT)
        _write_doc("espace", JUGEMENT.replace(" ; ", "  ;   "))

        result = IngestionPipeline(Path("raw"), Path("out")).run()

        assert result.processed == 1
        assert result.duplicates == 1


def test_deux_jugements_distincts_ne_sont_pas_dedupliques():
    """Garde-fou : dédupliquer APRÈS anonymisation les rendrait identiques."""
    with _sandbox():
        _write_doc(
            "affaire_a",
            "Le salarié Youssef Idrissi a été licencié. " + JUGEMENT,
        )
        _write_doc(
            "affaire_b",
            "Le salarié Karim Alaoui a été licencié. " + JUGEMENT,
        )

        result = IngestionPipeline(Path("raw"), Path("out")).run()

        assert result.processed == 2, (
            "deux affaires distinctes ont été fusionnées — l'ordre "
            "dedup/anonymisation est probablement inversé"
        )
        assert result.duplicates == 0


def test_documents_distincts_sont_tous_conserves():
    with _sandbox():
        _write_doc("a", JUGEMENT)
        _write_doc("b", "Attendu que le contrat de bail est résilié de plein droit.")

        result = IngestionPipeline(Path("raw"), Path("out")).run()

        assert result.processed == 2
        assert result.duplicates == 0


def test_le_rapport_d_ingestion_expose_les_doublons():
    with _sandbox():
        _write_doc("original", JUGEMENT)
        _write_doc("copie", JUGEMENT)

        IngestionPipeline(Path("raw"), Path("out")).run()
        report = json.loads(Path("out/ingestion_report.json").read_text(encoding="utf-8"))

        assert report["duplicates"] == 1
        assert report["duplicate_files"][0]["duplicate_of"]
        assert report["total_files_discovered"] == 2


def test_segments_ecrits_dans_segments_jsonl():
    with _sandbox():
        _write_doc("contrat", "Article 1 - Objet. Article 2 - Durée du contrat.")

        result = IngestionPipeline(Path("raw"), Path("out")).run()
        lines = Path("out/segments.jsonl").read_text(encoding="utf-8").splitlines()

        assert result.segments == 2
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["kind"] == "article"
        assert first["number"] == "1"
        assert first["doc_id"]


def test_documents_et_metadata_restent_inchanges():
    """Le contrat de sortie lu par M2 ne doit pas bouger."""
    with _sandbox():
        _write_doc("doc", "Article 1 - Objet du contrat de bail.")

        IngestionPipeline(Path("raw"), Path("out")).run()
        record = json.loads(Path("out/metadata.jsonl").read_text(encoding="utf-8").strip())

        assert set(record).issuperset(
            {"doc_id", "title", "source", "date", "category", "language", "file_path"}
        )
        assert Path(record["file_path"]).is_file()
