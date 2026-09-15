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
    """A single detection rule: PII type + regex + how to mask a match.

    A rule may expose a named group ``(?P<pii>...)``. When present, only that
    group is masked and the surrounding context is preserved — this is what
    lets a rule anchor on a legal marker without destroying it. For instance
    ``"Le salarié Youssef Idrissi"`` becomes ``"Le salarié [NOM]"``: the role,
    which carries the legal meaning, survives. Rules without the group mask
    the whole match.
    """

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
    """A detected span. ``start``/``end`` delimit what will actually be masked
    — the ``pii`` group when the rule defines one, the whole match otherwise.
    """

    pii_type: PIIType
    value: str
    start: int
    end: int
    rule_index: int
    rule_description: str


class AnonymizationRuleSet(BaseModel):
    """Ordered collection of PII rules applied to a document's text."""

    rules: list[PIIPattern] = Field(default_factory=list)

    def rules_for(self, pii_type: PIIType) -> list[PIIPattern]:
        return [r for r in self.rules if r.pii_type == pii_type]


# --------------------------------------------------------------------------
# Default rule set for Moroccan legal documents (fr/ar mixed corpora).
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Arabic
#
# The French rules use the capital initial of [A-ZÀ-Ý] as the signal that a
# word is a proper noun, which is what tells them where a name ends. Arabic
# has no case, so an Arabic rule anchored on a title has no boundary other
# than counting words — and it therefore swallows whatever follows the name.
# Measured before this list existed: "السيد أحمد بنعلي تقدم بمقال" masked the
# verb تقدم along with the name, leaving a judgment without its operative act.
#
# These words act as that missing boundary: the name match stops when it meets
# one. The list covers the verbs that habitually follow a party's name in a
# decision, plus the function words that join clauses.
# --------------------------------------------------------------------------

ARABIC_STOPWORDS = (
    # verbes fréquents après le nom d'une partie
    "تقدم", "تقدمت", "حضر", "حضرت", "أدلى", "أدلت", "رفض", "رفضت",
    "قدم", "قدمت", "صرح", "صرحت", "أكد", "أكدت", "طلب", "طلبت",
    "دفع", "دفعت", "تمسك", "تمسكت", "أقر", "أقرت", "ادعى", "ادعت",
    "استأنف", "استأنفت", "قال", "قالت", "ذكر", "ذكرت", "أجاب", "أجابت",
    "وقع", "وقعت", "التمس", "التمست", "نازع", "نازعت",
    # mots-outils et vocabulaire procédural
    "أن", "إن", "بأن", "قد", "وقد", "كان", "كانت", "لم", "لا", "ما",
    "في", "من", "على", "إلى", "عن", "مع", "بعد", "قبل", "حيث", "وحيث",
    "الذي", "التي", "هذا", "هذه", "ذلك", "بذلك",
    "المحكمة", "الجلسة", "الدعوى", "الحكم", "القرار", "الطلب", "الملف",
    "القانون", "الفصل", "المادة", "الظهير", "المغرب", "الرباط",
)

_AR_STOP = "|".join(ARABIC_STOPWORDS)
# A name word: two or more Arabic letters that are not one of the stopwords.
AR_NAME_WORD = rf"(?!(?:{_AR_STOP})\b)[؀-ۿ]{{2,}}"

# Identifiers that share the CIN's shape (letters + 5-6 digits) but designate a
# case, a company or a publication — never a person. Masking them would corrupt
# the citation the assistant is supposed to produce, so they are excluded from
# the context-free CIN rule.
LEGAL_REF_PREFIXES = ("RC", "BO", "RG", "TP", "IF", "ICE", "TVA", "CNSS", "AMO")

