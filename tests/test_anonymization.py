"""M8 — regression tests for PII removal in the M1 ingestion pipeline.

Two things are guarded here:

1. Personal data never reaches ``data/processed/``. The pipeline is the only
   place where removal is still a cheap text edit; once M2 has embedded a
   document, removing an individual means rebuilding the index.
2. Legal references survive. A masking rule that eats article, docket or
   registry numbers would corrupt the citations the assistant is built to
   produce — a silent failure that is worse than no masking at all.

Run: ``python -m pytest tests/ -v``
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

from src.m1_ingestion.anonymization_schema import (
    DEFAULT_RULE_SET,
    PIIType,
    anonymize_document,
    anonymize_text,
    detect_pii,
)
from src.m1_ingestion.ingest import IngestionPipeline, build_metadata, make_doc_id

# --------------------------------------------------------------------------
# Rule precision: what must be masked
# --------------------------------------------------------------------------

MUST_MASK = [
    ("Le requérant, titulaire de la CIN AB123456, demeurant à Rabat", "AB123456"),
    ("Monsieur Ahmed Benali, CIN A 123456", "A 123456"),
    ("porteur de la carte nationale n° AB12345", "AB12345"),
    ("Monsieur Ahmed Benali comparaît en personne", "Ahmed Benali"),
    ("Maître Salma Tazi, avocate au barreau", "Salma Tazi"),
    ("Le salarié Youssef Idrissi a été licencié", "Youssef Idrissi"),
    ("Témoin : Rachid El Amrani, âgé de 42 ans", "Rachid El Amrani"),
    ("ENTRE : Karim Alaoui, demeurant à Rabat", "Karim Alaoui"),
    ("Contact : a.benali@cabinet.ma pour toute notification", "a.benali@cabinet.ma"),
    ("joignable au 0612345678 selon le dossier", "0612345678"),
]


def test_personal_data_is_removed():
    for text, secret in MUST_MASK:
        assert secret not in anonymize_text(text), (
            f"{secret!r} survived anonymisation in {text!r}"
        )


# --------------------------------------------------------------------------
# Rule precision: what must survive
# --------------------------------------------------------------------------

MUST_SURVIVE = [
    # Amounts: "de 150000" used to be read as a CIN, which silently deleted
    # every award and penalty from the judgments.
    "La somme de 150000 dirhams à titre de dommages-intérêts",
    "Dossier n° 123456 - Cour de Cassation",
    "Registre de commerce RC123456",
    "Bulletin Officiel BO 12345 du 3 janvier",
    "Référence RG 98765/2023",
    "Article 24 du Code du Travail",
    "Vu le dahir n° 1-58-250 du 6 septembre 1958",
    "Conformément à la loi n° 65-99 relative au Code du Travail",
    # Institutions are not personal data and are required for citation.
    "Cour d'Appel de Casablanca",
    "Tribunal de Première Instance de Fès",
]


def test_legal_references_survive():
    for text in MUST_SURVIVE:
        assert anonymize_text(text) == text, (
            f"anonymisation altered a legal reference: {text!r} -> "
            f"{anonymize_text(text)!r}"
        )


def test_masking_preserves_procedural_role():
    """The role carries the legal meaning and must outlive the name."""
    masked = anonymize_text("Le salarié Youssef Idrissi a été licencié")
    assert "salarié" in masked
    assert "licencié" in masked
    assert "[NOM]" in masked


def test_arabic_names_are_masked():
    """Three anchors work in Arabic: a title, a role plus a colon, a role
    plus a title. All three are signals; a role alone is not — see the test
    of the known limit below.
    """
    for text, name in [
        ("حيث أن السيد أحمد بنعلي تقدم بطلب.", "أحمد بنعلي"),
        ("الشاهد: رشيد العمراني، أدلى بشهادته.", "رشيد العمراني"),
        ("المدعي السيد يوسف الإدريسي طرد تعسفيا.", "يوسف الإدريسي"),
    ]:
        assert name not in anonymize_text(text), f"{name!r} survived in {text!r}"


# Issue #31, reported by @DOUAEM449: a procedural role followed by Arabic words
# was treated as introducing a name, so the words after it were masked. The
# first case below is taken verbatim from dataset_generator.py — the defect hit
# the corpus actually in the repository.
ARABIC_LEGAL_TERMS_MUST_SURVIVE = [
    "طبقا لأحكام القانون رقم 65.99، يلتزم المشغل بضمان ظروف عمل تليق بالكرامة الإنسانية.",
    "المشغل ملزم بأداء التعويضات القانونية.",
    "الطالب يطالب بالتعويض عن الفصل التعسفي.",
    "الأجير يستحق تعويضا عن الإخطار.",
    "المدعي يطلب من المحكمة الحكم له.",
    "حيث إن المشغل لم يحترم مسطرة الفصل.",
]


def test_arabic_procedural_terms_are_not_treated_as_name_anchors():
    """A role word used generically must not mask the sentence after it."""
    for text in ARABIC_LEGAL_TERMS_MUST_SURVIVE:
        assert anonymize_text(text) == text, f"altered: {text!r}"


def test_known_limit_arabic_bare_role_no_longer_anchors():
    """The cost of fixing issue #31, stated rather than hidden.

    "الشاهد رشيد العمراني" — a role followed directly by a name, without a
    colon or a title — is no longer detected by that rule. Arabic has no
    capitalisation, so this form is indistinguishable from "المشغل ملزم":
    every positional variant tried caught all test names *and* destroyed all
    test sentences, with nothing in between.

    Propagation still covers the realistic document, where the same person is
    introduced once with a title. What is lost is the name that appears only
    ever after a bare role. Closing that needs NER — action A-1.
    """
    text = "حيث أن الشاهد رشيد العمراني أدلى بشهادته"
    assert "رشيد العمراني" in anonymize_text(text)


def test_propagation_recovers_the_bare_role_case_in_a_real_document():
    """The loss above is bounded: one titled mention re-covers the rest."""
    masked = anonymize_text(
        "حيث أن السيد رشيد العمراني حضر. وحيث أن الشاهد رشيد العمراني أدلى بشهادته."
    )
    assert "رشيد العمراني" not in masked
    assert "أدلى" in masked


def test_detect_reports_positions_that_match_the_text():
    text = "Le salarié Youssef Idrissi a été licencié"
    for match in detect_pii(text):
        assert text[match.start : match.end] == match.value


def test_report_lists_only_applied_masks():
    text = "Le requérant, titulaire de la CIN AB123456, demeurant à Rabat"
    masked, applied = anonymize_document(text)
    assert masked != text
    assert applied, "expected at least one applied mask"
    assert all(m.pii_type == PIIType.CIN for m in applied)


def test_ruleset_regexes_all_compile():
    for rule in DEFAULT_RULE_SET.rules:
        rule.compiled()


# --------------------------------------------------------------------------
# Metadata must not carry personal data either
# --------------------------------------------------------------------------


@contextlib.contextmanager
def _sandbox():
    """Run inside a throwaway cwd.

    DocumentMetadata rejects absolute file_path values, so the pipeline is
    always driven with paths relative to the working directory — as the CLI
    and the Airflow DAG do. The tests mirror that.
    """
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            yield Path(tmp)
        finally:
            os.chdir(previous)


def test_doc_id_does_not_leak_the_file_name():
    """A file named after a party must not put that name in the identifier."""
    with _sandbox():
        raw_dir = Path("raw")
        source = raw_dir / "jurisprudence" / "arret_ahmed_benali_2024.txt"
        source.parent.mkdir(parents=True)
        source.write_text("contenu", encoding="utf-8")

        doc_id = make_doc_id(source, raw_dir)

        assert "ahmed" not in doc_id.lower()
        assert "benali" not in doc_id.lower()
        assert doc_id.startswith("jurisprudence-")


def test_title_falls_back_to_source_not_file_name():
    with _sandbox():
        raw_dir = Path("raw")
        source = raw_dir / "jurisprudence" / "arret_ahmed_benali_2024.txt"
        source.parent.mkdir(parents=True)
        source.write_text("contenu", encoding="utf-8")

        meta = build_metadata(source, raw_dir, Path("out"), "contenu du jugement")

        assert "Benali" not in meta.title
        assert "Jurisprudence" in meta.title


# --------------------------------------------------------------------------
# End to end: the pipeline itself
# --------------------------------------------------------------------------

JUDGMENT = (
    "Attendu que Monsieur Ahmed Benali, titulaire de la CIN AB123456, "
    "demeurant à Rabat, joignable au 0612345678, a saisi la Cour d'Appel "
    "de Casablanca ; Attendu que les pièces établissent l'absence de "
    "procédure disciplinaire régulière ; Par ces motifs, la Cour déclare "
    "le licenciement abusif et condamne l'employeur au versement de "
    "150000 dirhams au titre de l'article 41 du Code du Travail."
)

SECRETS = ["Ahmed Benali", "AB123456", "0612345678"]
KEEP = ["Cour d'Appel", "150000", "article 41", "licenciement abusif"]


def _run_pipeline(*, anonymise: bool) -> tuple[Path, str]:
    raw_dir = Path("raw")
    out_dir = Path("processed")
    doc = raw_dir / "jurisprudence" / "arret_ahmed_benali_2024.txt"
    doc.parent.mkdir(parents=True)
    doc.write_text(JUDGMENT, encoding="utf-8")
    doc.with_suffix(".txt.meta.json").write_text(
        json.dumps({"date": "2024-03-12", "category": "Droit du travail"}),
        encoding="utf-8",
    )

    IngestionPipeline(raw_dir, out_dir, anonymise=anonymise).run()
    written = list((out_dir / "documents").glob("*.txt"))
    assert len(written) == 1, f"expected one processed document, got {written}"
    return out_dir, written[0].read_text(encoding="utf-8")


def test_pipeline_writes_no_personal_data():
    with _sandbox():
        _, content = _run_pipeline(anonymise=True)
        for secret in SECRETS:
            assert secret not in content, f"{secret!r} reached data/processed"


def test_pipeline_preserves_the_legal_content():
    with _sandbox():
        _, content = _run_pipeline(anonymise=True)
        for kept in KEEP:
            assert kept in content, f"{kept!r} was lost during anonymisation"


def test_metadata_index_carries_no_personal_data():
    with _sandbox():
        out_dir, _ = _run_pipeline(anonymise=True)
        index = (out_dir / "metadata.jsonl").read_text(encoding="utf-8")
        for secret in SECRETS + ["benali"]:
            assert secret.lower() not in index.lower(), (
                f"{secret!r} reached the metadata index"
            )


def test_opt_out_is_honoured_and_is_the_only_way_to_keep_pii():
    """Guards the default: PII survives only when explicitly asked for."""
    with _sandbox():
        _, content = _run_pipeline(anonymise=False)
        assert "Ahmed Benali" in content


# --------------------------------------------------------------------------
# Name propagation
#
# A party is introduced once with a civility or a role, then referred to bare
# for the rest of the decision. The anchored rules catch the introduction;
# propagation has to catch the repetitions, which is where most of the
# residual exposure lives.
# --------------------------------------------------------------------------

JUDGMENT_WITH_REPEATS = (
    "ROYAUME DU MAROC - Cour d'Appel de Casablanca - Chambre sociale\n"
    "Dossier n 45782/2024\n\n"
    "ENTRE : Karim Alaoui, demeurant a Rabat, demandeur\n"
    "ET : la societe Atlas Distribution, defenderesse\n\n"
    "Attendu que Monsieur Karim Alaoui a ete engage le 3 mars 2019 ;\n"
    "Attendu qu'Alaoui a ete licencie le 12 janvier 2024 sans procedure ;\n"
    "Attendu que le temoin Rachid El Amrani declare avoir assiste ;\n"
    "Attendu qu'El Amrani precise qu'aucun avertissement n'a ete remis ;\n"
    "Attendu que Karim Alaoui reclame des dommages-interets ;\n"
    "Par ces motifs, la Cour condamne la societe a verser a Alaoui la somme\n"
    "de 150000 dirhams, conformement a l'article 62 du Code du Travail."
)


def test_repeated_bare_names_are_masked():
    masked = anonymize_text(JUDGMENT_WITH_REPEATS)
    for name in ("Alaoui", "Karim", "Amrani", "Rachid"):
        assert name not in masked, f"{name!r} survived propagation"


def test_propagation_is_what_makes_the_difference():
    """Without it, the repetitions go through — this is the gap it closes."""
    unpropagated, _ = anonymize_document(
        JUDGMENT_WITH_REPEATS, propagate_names=False
    )
    assert "Alaoui" in unpropagated
    propagated, _ = anonymize_document(JUDGMENT_WITH_REPEATS, propagate_names=True)
    assert "Alaoui" not in propagated


def test_propagation_does_not_touch_the_legal_content():
    """The whole point of masking more is to not start masking wrongly."""
    masked = anonymize_text(JUDGMENT_WITH_REPEATS)
    for kept in (
        "Cour d'Appel de Casablanca",
        "Dossier n 45782",
        "150000 dirhams",
        "article 62 du Code du Travail",
        "Chambre sociale",
    ):
        assert kept in masked, f"{kept!r} was destroyed by propagation"


def test_company_name_is_not_propagated():
    """A legal person is not personal data and must stay citable."""
    assert "Atlas Distribution" in anonymize_text(JUDGMENT_WITH_REPEATS)


def test_name_particle_is_swallowed_not_left_dangling():
    """'El Amrani' must not come out as 'El [NOM]'."""
    masked = anonymize_text(JUDGMENT_WITH_REPEATS)
    assert "El [NOM]" not in masked
    assert "El Amrani" not in masked


def test_multiword_name_yields_a_single_placeholder():
    """'[NOM] [NOM]' would leak how many words the name had."""
    assert "[NOM] [NOM]" not in anonymize_text(JUDGMENT_WITH_REPEATS)


def test_institution_words_are_never_propagated():
    """A name span containing a common noun must not mask it document-wide."""
    text = (
        "Attendu que Monsieur Karim Alaoui a saisi le Tribunal de Premiere "
        "Instance ; Attendu que le Tribunal a statue ; la Cour confirme."
    )
    masked = anonymize_text(text)
    assert masked.count("Tribunal") == 2
    assert "Cour" in masked


def test_known_limit_a_name_never_anchored_is_still_missed():
    """Propagation seeds on anchored detections — no anchor, no seed.

    Documented as a limitation in docs/RGPD.md and docs/AIPD.md (E-01), and
    asserted here so that the day it changes, this test says so.
    """
    text = "Attendu que Youssef Idrissi a saisi la juridiction competente."
    assert "Youssef Idrissi" in anonymize_text(text)


def test_uppercase_variant_of_a_known_name_is_masked():
    """Judgments write the surname in caps in headers and party lists.

    Matching only the detected casing left it exposed where it is most
    visible — while the given name, matching exactly, disappeared.
    """
    masked = anonymize_text(
        "Monsieur Ahmed Benali expose. Partie : BENALI Ahmed, demandeur."
    )
    assert "BENALI" not in masked
    assert "Benali" not in masked


def test_a_surname_that_is_also_a_common_word_stays_case_sensitive():
    """Guards the restriction: only the capitalised forms propagate.

    Full case-insensitive matching would erase the adjective in
    "un argument fort" once someone named Fort appears in the document.
    """
    masked = anonymize_text("Monsieur Pierre Fort temoigne. Un argument fort.")
    assert "Pierre Fort" not in masked
    assert "argument fort" in masked


# --------------------------------------------------------------------------
# Arabic
#
# The rules below used to have no "must survive" counterpart at all, and that
# is precisely how the over-masking went unnoticed: the name disappeared, the
# test passed, and the verb disappeared with it.
# --------------------------------------------------------------------------

ARABIC_MUST_SURVIVE = [
    ("حيث أن السيد أحمد بنعلي تقدم بمقال افتتاحي.", "تقدم"),
    ("حيث أن السيد أحمد بنعلي حضر الجلسة.", "حضر"),
    ("حيث أن الشاهد رشيد العمراني أدلى بشهادته أمام المحكمة.", "أدلى"),
    ("وحيث أن السيدة فاطمة بناني رفضت التوقيع.", "رفضت"),
]


def test_arabic_masking_does_not_eat_the_verb():
    """The verb is the operative act of the judgment, not filler."""
    for text, verb in ARABIC_MUST_SURVIVE:
        masked = anonymize_text(text)
        assert verb in masked, f"{verb!r} was destroyed in {text!r} -> {masked!r}"


def test_arabic_institution_survives():
    masked = anonymize_text("حيث أن الشاهد رشيد العمراني أدلى أمام المحكمة.")
    assert "المحكمة" in masked


def test_arabic_names_propagate():
    """Without an Arabic token pattern this masked only the first mention."""
    masked = anonymize_text(
        "حيث أن السيد أحمد بنعلي تقدم. وحيث أن بنعلي أكد ذلك أمام المحكمة."
    )
    assert "بنعلي" not in masked
    assert "أكد" in masked and "المحكمة" in masked


def test_mixed_document_propagates_in_both_scripts():
    masked = anonymize_text(
        "السيد أحمد بنعلي. Le salarie Ahmed Benali conteste. بنعلي أكد."
    )
    assert "بنعلي" not in masked
    assert "Benali" not in masked


# --------------------------------------------------------------------------
# CIN spellings
# --------------------------------------------------------------------------

CIN_MUST_MASK = [
    ("Le requerant porte la CIN AB123456.", "AB123456"),
    ("Piece jointe : AB-123456 au dossier.", "AB-123456"),
    ("Titulaire de la CIN n AB 123456, domicilie a Rabat.", "AB 123456"),
    ("Porteur de la CNIE AB123456.", "AB123456"),
    ("الحامل للبطاقة الوطنية AB123456 المقيم بالرباط.", "AB123456"),
]


def test_cin_spellings_are_masked():
    for text, secret in CIN_MUST_MASK:
        assert secret not in anonymize_text(text), f"{secret!r} survived in {text!r}"


CIN_LOOKALIKES_MUST_SURVIVE = [
    "La somme de 150000 dirhams",
    "Registre de commerce RC123456",
    "Registre RC-123456",
    "Bulletin Officiel BO 12345",
    "Reference RG 98765/2023",
    "Dossier n 123456",
]


def test_cin_lookalikes_survive():
    """The hyphen added for CIN must not reopen the reference false positive."""
    for text in CIN_LOOKALIKES_MUST_SURVIVE:
        assert anonymize_text(text) == text, f"altered: {text!r}"
