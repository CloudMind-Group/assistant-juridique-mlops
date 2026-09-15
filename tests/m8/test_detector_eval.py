"""M8 — tests du banc d'évaluation du détecteur.

Le banc mesure ; ces tests garantissent qu'il mesure juste. Un scorer faux
est pire qu'aucun scorer : il donne des chiffres, et on les croit.

Un seul seuil est gardé en garde-fou : **le dommage doit rester nul.**
Le rappel, lui, est mesuré et publié sans seuil — les limites connues sont
documentées (E-01) et un seuil de rappel pousserait à masquer davantage,
c'est-à-dire exactement vers le défaut que le dommage surveille.
"""

from __future__ import annotations

import pytest

from src.m1_ingestion.anonymization_schema import anonymize_text
from src.m8_compliance.detector_eval import (
    Score,
    evaluate,
    evaluate_case,
    report,
)
from src.m8_compliance.evaluation_set import (
    EVALUATION_SET,
    EvaluationCase,
    cases_by_family,
    cases_by_language,
    known_limits,
)

# --------------------------------------------------------------------------
# Le jeu d'évaluation est-il bien formé ?
# --------------------------------------------------------------------------


def test_evaluation_set_is_not_empty():
    assert len(EVALUATION_SET) >= 30


def test_every_case_declares_something_to_check():
    for case in EVALUATION_SET:
        assert case.must_mask or case.must_survive, case.text


def test_a_case_with_an_absent_fragment_is_refused():
    """Le libellé est vérifié à la construction : une étiquette fausse doit
    échouer bruyamment, sinon elle se lit comme un échec du détecteur.
    """
    with pytest.raises(ValueError, match="absent"):
        EvaluationCase(
            text="Monsieur Ahmed Benali comparaît.",
            language="fr",
            family="nom",
            must_mask=("Karim Alaoui",),
        )


def test_both_scripts_are_covered():
    assert cases_by_language("fr")
    assert cases_by_language("ar")


def test_the_arabic_legal_vocabulary_family_exists():
    """Issue #31 : ces cas sont la mémoire du défaut, ils doivent rester."""
    assert len(cases_by_family("vocabulaire")) >= 5


def test_known_limits_are_labelled():
    limits = known_limits()
    assert limits, "les limites documentées doivent rester dans le jeu"
    for case in limits:
        assert case.must_mask, "une limite connue porte sur une détection manquée"


# --------------------------------------------------------------------------
# Le scorer compte-t-il juste ?
# --------------------------------------------------------------------------


def test_a_perfect_detector_scores_full_recall_and_no_damage():
    def parfait(text: str) -> str:
        for case in EVALUATION_SET:
            if case.text == text:
                out = text
                for fragment in case.must_mask:
                    out = out.replace(fragment, "[X]")
                return out
        return text

    _, by_language, _ = evaluate(parfait)
    for score in by_language.values():
        assert score.recall in (None, 1.0)
        assert score.damage in (None, 0.0)


def test_a_detector_that_masks_everything_is_caught_by_damage():
    """Le point de tout l'exercice : un rappel parfait obtenu en détruisant
    le texte doit apparaître comme un échec, pas comme un succès.
    """
    _, by_language, _ = evaluate(lambda text: "[MASQUE]")
    fr = by_language["fr"]
    assert fr.recall == 1.0, "tout est masqué, donc tout ce qui devait l'être l'est"
    assert fr.damage == 1.0, "et tout ce qui devait survivre a disparu"


def test_a_detector_that_does_nothing_scores_zero_recall_and_no_damage():
    _, by_language, _ = evaluate(lambda text: text)
    fr = by_language["fr"]
    assert fr.recall == 0.0
    assert fr.damage == 0.0


def test_case_result_separates_the_two_failure_modes():
    case = EvaluationCase(
        text="Le salarié Youssef Idrissi a été licencié.",
        language="fr", family="nom",
        must_mask=("Youssef Idrissi",), must_survive=("salarié",),
    )
    fuite = evaluate_case(case, lambda t: t)
    assert fuite.leaked and not fuite.damaged

    destruction = evaluate_case(case, lambda t: "[MASQUE]")
    assert destruction.damaged and not destruction.leaked


def test_score_returns_none_rather_than_zero_when_nothing_is_expected():
    """Une famille sans cas « doit survivre » n'a pas 0 % de dommage : elle
    n'en a pas. Confondre les deux ferait passer une absence de mesure pour
    un bon résultat.
    """
    vide = Score()
    assert vide.recall is None
    assert vide.damage is None


# --------------------------------------------------------------------------
# Le garde-fou
# --------------------------------------------------------------------------


def test_the_current_detector_causes_no_damage_in_any_language():
    """Seul seuil du banc : rien de ce qui doit survivre ne doit être altéré.

    Le sur-masquage est une panne silencieuse — rien n'échoue, le rapport
    de qualité affiche 100 %, et l'assistant répond avec des décisions
    amputées. C'est le seul mode de défaillance qui mérite un seuil dur.
    """
    _, by_language, _ = evaluate(anonymize_text)
    for langue, score in by_language.items():
        if score.damage is not None:
            assert score.damage == 0.0, (
                f"{langue} : {score.damage:.0%} du texte protégé a été altéré — "
                "exécuter `python -m src.m8_compliance.detector_eval --echecs`"
            )


def test_report_renders_both_figures():
    texte = report()
    assert "rappel" in texte and "dommage" in texte
    assert "Par langue" in texte and "Par famille" in texte