DEFAULT_RULES: list[PIIPattern] = [
    PIIPattern(
        pii_type=PIIType.CIN,
        description="CIN annoncée par sa mention (ex: « CIN n° AB123456 », « البطاقة الوطنية AB123456 »)",
        regex=(
            # CNIE est l'appellation officielle actuelle (Carte Nationale
            # d'Identité Électronique) : son ordre de lettres C-N-I-E ne
            # correspond pas au motif C-I-N-E, d'où l'alternative explicite.
            r"(?:C\.?\s?N\.?\s?I\.?\s?E\.?"
            r"|C\.?\s?I\.?\s?N\.?\s?E?\.?"
            r"|carte\s+(?:nationale|d'identit[ée])(?:\s+d'identit[ée])?"
            r"(?:\s+nationale)?(?:\s+[ée]lectronique)?"
            r"|بطاقة\s+التعريف\s+الوطنية|البطاقة\s+الوطنية)"
            # `n` seul et `n.` sont fréquents : le signe degré disparaît en
            # sortie d'OCR et dans le texte brut.
            r"\s*(?:n[°o]?\.?|رقم)?\s*:?\s*(?P<pii>[A-Za-z]{1,2}[\s\-]?\d{5,6})\b"
        ),
        masking_strategy=MaskingStrategy.PLACEHOLDER,
        placeholder="[CIN]",
    ),
    PIIPattern(
        pii_type=PIIType.CIN,
        description="CIN isolée, sans mention (ex: AB123456)",
        # Uppercase, and separated at most by a hyphen — jamais par un espace,
        # sans quoi une préposition suivie d'un montant ("de 150000 dirhams")
        # serait prise pour un identifiant. Le trait d'union est une graphie
        # courante de la CIN et ne rouvre pas ce défaut. Le lookahead écarte
        # les références d'affaire, d'entreprise et de publication, avec leur
        # trait d'union éventuel.
        regex=(
            r"\b(?!(?:" + "|".join(LEGAL_REF_PREFIXES) + r")-?\d)"
            r"[A-Z]{1,2}-?\d{5,6}\b"
        ),
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
        pii_type=PIIType.NOM,
        description="Nom précédé de sa qualité procédurale (ex: « le salarié Youssef Idrissi »)",
        # The role marker is matched but left in place — only the group is
        # masked. "Le salarié X" -> "Le salarié [NOM]" keeps the legal fact.
        regex=(
            r"(?i:demandeur|demanderesse|d[ée]fendeur|d[ée]fenderesse"
            r"|requ[ée]rante?|salari[ée]e?|t[ée]moin|appelante?|intim[ée]e?"
            r"|employ[ée]e?|pr[ée]venue?|inculp[ée]e?)"
            r"\s*:?\s+(?P<pii>[A-ZÀ-Ý][\wà-ÿ'\-]+(?:\s+[A-ZÀ-Ý][\wà-ÿ'\-]+){0,2})"
        ),
        masking_strategy=MaskingStrategy.PLACEHOLDER,
        placeholder="[NOM]",
    ),
    PIIPattern(
        pii_type=PIIType.NOM,
        description="Partie introduite par « ENTRE » dans un contrat ou un jugement",
        regex=(
            r"\bENTRE\s*:?\s*"
            r"(?P<pii>[A-ZÀ-Ý][\wà-ÿ'\-]+(?:\s+[A-ZÀ-Ý][\wà-ÿ'\-]+){0,2})"
        ),
        masking_strategy=MaskingStrategy.PLACEHOLDER,
        placeholder="[NOM]",
    ),
    PIIPattern(
        pii_type=PIIType.NOM,
        description="اسم مسبوق بصفته في الدعوى ثم نقطتين (الشاهد: أحمد بنعلي)",
        # Le deux-points est exigé, et c'est le cœur du correctif de l'issue
        # #31. Une qualité procédurale suivie de mots arabes n'est **pas** un
        # indice de nom : « المشغل ملزم بأداء التعويضات » a exactement la même
        # forme que « الشاهد رشيد العمراني أدلى ». Le français s'en sort grâce
        # à la majuscule du nom propre ; l'arabe n'a pas cet équivalent, et
        # aucun réglage de la fenêtre de mots ne sépare les deux cas — mesuré :
        # toute variante positionnelle attrape les 3 noms d'essai et détruit
        # les 6 phrases juridiques d'essai, sans milieu.
        #
        # Le deux-points, lui, est un vrai signal : il n'apparaît que dans les
        # listes de parties. On y perd du rappel — un nom nu après une qualité
        # n'est plus détecté par cette règle — et c'est un arbitrage assumé :
        # le sur-masquage corrompt le corpus en silence, le sous-masquage est
        # borné, documenté (E-01) et rattrapé par la propagation dès que le
        # nom est ancré une fois par un titre ailleurs dans le document.
        regex=(
            r"(?:الشاهد|المدعى\s+عليه|المدعي|الطالب|المطلوب|الأجير|المشغل|المتهم)"
            rf"\s*:\s*(?P<pii>{AR_NAME_WORD}(?:\s+{AR_NAME_WORD}){{0,2}})"
        ),
        masking_strategy=MaskingStrategy.PLACEHOLDER,
        placeholder="[NOM]",
    ),
    PIIPattern(
        pii_type=PIIType.NOM,
        description="اسم مسبوق بصفته ثم بلقب (الشاهد السيد أحمد بنعلي)",
        # Second ancrage fiable : la qualité suivie d'un titre. Le titre est
        # le signal, la qualité n'est là que pour ne pas couper la phrase.
        regex=(
            r"(?:الشاهد|المدعى\s+عليه|المدعي|الطالب|المطلوب|الأجير|المشغل|المتهم)"
            r"\s+(?:السيد|السيدة|الأستاذ|الأستاذة)\s+"
            rf"(?P<pii>{AR_NAME_WORD}(?:\s+{AR_NAME_WORD}){{0,2}})"
        ),
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
        # Pas de groupe `pii` : la civilité est masquée avec le nom, comme le
        # fait la règle française. Ce que la liste de mots-outils change ici,
        # c'est uniquement où la correspondance s'arrête.
        regex=(
            r"(?:السيد|السيدة|الأستاذ|الأستاذة)\s+"
            rf"{AR_NAME_WORD}(?:\s+{AR_NAME_WORD}){{0,2}}"
        ),
        masking_strategy=MaskingStrategy.PLACEHOLDER,
        placeholder="[NOM]",
    ),
]

