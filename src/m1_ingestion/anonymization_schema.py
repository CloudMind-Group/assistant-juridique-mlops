"""
PII detection & masking schema for Moroccan legal texts — RGPD/loi 09-08.

Collaboration: Taha. Defines the Pydantic rule schema used to detect and
mask personally identifiable information (names, CIN, phone numbers,
addresses, emails) that can appear in raw jurisprudence / contract text
before it is exposed to downstream modules (M2 indexing, M5/M6).

This module only defines/enforces the *rule schema* and provides a
reference regex-based detector built on top of it — it is not a full NLP
NER pipeline. Rules are intentionally data-driven (Pydantic models) so
Taha's team can extend/tune them (e.g. swap in a spaCy/NER-backed rule)
without touching the ingestion pipeline.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Pattern

from pydantic import BaseModel, Field, field_validator


class PIIType(str, Enum):
    NOM = "nom"
    CIN = "cin"
    TELEPHONE = "telephone"
    ADRESSE = "adresse"
    EMAIL = "email"


class MaskingStrategy(str, Enum):
    REDACT_FULL = "redact_full"  # replace entire match with placeholder
    PARTIAL_MASK = "partial_mask"  # keep first/last chars, mask the middle
    HASH = "hash"  # replace with a short deterministic hash token
    PLACEHOLDER = "placeholder"  # replace with a fixed tag, e.g. [NOM]


class PIIPattern(BaseModel):
    """A single detection rule: PII type + regex + how to mask a match."""

    pii_type: PIIType
    description: str = Field(..., min_length=1)
    regex: str = Field(..., min_length=1)
    masking_strategy: MaskingStrategy = MaskingStrategy.PLACEHOLDER
    placeholder: str = Field(
        default="[MASQUE]", description="Used when masking_strategy=placeholder"
    )
    flags: int = re.UNICODE

    model_config = {"use_enum_values": True}

    @field_validator("regex")
    @classmethod
    def regex_must_compile(cls, v: str) -> str:
        try:
            re.compile(v, re.UNICODE)
        except re.error as exc:
            raise ValueError(f"invalid regex {v!r}: {exc}") from exc
        return v

    def compiled(self) -> Pattern[str]:
        return re.compile(self.regex, self.flags)


class PIIMatch(BaseModel):
    pii_type: PIIType
    value: str
    start: int
    end: int
    rule_description: str


class AnonymizationRuleSet(BaseModel):
    """Ordered collection of PII rules applied to a document's text."""

    rules: list[PIIPattern] = Field(default_factory=list)

    def rules_for(self, pii_type: PIIType) -> list[PIIPattern]:
        return [r for r in self.rules if r.pii_type == pii_type]


# --------------------------------------------------------------------------
# Default rule set for Moroccan legal documents (fr/ar mixed corpora).
# --------------------------------------------------------------------------

