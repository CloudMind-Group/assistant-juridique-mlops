"""
Module 1 — Segmentation structurelle des textes juridiques.

Détecte les frontières d'articles et d'alinéas (fr/ar) dans un document
nettoyé, et découpe le texte en segments correspondants.

Ce module ne modifie **pas** le contrat de sortie existant : `documents/`
et `metadata.jsonl` restent identiques. Les segments sont écrits dans un
fichier additionnel `data/processed/segments.jsonl`, que M2 peut utiliser
pour un chunking respectant la structure légale (un article coupé en son
milieu perd son sens juridique).

Point de conception — précision avant rappel :
    Un texte juridique cite constamment d'autres articles
    (« conformément à l'article 41 du Code du Travail », « المنصوص عليها في
    المادة 5 »). Ces mentions sont des *renvois*, pas des titres de section.
    Les traiter comme des frontières découperait le document à des endroits
    arbitraires. La détection exige donc que le marqueur soit en position de
    titre : début du texte, début de ligne, ou après une ponctuation de fin
    de phrase. Un renvoi en milieu de phrase ne déclenche jamais de coupure.

    Alternative rejetée : détecter tout « Article \\d+ » sans condition de
    position. Plus simple, mais chaque renvoi devenait une fausse frontière —
    exactement le mode d'échec constaté sur les règles d'anonymisation, où
    une règle trop large a masqué du vocabulaire juridique ordinaire.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Ponctuations qui terminent une phrase, en français comme en arabe. Un
# marqueur qui suit l'une d'elles est un titre ; un marqueur en milieu de
# phrase est un renvoi.
_BOUNDARY = r"(?:^|(?<=[.;:!?؟۔\n]))\s*"

# « Article 4 », « Article 12 bis ». Majuscule obligatoire : « l'article 41 »
# en minuscule est un renvoi, jamais un titre.
_ARTICLE_FR = re.compile(
    _BOUNDARY + r"(?P<label>Article\s+(?P<number>\d+(?:\s+(?:bis|ter|quater))?))\b",
    re.MULTILINE,
)

# « المادة 3 ». L'arabe n'a pas de casse : c'est la condition de position
# qui écarte les renvois (« في المادة 5 » suit « في », pas une ponctuation).
_ARTICLE_AR = re.compile(
    _BOUNDARY + r"(?P<label>المادة\s+(?P<number>\d+))\b",
    re.MULTILINE,
)

_ALINEA_FR = re.compile(
    _BOUNDARY + r"(?P<label>(?:Alinéa|Al\.)\s*(?P<number>\d+))\b",
    re.MULTILINE,
)

_ALINEA_AR = re.compile(
    _BOUNDARY + r"(?P<label>الفقرة\s+(?P<number>\d+))\b",
    re.MULTILINE,
)

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_ARTICLE_FR, "article"),
    (_ARTICLE_AR, "article"),
    (_ALINEA_FR, "alinea"),
    (_ALINEA_AR, "alinea"),
)


@dataclass(frozen=True)
class Segment:
    """Un article ou alinéa détecté, avec sa position dans le texte source."""

    kind: str  # "article" | "alinea"
    label: str  # libellé tel qu'il apparaît, ex. "Article 3" / "المادة 3"
    number: str  # numéro extrait, ex. "3"
    start: int  # offset du début du marqueur dans le texte nettoyé
    end: int  # offset de fin du segment (début du marqueur suivant, ou fin)
    text: str  # contenu du segment, marqueur inclus

    def to_dict(self, doc_id: str, index: int) -> dict[str, object]:
        """Représentation sérialisable pour `segments.jsonl`."""
        return {
            "doc_id": doc_id,
            "segment_index": index,
            "kind": self.kind,
            "label": self.label,
            "number": self.number,
            "start": self.start,
            "end": self.end,
            "text": self.text,
        }


def find_markers(text: str) -> list[tuple[int, int, str, str, str]]:
    """Retourne les marqueurs structurels détectés, triés par position.

    Chaque entrée : (start, end_du_marqueur, kind, label, number).
    Les doublons de position (deux motifs qui matchent au même offset) sont
    résolus en gardant le premier motif déclaré.
    """
    seen_starts: set[int] = set()
    markers: list[tuple[int, int, str, str, str]] = []

    for pattern, kind in _PATTERNS:
        for match in pattern.finditer(text):
            start = match.start("label")
            if start in seen_starts:
                continue
            seen_starts.add(start)
            markers.append(
                (
                    start,
                    match.end("label"),
                    kind,
                    match.group("label").strip(),
                    match.group("number").strip(),
                )
            )

    markers.sort(key=lambda item: item[0])
    return markers


def segment_document(text: str) -> list[Segment]:
    """Découpe `text` en segments article/alinéa.

    Retourne une liste vide si aucun marqueur structurel n'est détecté — le
    document reste alors exploitable tel quel par M2, sans segmentation.
    Le texte qui précède le premier marqueur (titre, en-tête de juridiction)
    n'est volontairement rattaché à aucun segment : ce n'est pas un article.
    """
    markers = find_markers(text)
    if not markers:
        return []

    segments: list[Segment] = []
    for position, (start, _marker_end, kind, label, number) in enumerate(markers):
        end = markers[position + 1][0] if position + 1 < len(markers) else len(text)
        segments.append(
            Segment(
                kind=kind,
                label=label,
                number=number,
                start=start,
                end=end,
                text=text[start:end].strip(),
            )
        )

    return segments