DEFAULT_RULE_SET = AnonymizationRuleSet(rules=DEFAULT_RULES)


def detect_pii(text: str, rule_set: AnonymizationRuleSet = DEFAULT_RULE_SET) -> list[PIIMatch]:
    """Return every PII match found in `text`, ordered by position.

    Ties are broken by span length, longest first, so that when two rules fire
    at the same offset the more complete one is the one applied.
    """
    matches: list[PIIMatch] = []
    for index, rule in enumerate(rule_set.rules):
        compiled = rule.compiled()
        targets_group = "pii" in compiled.groupindex
        for m in compiled.finditer(text):
            start, end = (m.span("pii") if targets_group else m.span())
            matches.append(
                PIIMatch(
                    pii_type=rule.pii_type,
                    value=text[start:end],
                    start=start,
                    end=end,
                    rule_index=index,
                    rule_description=rule.description,
                )
            )
    return sorted(matches, key=lambda mm: (mm.start, -(mm.end - mm.start)))


def _mask_value(value: str, rule: PIIPattern) -> str:
    if rule.masking_strategy == MaskingStrategy.PARTIAL_MASK:
        digits = re.sub(r"\D", "", value)
        if len(digits) <= 4:
            return rule.placeholder
        return f"{digits[:2]}{'*' * (len(digits) - 4)}{digits[-2:]}"
    if rule.masking_strategy == MaskingStrategy.HASH:
        # `use_enum_values` stores pii_type as a plain string, so read it as one.
        return f"[{str(rule.pii_type).upper()}_{abs(hash(value)) % 100000:05d}]"
    # REDACT_FULL and PLACEHOLDER both collapse to the configured placeholder.
    return rule.placeholder