DEFAULT_RULES: list[PIIPattern] = [
    PIIPattern(
        pii_type=PIIType.CIN,
        description="Carte d'Identité Nationale marocaine (ex: AB123456, A-123456)",
        regex=r"\b[A-Za-z]{1,2}[\s\-]?\d{5,6}\b",
        masking_strategy=MaskingStrategy.PLACEHOLDER,
        placeholder="[CIN]",
    ),
    PIIPattern(
        pii_type=PIIType.TELEPHONE,
        description="Numéro de téléphone marocain (fixe/mobile, +212 ou 0 local)",
        regex=r"(?:\+212|00212|0)[\s.\-]?[5-7](?:[\s.\-]?\d{2}){4}\b",
        masking_strategy=MaskingStrategy.PARTIAL_MASK,
        placeholder="[TELEPHONE]",
    ),
    PIIPattern(
        pii_type=PIIType.EMAIL,
        description="Adresse e-mail",
        regex=r"\b[\w.\-]+@[\w\-]+\.[A-Za-z]{2,}\b",
        masking_strategy=MaskingStrategy.PLACEHOLDER,
        placeholder="[EMAIL]",
    ),
    PIIPattern(
        pii_type=PIIType.NOM,
        description="Nom précédé d'une civilité (M., Mme, Maître, Monsieur, Madame)",
        regex=r"\b(?:M\.|Mme\.?|Mlle\.?|Me\.?|Monsieur|Madame|Ma[iî]tre)\s+"
        r"[A-ZÀ-Ý][\wà-ÿ'\-]+(?:\s+[A-ZÀ-Ý][\wà-ÿ'\-]+){0,2}",
        masking_strategy=MaskingStrategy.PLACEHOLDER,
        placeholder="[NOM]",
    ),
    PIIPattern(
        pii_type=PIIType.ADRESSE,
        description="Adresse postale marocaine (Rue/Avenue/Hay/Quartier/Lotissement/Résidence + libellé)",
        regex=r"\b(?:Rue|Avenue|Bd|Boulevard|Hay|Quartier|Lotissement|R[ée]sidence|Angle)\s+"
        r"[A-Za-zÀ-ÿ0-9,'\-\s]{3,60}?(?=[.,\n]|$)",
        masking_strategy=MaskingStrategy.PLACEHOLDER,
        placeholder="[ADRESSE]",
    ),
    PIIPattern(
        pii_type=PIIType.NOM,
        description="اسم مسبوق بلقب (السيد/السيدة/الأستاذ)",
        regex=r"(?:السيد|السيدة|الأستاذ|الأستاذة)\s+[؀-ۿ]{2,}(?:\s+[؀-ۿ]{2,}){0,2}",
        masking_strategy=MaskingStrategy.PLACEHOLDER,
        placeholder="[NOM]",
    ),
]

DEFAULT_RULE_SET = AnonymizationRuleSet(rules=DEFAULT_RULES)


def detect_pii(text: str, rule_set: AnonymizationRuleSet = DEFAULT_RULE_SET) -> list[PIIMatch]:
    """Return every PII match found in `text`, ordered by position."""
    matches: list[PIIMatch] = []
    for rule in rule_set.rules:
        for m in rule.compiled().finditer(text):
            matches.append(
                PIIMatch(
                    pii_type=rule.pii_type,
                    value=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    rule_description=rule.description,
                )
            )
    return sorted(matches, key=lambda mm: mm.start)


def _mask_value(value: str, rule: PIIPattern) -> str:
    if rule.masking_strategy == MaskingStrategy.PARTIAL_MASK:
        digits = re.sub(r"\D", "", value)
        if len(digits) <= 4:
            return rule.placeholder
        return f"{digits[:2]}{'*' * (len(digits) - 4)}{digits[-2:]}"
    if rule.masking_strategy == MaskingStrategy.HASH:
        return f"[{rule.pii_type.value.upper()}_{abs(hash(value)) % 100000:05d}]"
    # REDACT_FULL and PLACEHOLDER both collapse to the configured placeholder.
    return rule.placeholder


def anonymize_text(text: str, rule_set: AnonymizationRuleSet = DEFAULT_RULE_SET) -> str:
    """Apply every rule in `rule_set` and return the masked text.

    Rules are applied left-to-right over non-overlapping spans found on the
    original text, so masking one match never shifts the offsets used to
    detect the next one.
    """
    matches = detect_pii(text, rule_set)
    if not matches:
        return text

    rule_by_description = {r.description: r for r in rule_set.rules}
    out: list[str] = []
    cursor = 0
    last_end = -1
    for match in matches:
        if match.start < last_end:
            continue  # skip overlapping match (already covered)
        rule = rule_by_description[match.rule_description]
        out.append(text[cursor:match.start])
        out.append(_mask_value(match.value, rule))
        cursor = match.end
        last_end = match.end
    out.append(text[cursor:])
    return "".join(out)
