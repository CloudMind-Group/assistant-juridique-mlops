"""M1 — tests des connecteurs de collecte.

Le point vérifié ici n'est pas « le connecteur télécharge », c'est
« ce qu'il écrit est réellement ingérable ». Un connecteur qui produit des
fichiers qu'`ingest.py` ignore ensuite silencieusement ne sert à rien —
c'est le défaut qui avait été trouvé en testant `LocalDropConnector` avant
l'ajout de `depots_internes` à `FOLDER_TO_SOURCE`.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

import pytest

from src.m1_ingestion.collect import (
    CONNECTORS,
    LegifranceConnector,
    LocalDropConnector,
)
from src.m1_ingestion.ingest import FOLDER_TO_SOURCE, IngestionPipeline


@contextlib.contextmanager
def _sandbox():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            yield Path(tmp)
        finally:
            os.chdir(previous)


def _dropzone(*documents: tuple[str, str]) -> Path:
    zone = Path("dropzone")
    zone.mkdir(parents=True, exist_ok=True)
    for stem, text in documents:
        (zone / f"{stem}.txt").write_text(text, encoding="utf-8")
    return zone


TEXTE = "Article 1 - Le present contrat regit les relations entre les parties."


def test_local_drop_ecrit_texte_et_sidecar():
    with _sandbox():
        connector = LocalDropConnector(_dropzone(("doc_a", TEXTE)))
        written = connector.write_all(Path("raw"))

        assert written == 1
        folder = Path("raw") / connector.source_slug
        assert (folder / "doc_a.txt").read_text(encoding="utf-8") == TEXTE

        sidecar = json.loads((folder / "doc_a.txt.meta.json").read_text(encoding="utf-8"))
        assert set(sidecar) == {"title", "date", "category", "language"}


def test_limit_borne_le_nombre_de_documents():
    with _sandbox():
        connector = LocalDropConnector(
            _dropzone(("a", TEXTE), ("b", TEXTE), ("c", TEXTE))
        )

        assert connector.write_all(Path("raw"), limit=2) == 2


def test_document_deja_collecte_est_ignore():
    """Relancer la collecte ne doit pas réécrire ce qui existe déjà."""
    with _sandbox():
        connector = LocalDropConnector(_dropzone(("doc_a", TEXTE)))

        assert connector.write_all(Path("raw")) == 1
        assert connector.write_all(Path("raw")) == 0


def test_le_slug_du_connecteur_est_connu_de_l_ingestion():
    """Sans cette correspondance, ingest.py ignore les fichiers collectés."""
    for connector_cls in CONNECTORS.values():
        assert connector_cls.source_slug in FOLDER_TO_SOURCE, (
            f"{connector_cls.__name__}.source_slug='{connector_cls.source_slug}' "
            "n'est pas dans FOLDER_TO_SOURCE : ingest.py ne saura pas quoi en faire"
        )


def test_bout_en_bout_collecte_puis_ingestion():
    with _sandbox():
        LocalDropConnector(_dropzone(("doc_a", TEXTE))).write_all(Path("raw"))

        result = IngestionPipeline(Path("raw"), Path("out")).run()

        assert result.processed == 1
        assert result.skipped == 0
        record = json.loads(Path("out/metadata.jsonl").read_text(encoding="utf-8").strip())
        assert record["source"] == "Dépôt Interne"


def test_legifrance_refuse_explicitement_tant_qu_il_est_un_squelette():
    connector = LegifranceConnector("https://exemple.invalid")

    with pytest.raises(NotImplementedError):
        list(connector.fetch())