# --------------------------------------------------------------------------
# Name propagation
#
# The anchored rules above need a civility or a procedural role to fire. In a
# real judgment, a party is introduced once — "Monsieur Ahmed Benali" — and
# then referred to bare for pages: "Benali soutient que…". The anchored rules
# catch the introduction and miss every repetition, which is where most of the
# residual exposure lives.
#
# Propagation closes that gap without a NER model: every token of a name found
# by an anchored rule is masked wherever else it appears in the same document.
# Only anchored detections seed it, so a false positive stays local instead of
# being amplified across the text.
# --------------------------------------------------------------------------

MIN_PROPAGATION_TOKEN_LENGTH = 3

# Words that may sit inside a detected name span but must never be propagated
# on their own: honorifics carried by the civility rules, and institution or
# procedural vocabulary that would otherwise be masked throughout the document
# — destroying exactly the citations the corpus exists to provide.
NON_PROPAGABLE_TOKENS = frozenset(
    {
        "monsieur", "madame", "mademoiselle", "maitre", "maître", "mme", "mlle",
        "cour", "tribunal", "chambre", "conseil", "juridiction", "audience",
        "cassation", "appel", "instance", "premiere", "première", "commerce",
        "administratif", "social", "penal", "pénal", "civil", "royaume",
        "maroc", "rabat", "casablanca", "fes", "fès", "marrakech", "tanger",
        "societe", "société", "entreprise", "association", "ministere",
        "ministère", "etat", "état", "code", "travail", "dahir", "article",
        "loi", "decret", "décret", "arrete", "arrêté", "bulletin", "officiel",
        "demandeur", "demanderesse", "defendeur", "défendeur", "requerant",
        "requérant", "salarie", "salarié", "temoin", "témoin", "employeur",
        "appelant", "intime", "intimé", "prevenu", "prévenu", "partie",
    }
    # Même rôle côté arabe : ces mots peuvent se trouver dans un empan détecté
    # sans être des noms, et les propager les effacerait du document entier.
    | set(ARABIC_STOPWORDS)
    | {"السيد", "السيدة", "الأستاذ", "الأستاذة", "الشاهد", "المدعي", "الأجير", "المتهم"}
)

# Latin token: a capital initial is what marks a proper noun. Arabic has no
# case, so Arabic tokens are taken by script and filtered by the stopword list
# below — without that filter, propagating a word like حيث would mask it
# throughout the document, which is the failure mode the Latin exclusion list
# exists to prevent.
_NAME_TOKEN_RE = re.compile(r"[A-ZÀ-Ý][\wà-ÿ'\-]+|[؀-ۿ]{3,}", re.UNICODE)

# Name particles common in Moroccan surnames. Too short and too frequent to
# propagate on their own, they are swallowed when they directly precede a
# propagated token — otherwise "El Amrani" would come out as "El [NOM]".
# Only the capitalised form is taken, which keeps the French preposition in
# "la demande de Benali" out of the mask.
NAME_PARTICLES = ("El", "Ben", "Bel", "Ait", "Aït", "Ould", "Oulad", "Bou", "Abou", "Abd")


PROPAGATION_RULE = PIIPattern(
    pii_type=PIIType.NOM,
    description="Nom déjà identifié ailleurs dans le document (propagation)",
    regex=r"(?!x)x",  # never matched directly; spans come from propagation
    masking_strategy=MaskingStrategy.PLACEHOLDER,
    placeholder="[NOM]",
)


def _propagable_tokens(matches: list[PIIMatch], rule_set: AnonymizationRuleSet) -> set[str]:
    """Collect the name tokens worth masking elsewhere in the document."""
    tokens: set[str] = set()
    for match in matches:
        if match.pii_type != PIIType.NOM:
            continue
        for token in _NAME_TOKEN_RE.findall(match.value):
            if len(token) < MIN_PROPAGATION_TOKEN_LENGTH:
                continue
            if token.lower() in NON_PROPAGABLE_TOKENS:
                continue
            tokens.add(token)
    return tokens


