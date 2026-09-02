"""
Module 1 — Connecteurs de collecte de données.

Chaque connecteur produit des documents dans ``data/raw/<source_slug>/`` sous
la forme ``<stem>.txt`` + ``<stem>.txt.meta.json`` — exactement le contrat que
``dataset_generator.py`` utilise déjà, donc ``ingest.py`` les consomme sans
aucune modification de son côté.

⚠️ Ce fichier est un SQUELETTE : ``LegifranceConnector.fetch()`` lève
``NotImplementedError``. Brancher un vrai scraping/appel API nécessite une
revue explicite (robots.txt, CGU du site source, quotas, secrets d'API) —
volontairement laissé hors de ce squelette.

Usage prévu une fois un connecteur distant implémenté :
    python -m src.m1_ingestion.collect --source legifrance --limit 50

Usage déjà fonctionnel aujourd'hui (dépôts internes) :
    python -m src.m1_ingestion.collect --source local --limit 50
"""

from __future__ import annotations

import argparse
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

logger = logging.getLogger("m1_ingestion.collect")

RAW_DIR = Path("data/raw")


@dataclass(frozen=True)
class RawDocument:
    """Un document brut prêt à être écrit dans data/raw/<source_slug>/.

    Champs alignés sur le sidecar .meta.json que load_sidecar_metadata()
    (ingest.py) sait déjà lire — ne pas renommer sans vérifier ce contrat.
    """

    stem: str  # nom de fichier sans extension, doit être unique par source
    text: str
    title: str
    date: str  # "YYYY-MM-DD" ou "YYYY"
    category: str
    language: str  # "fr" | "ar"
    source_slug: str  # doit correspondre à une clé de FOLDER_TO_SOURCE (ingest.py)


class BaseConnector(ABC):
    """Contrat commun à tout connecteur de collecte M1."""

    source_slug: str

    @abstractmethod
    def fetch(self, *, limit: int | None = None) -> Iterator[RawDocument]:
        """Récupère les documents depuis la source. À implémenter par connecteur."""
        raise NotImplementedError

    def write_all(self, out_dir: Path = RAW_DIR, *, limit: int | None = None) -> int:
        """Écrit les documents récupérés au format attendu par ingest.py."""
        folder = out_dir / self.source_slug
        folder.mkdir(parents=True, exist_ok=True)

        written = 0
        for doc in self.fetch(limit=limit):
            text_path = folder / f"{doc.stem}.txt"
            meta_path = folder / f"{doc.stem}.txt.meta.json"

            if text_path.exists():
                logger.warning("Skipping %s: already collected", doc.stem)
                continue

            text_path.write_text(doc.text, encoding="utf-8")
            meta_path.write_text(
                json.dumps(
                    {
                        "title": doc.title,
                        "date": doc.date,
                        "category": doc.category,
                        "language": doc.language,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            written += 1
            logger.info("Collected %s -> %s", self.source_slug, doc.stem)

        return written


class LegifranceConnector(BaseConnector):
    """Connecteur pour un portail juridique officiel distant.

    TODO (bloquant avant tout usage réel) :
      - Vérifier les CGU / conditions de réutilisation du site source.
      - Vérifier robots.txt et respecter un rate-limit explicite.
      - Gérer l'authentification (clé API si applicable) via variable
        d'environnement, jamais en dur dans le code.
      - Définir la pagination / les critères de sélection des documents.
    """

    source_slug = "portails_officiels"

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url
        self.api_key = api_key

    def fetch(self, *, limit: int | None = None) -> Iterator[RawDocument]:
        raise NotImplementedError(
            "LegifranceConnector.fetch() n'est pas implémenté — voir les TODO "
            "de la classe avant tout développement réel de scraping/API."
        )


class LocalDropConnector(BaseConnector):
    """Connecteur trivial : republie des fichiers .txt déjà présents localement
    sous le format attendu. Premier connecteur réellement fonctionnel
    (dépôts PDF/DOCX internes déposés à la main), en attendant les
    connecteurs distants.
    """

    source_slug = "depots_internes"

    def __init__(self, source_dir: Path) -> None:
        self.source_dir = source_dir

    def fetch(self, *, limit: int | None = None) -> Iterator[RawDocument]:
        files = sorted(self.source_dir.glob("*.txt"))
        if limit is not None:
            files = files[:limit]
        for path in files:
            yield RawDocument(
                stem=path.stem,
                text=path.read_text(encoding="utf-8"),
                title=path.stem.replace("_", " ").title(),
                date="1900",
                category="non_categorise",
                language="fr",
                source_slug=self.source_slug,
            )


CONNECTORS: dict[str, type[BaseConnector]] = {
    "legifrance": LegifranceConnector,
    "local": LocalDropConnector,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M1 data collection connectors")
    parser.add_argument("--source", choices=sorted(CONNECTORS), required=True)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if args.source == "legifrance":
        raise SystemExit(
            "legifrance: squelette non implémenté, voir les TODO de LegifranceConnector."
        )

    connector = CONNECTORS[args.source](Path("data/dropzone"))
    count = connector.write_all(limit=args.limit)
    logger.info("Collecte terminée: %d documents écrits", count)


if __name__ == "__main__":
    main()
