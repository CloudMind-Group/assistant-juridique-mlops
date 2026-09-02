"""M1 — tests du générateur de corpus synthétique.

La propriété testée en priorité est le **déterminisme**. L'équipe s'appuie
dessus concrètement : quand le remote DVC n'est pas accessible, on demande
aux autres modules de régénérer le corpus localement avec le même
`--count`, en supposant qu'ils obtiennent exactement le même jeu de
données. Si une source d'aléa entrait un jour dans ce module, cette
consigne deviendrait fausse sans que rien ne le signale.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
from pathlib import Path

from src.m1_ingestion import dataset_generator
from src.m1_ingestion.ingest import FOLDER_TO_SOURCE


@contextlib.contextmanager
def _sandbox():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            yield Path(tmp)
        finally:
            os.chdir(previous)


def _fingerprint(root: Path) -> str:
    """Empreinte stable de l'arborescence générée (chemins + contenus)."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(root)).replace("\\", "/").encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_generation_est_deterministe():
    with _sandbox():
        dataset_generator.generate_corpus(60)
        first = _fingerprint(Path("data/raw"))

    with _sandbox():
        dataset_generator.generate_corpus(60)
        second = _fingerprint(Path("data/raw"))

    assert first == second, (
        "le générateur n'est plus déterministe : la consigne « régénérez "
        "localement avec le même --count » ne tient plus"
    )


def test_le_total_est_borne_entre_50_et_100():
    with _sandbox():
        dataset_generator.generate_corpus(5)  # sous la borne basse
        assert len(list(Path("data/raw").rglob("*.txt"))) == 50

    with _sandbox():
        dataset_generator.generate_corpus(500)  # au-dessus de la borne haute
        assert len(list(Path("data/raw").rglob("*.txt"))) >= 99


def test_les_trois_sources_sont_peuplees():
    with _sandbox():
        dataset_generator.generate_corpus(60)

        for slug in ("bulletin_officiel", "jurisprudence", "contrats_types"):
            assert list((Path("data/raw") / slug).glob("*.txt")), f"{slug} vide"
            assert slug in FOLDER_TO_SOURCE


def test_chaque_document_a_un_sidecar_valide():
    with _sandbox():
        dataset_generator.generate_corpus(50)

        for text_path in Path("data/raw").rglob("*.txt"):
            sidecar = text_path.with_suffix(".txt.meta.json")
            assert sidecar.is_file(), f"sidecar manquant pour {text_path}"

            meta = json.loads(sidecar.read_text(encoding="utf-8"))
            assert set(meta).issuperset(
                {"doc_id", "title", "source", "date", "category", "language"}
            )
            assert meta["language"] in {"fr", "ar"}


def test_le_corpus_contient_du_francais_et_de_l_arabe():
    with _sandbox():
        dataset_generator.generate_corpus(60)

        langues = {
            json.loads(p.read_text(encoding="utf-8"))["language"]
            for p in Path("data/raw").rglob("*.meta.json")
        }

        assert langues == {"fr", "ar"}