def _propagated_matches(
    text: str, tokens: set[str], rule_index: int
) -> list[PIIMatch]:
    """Find every occurrence of `tokens` in `text`, as maskable spans."""
    if not tokens:
        return []

    # Judgments write the same name several ways in one document: "Benali" in
    # the motifs, "BENALI" in the header and the list of parties. Matching only
    # the detected form leaves the surname exposed exactly where it is most
    # visible. The uppercase variant is therefore added — and only it: matching
    # case-insensitively would let a surname that doubles as a common word
    # ("Fort") erase that word from the whole document.
    variants: set[str] = set()
    for token in tokens:
        variants.add(token)
        variants.add(token.upper())

    # Longest first, so "Ahmed Benali" wins over "Benali" at the same offset.
    alternation = "|".join(re.escape(t) for t in sorted(variants, key=len, reverse=True))
    particles = "|".join(NAME_PARTICLES)
    pattern = re.compile(
        rf"\b(?:(?:{particles})\s+)?(?:{alternation})\b",
        re.UNICODE,
    )
    return [
        PIIMatch(
            pii_type=PIIType.NOM,
            value=m.group(0),
            start=m.start(),
            end=m.end(),
            rule_index=rule_index,
            rule_description=PROPAGATION_RULE.description,
        )
        for m in pattern.finditer(text)
    ]


_NAME_GAP_RE = re.compile(r"^[\s'’-]{0,2}$", re.UNICODE)


def _merge_adjacent_names(matches: list[PIIMatch], text: str) -> list[PIIMatch]:
    """Fuse consecutive name spans separated only by a space or an apostrophe.

    Without this, "Ahmed Benali" — two propagated tokens — would be rendered
    as "[NOM] [NOM]", which leaks the number of words in the name and reads
    like a bug. Sorted input is assumed.
    """
    merged: list[PIIMatch] = []
    for match in matches:
        if (
            merged
            and match.pii_type == PIIType.NOM
            and merged[-1].pii_type == PIIType.NOM
            and match.start >= merged[-1].end
            and _NAME_GAP_RE.match(text[merged[-1].end : match.start])
        ):
            previous = merged[-1]
            merged[-1] = previous.model_copy(
                update={"end": match.end, "value": text[previous.start : match.end]}
            )
            continue
        merged.append(match)
    return merged


def anonymize_document(
    text: str,
    rule_set: AnonymizationRuleSet = DEFAULT_RULE_SET,
    propagate_names: bool = True,
) -> tuple[str, list[PIIMatch]]:
    """Mask `text` and return it along with the spans that were actually masked.

    Rules are applied left-to-right over non-overlapping spans found on the
    original text, so masking one match never shifts the offsets used to
    detect the next one. Overlapping detections are reported by
    :func:`detect_pii` but only the retained ones are returned here, which
    makes the second element usable as an audit trail of the masking.

    With `propagate_names`, a second pass masks every other occurrence of a
    name already identified by an anchored rule — see the note above.
    """
    matches = detect_pii(text, rule_set)

    rules = list(rule_set.rules)
    if propagate_names and matches:
        rules.append(PROPAGATION_RULE)
        matches = matches + _propagated_matches(
            text, _propagable_tokens(matches, rule_set), len(rules) - 1
        )
        # Anchored spans must win over propagated ones at equal position, so
        # that "Monsieur X" is masked whole rather than leaving the civility.
        matches.sort(key=lambda mm: (mm.start, -(mm.end - mm.start), mm.rule_index))
        matches = _merge_adjacent_names(matches, text)

    if not matches:
        return text, []

    applied: list[PIIMatch] = []
    out: list[str] = []
    cursor = 0
    last_end = -1
    for match in matches:
        if match.start < last_end:
            continue  # skip overlapping match (already covered)
        rule = rules[match.rule_index]
        out.append(text[cursor:match.start])
        out.append(_mask_value(match.value, rule))
        applied.append(match)
        cursor = match.end
        last_end = match.end
    out.append(text[cursor:])
    return "".join(out), applied


def anonymize_text(text: str, rule_set: AnonymizationRuleSet = DEFAULT_RULE_SET) -> str:
    """Mask `text` and return it. Thin wrapper over :func:`anonymize_document`."""
    return anonymize_document(text, rule_set)[0]
