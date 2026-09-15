"""M8 — scorer for any PII detector, per language and per family.

The AIPD requires that a replacement detector (action A-1, NER) be evaluated
**separately on each language**, because a detector strong in French and mute
in Arabic would raise the overall figure while widening risk R-07. That
requirement was written in four places and measurable in none. This module
makes it executable.

Two figures are produced, and both matter:

  - **rappel** — what fraction of the personal data that should disappear
    actually disappeared;
  - **dommage** — what fraction of the text that must survive was altered.

Reporting recall alone is how a detector gets optimised into masking
everything. A detector that masks the entire document scores 100 % recall
and destroys the corpus, which is why `dommage` is printed beside it and
never folded into a single score.

Usage:
    python -m src.m8_compliance.detector_eval
    python -m src.m8_compliance.detector_eval --langue ar
    python -m src.m8_compliance.detector_eval --echecs
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable

from src.m1_ingestion.anonymization_schema import anonymize_text
from src.m8_compliance.evaluation_set import EVALUATION_SET, EvaluationCase

Detector = Callable[[str], str]


@dataclass
class CaseResult:
    case: EvaluationCase
    output: str
    leaked: tuple[str, ...]      # devait être masqué, ne l'a pas été
    damaged: tuple[str, ...]     # devait survivre, a été altéré

    @property
    def ok(self) -> bool:
        return not self.leaked and not self.damaged


@dataclass
class Score:
    """Counts kept separate on purpose — a single number would hide the
    trade-off between the two failure modes."""

    expected_masked: int = 0
    actually_masked: int = 0
    expected_intact: int = 0
    actually_intact: int = 0
    cases: int = 0
    cases_ok: int = 0

    @property
    def recall(self) -> float | None:
        if not self.expected_masked:
            return None
        return self.actually_masked / self.expected_masked

    @property
    def damage(self) -> float | None:
        """Fraction of protected text that was altered. Lower is better."""
        if not self.expected_intact:
            return None
        return 1 - (self.actually_intact / self.expected_intact)


def evaluate_case(case: EvaluationCase, detector: Detector) -> CaseResult:
    output = detector(case.text)
    leaked = tuple(f for f in case.must_mask if f in output)
    damaged = tuple(f for f in case.must_survive if f not in output)
    return CaseResult(case=case, output=output, leaked=leaked, damaged=damaged)


def evaluate(
    detector: Detector = anonymize_text,
    cases: Iterable[EvaluationCase] = EVALUATION_SET,
) -> tuple[list[CaseResult], dict[str, Score], dict[str, Score]]:
    """Return the per-case results plus scores by language and by family."""
    results: list[CaseResult] = []
    by_language: dict[str, Score] = defaultdict(Score)
    by_family: dict[str, Score] = defaultdict(Score)

    for case in cases:
        result = evaluate_case(case, detector)
        results.append(result)
        for bucket in (by_language[case.language], by_family[case.family]):
            bucket.cases += 1
            bucket.cases_ok += int(result.ok)
            bucket.expected_masked += len(case.must_mask)
            bucket.actually_masked += len(case.must_mask) - len(result.leaked)
            bucket.expected_intact += len(case.must_survive)
            bucket.actually_intact += len(case.must_survive) - len(result.damaged)

    return results, dict(by_language), dict(by_family)


def _pct(value: float | None) -> str:
    return "  n/a" if value is None else f"{value * 100:5.1f}%"


def _table(title: str, scores: dict[str, Score]) -> list[str]:
    lines = [title, f"  {'':12} {'cas':>7}  {'rappel':>7}  {'dommage':>8}"]
    for key in sorted(scores):
        s = scores[key]
        lines.append(
            f"  {key:12} {s.cases_ok:>3}/{s.cases:<3}  {_pct(s.recall)}  {_pct(s.damage)}"
        )
    return lines


def report(
    detector: Detector = anonymize_text,
    cases: Iterable[EvaluationCase] = EVALUATION_SET,
    show_failures: bool = False,
) -> str:
    results, by_language, by_family = evaluate(detector, cases)
    total = Score()
    for s in by_language.values():
        total.cases += s.cases
        total.cases_ok += s.cases_ok
        total.expected_masked += s.expected_masked
        total.actually_masked += s.actually_masked
        total.expected_intact += s.expected_intact
        total.actually_intact += s.actually_intact

    lines: list[str] = []
    lines += _table("Par langue", by_language) + [""]
    lines += _table("Par famille", by_family) + [""]
    lines.append(
        f"  {'ENSEMBLE':12} {total.cases_ok:>3}/{total.cases:<3}  "
        f"{_pct(total.recall)}  {_pct(total.damage)}"
    )

    if show_failures:
        echecs = [r for r in results if not r.ok]
        lines += ["", f"{len(echecs)} cas en échec", ""]
        for r in echecs:
            connu = "  [limite documentée]" if "LIMITE CONNUE" in r.case.note else ""
            lines.append(f"  [{r.case.language}/{r.case.family}]{connu}")
            lines.append(f"    entrée : {r.case.text}")
            lines.append(f"    sortie : {r.output}")
            if r.leaked:
                lines.append(f"    a fuité : {', '.join(repr(f) for f in r.leaked)}")
            if r.damaged:
                lines.append(f"    détruit : {', '.join(repr(f) for f in r.damaged)}")
            if r.case.note:
                lines.append(f"    note    : {r.case.note}")
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Évalue un détecteur PII par langue et par famille"
    )
    parser.add_argument("--langue", help="n'évaluer qu'une langue : fr, ar, mixte")
    parser.add_argument("--famille", help="n'évaluer qu'une famille de cas")
    parser.add_argument(
        "--echecs", action="store_true", help="détailler chaque cas en échec"
    )
    args = parser.parse_args()

    cases = EVALUATION_SET
    if args.langue:
        cases = tuple(c for c in cases if c.language == args.langue)
    if args.famille:
        cases = tuple(c for c in cases if c.family == args.famille)
    if not cases:
        print("aucun cas ne correspond au filtre")
        return 1

    print(report(cases=cases, show_failures=args.echecs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
