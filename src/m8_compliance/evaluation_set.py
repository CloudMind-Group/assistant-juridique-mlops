"""M8 — labelled evaluation set for the PII detector.

Every case states two things, and the second is the one that is usually
forgotten: what must disappear, **and what must survive untouched**.

That asymmetry is deliberate. A detector is easy to score on recall alone,
and a detector optimised on recall alone converges on masking everything —
which destroys the corpus silently. Two real defects in this project came
from exactly that blind spot:

  - the CIN rule read ``de 150000`` as an identity number and erased every
    award and penalty from the judgments;
  - the Arabic role rule swallowed the verb that follows a name, removing
    the act the decision records.

Neither raised an error. Neither failed a test. Both were found by looking
at output, which is why this set exists as data rather than as a habit.

Cases are labelled by language so that a detector can be scored per script.
A detector strong in French and mute in Arabic would raise the global score
while widening the gap this project treats as risk R-07.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvaluationCase:
    """One text, with what the detector must and must not touch.

    Spans are given as substrings rather than offsets: offsets are unreadable
    to write by hand and rot on the first edit, and this set is meant to be
    extended by whoever adds a rule.
    """

    text: str
    language: str  # "fr" | "ar" | "mixte"
    family: str
    must_mask: tuple[str, ...] = ()
    must_survive: tuple[str, ...] = ()
    note: str = ""

    def __post_init__(self) -> None:
        if not self.must_mask and not self.must_survive:
            raise ValueError(f"case states nothing to check: {self.text[:40]!r}")
        for fragment in self.must_mask + self.must_survive:
            if fragment not in self.text:
                raise ValueError(
                    f"fragment {fragment!r} is absent from the case text — "
                    "the label is wrong, not the detector"
                )


# --------------------------------------------------------------------------
# French — names
# --------------------------------------------------------------------------

_FR_NOMS = [
    EvaluationCase(
        text="Monsieur Ahmed Benali comparaît en personne.",
        language="fr", family="nom",
        must_mask=("Ahmed Benali",),
    ),
    EvaluationCase(
        text="Maître Salma Tazi, avocate au barreau de Casablanca.",
        language="fr", family="nom",
        must_mask=("Salma Tazi",),
        must_survive=("barreau de Casablanca",),
    ),
    EvaluationCase(
        text="Le salarié Youssef Idrissi a été licencié sans procédure.",
        language="fr", family="nom",
        must_mask=("Youssef Idrissi",),
        must_survive=("salarié", "licencié"),
        note="la qualité procédurale est un fait du jugement, pas du remplissage",
    ),
    EvaluationCase(
        text="ENTRE : Karim Alaoui, demeurant à Rabat, demandeur.",
        language="fr", family="nom",
        must_mask=("Karim Alaoui",),
    ),
    EvaluationCase(
        text="Monsieur Ahmed Benali expose. Partie : BENALI Ahmed, demandeur.",
        language="fr", family="nom",
        must_mask=("BENALI",),
        note="graphie des en-têtes et des listes de parties",
    ),
    EvaluationCase(
        text="Monsieur Karim Alaoui agit. La demande d'Alaoui est recevable.",
        language="fr", family="nom",
        must_mask=("Alaoui",),
        note="propagation après une mention ancrée",
    ),
    EvaluationCase(
        text="Attendu que Ahmed Benali a saisi le tribunal compétent.",
        language="fr", family="nom",
        must_mask=("Ahmed Benali",),
        note="LIMITE CONNUE (E-01) : aucun ancrage, NER requis",
    ),
    EvaluationCase(
        text="Monsieur Pierre Fort témoigne. Un argument fort a été retenu.",
        language="fr", family="nom",
        must_mask=("Pierre Fort",),
        must_survive=("argument fort",),
        note="un patronyme homographe d'un mot courant ne doit pas l'effacer",
    ),
]

# --------------------------------------------------------------------------
# Arabic — names
# --------------------------------------------------------------------------

_AR_NOMS = [
    EvaluationCase(
        text="حيث أن السيد أحمد بنعلي تقدم بمقال افتتاحي.",
        language="ar", family="nom",
        must_mask=("أحمد بنعلي",),
        must_survive=("تقدم",),
        note="le verbe est l'acte que la décision constate",
    ),
    EvaluationCase(
        text="الشاهد: رشيد العمراني، أدلى بشهادته أمام المحكمة.",
        language="ar", family="nom",
        must_mask=("رشيد العمراني",),
        must_survive=("أدلى", "المحكمة"),
    ),
    EvaluationCase(
        text="المدعي السيد يوسف الإدريسي طرد تعسفيا.",
        language="ar", family="nom",
        must_mask=("يوسف الإدريسي",),
    ),
    EvaluationCase(
        text="حيث أن السيد أحمد بنعلي تقدم. وحيث أن بنعلي أكد ذلك أمام المحكمة.",
        language="ar", family="nom",
        must_mask=("بنعلي",),
        must_survive=("أكد", "المحكمة"),
        note="propagation en arabe",
    ),
    EvaluationCase(
        text="حيث أن أحمد بنعلي تقدم بطلب.",
        language="ar", family="nom",
        must_mask=("أحمد بنعلي",),
        note="LIMITE CONNUE (E-01) : aucun ancrage, NER requis",
    ),
    EvaluationCase(
        text="حيث أن الشاهد رشيد العمراني أدلى بشهادته.",
        language="ar", family="nom",
        must_mask=("رشيد العمراني",),
        note="LIMITE CONNUE : qualité nue, arbitrage précision de l'issue #31",
    ),
]

# --------------------------------------------------------------------------
# Arabic — legal vocabulary that must never be treated as a name anchor
# (issue #31, signalée par M1)
# --------------------------------------------------------------------------

_AR_JURIDIQUE = [
    EvaluationCase(
        text="طبقا لأحكام القانون رقم 65.99، يلتزم المشغل بضمان ظروف عمل تليق بالكرامة الإنسانية.",
        language="ar", family="vocabulaire",
        must_survive=("يلتزم المشغل بضمان ظروف عمل",),
        note="repris mot pour mot de dataset_generator.py",
    ),
    EvaluationCase(
        text="المشغل ملزم بأداء التعويضات القانونية.",
        language="ar", family="vocabulaire",
        must_survive=("ملزم بأداء التعويضات",),
    ),
    EvaluationCase(
        text="الطالب يطالب بالتعويض عن الفصل التعسفي.",
        language="ar", family="vocabulaire",
        must_survive=("يطالب بالتعويض",),
    ),
    EvaluationCase(
        text="الأجير يستحق تعويضا عن الإخطار.",
        language="ar", family="vocabulaire",
        must_survive=("يستحق تعويضا",),
    ),
    EvaluationCase(
        text="المدعي يطلب من المحكمة الحكم له.",
        language="ar", family="vocabulaire",
        must_survive=("يطلب من المحكمة",),
    ),
]

# --------------------------------------------------------------------------
# CIN — spellings, and the references that share its shape
# --------------------------------------------------------------------------

_CIN = [
    EvaluationCase(
        text="Le requérant, titulaire de la CIN AB123456, demeurant à Rabat.",
        language="fr", family="cin", must_mask=("AB123456",)),
    EvaluationCase(
        text="Pièce jointe : AB-123456 au dossier.",
        language="fr", family="cin", must_mask=("AB-123456",)),
    EvaluationCase(
        text="Titulaire de la CIN n AB 123456, domicilié à Rabat.",
        language="fr", family="cin", must_mask=("AB 123456",),
        note="le signe degré disparaît en sortie d'OCR"),
    EvaluationCase(
        text="Porteur de la CNIE AB123456.",
        language="fr", family="cin", must_mask=("AB123456",),
        note="CNIE est l'appellation officielle actuelle"),
    EvaluationCase(
        text="الحامل للبطاقة الوطنية AB123456 المقيم بالرباط.",
        language="ar", family="cin", must_mask=("AB123456",)),
    EvaluationCase(
        text="Pièce jointe : ab123456 au dossier.",
        language="fr", family="cin", must_mask=("ab123456",),
        note="LIMITE CONNUE : minuscules écartées pour protéger « de 150000 »"),
]

_CIN_SOSIES = [
    EvaluationCase(
        text="La somme de 150000 dirhams à titre de dommages-intérêts.",
        language="fr", family="reference",
        must_survive=("de 150000 dirhams",),
        note="le défaut historique : les montants effacés de tous les jugements"),
    EvaluationCase(
        text="Registre de commerce RC123456 au tribunal de Casablanca.",
        language="fr", family="reference", must_survive=("RC123456",)),
    EvaluationCase(
        text="Registre RC-123456 déposé ce jour.",
        language="fr", family="reference", must_survive=("RC-123456",)),
    EvaluationCase(
        text="Bulletin Officiel BO 12345 du 3 janvier.",
        language="fr", family="reference", must_survive=("BO 12345",)),
    EvaluationCase(
        text="Référence RG 98765/2023 au rôle général.",
        language="fr", family="reference", must_survive=("RG 98765",)),
    EvaluationCase(
        text="Dossier n 123456 - Cour de Cassation.",
        language="fr", family="reference",
        must_survive=("Dossier n 123456", "Cour de Cassation")),
    EvaluationCase(
        text="Conformément à l'article 62 du Code du Travail et au dahir n 1-58-250.",
        language="fr", family="reference",
        must_survive=("article 62 du Code du Travail", "dahir n 1-58-250")),
    EvaluationCase(
        text="Monsieur Hassan Rabat témoigne. Le tribunal de Rabat a statué.",
        language="fr", family="reference",
        must_mask=("Hassan Rabat",), must_survive=("tribunal de Rabat",),
        note="un patronyme homographe d'une ville ne doit pas l'effacer"),
]

# --------------------------------------------------------------------------
# Other categories
# --------------------------------------------------------------------------

_AUTRES = [
    EvaluationCase(
        text="Joignable au 0612345678 en journée.",
        language="fr", family="telephone", must_mask=("0612345678",)),
    EvaluationCase(
        text="Joignable au +212 6 12 34 56 78 en journée.",
        language="fr", family="telephone", must_mask=("6 12 34 56 78",),
        note="graphie espacée, courante dans les actes"),
    EvaluationCase(
        text="Contact : a.benali@cabinet.ma pour toute notification.",
        language="fr", family="email", must_mask=("a.benali@cabinet.ma",)),
    EvaluationCase(
        text="Écrire à(a.benali@cabinet.ma)avant lundi.",
        language="fr", family="email", must_mask=("a.benali@cabinet.ma",)),
    EvaluationCase(
        text="Demeurant Rue Al Massira à Rabat, il conteste la décision.",
        language="fr", family="adresse", must_mask=("Rue Al Massira",)),
]

# --------------------------------------------------------------------------
# Mixed-script document
# --------------------------------------------------------------------------

_MIXTE = [
    EvaluationCase(
        text="السيد أحمد بنعلي. Le salarié Ahmed Benali conteste. بنعلي أكد.",
        language="mixte", family="nom",
        must_mask=("بنعلي", "Ahmed Benali"),
        must_survive=("salarié", "أكد"),
        note="la propagation doit opérer dans les deux écritures",
    ),
]


EVALUATION_SET: tuple[EvaluationCase, ...] = tuple(
    _FR_NOMS + _AR_NOMS + _AR_JURIDIQUE + _CIN + _CIN_SOSIES + _AUTRES + _MIXTE
)


def cases_by_language(language: str) -> tuple[EvaluationCase, ...]:
    return tuple(c for c in EVALUATION_SET if c.language == language)


def cases_by_family(family: str) -> tuple[EvaluationCase, ...]:
    return tuple(c for c in EVALUATION_SET if c.family == family)


def known_limits() -> tuple[EvaluationCase, ...]:
    """Cases the current detector is documented as failing.

    They stay in the set on purpose. A limit that is measured every run is a
    limit that gets noticed the day it disappears — or the day it widens.
    """
    return tuple(c for c in EVALUATION_SET if "LIMITE CONNUE" in c.note)
