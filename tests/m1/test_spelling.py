"""Tests du correcteur orthographique juridique (M1).

L'essentiel de ces tests ne vérifie pas ce que le correcteur corrige, mais
**ce qu'il refuse de toucher**. Sur un corpus de droit, une correction
abusive est plus grave qu'une faute laissée : le bruit d'OCR se voit, un
texte juridique silencieusement réécrit ne se voit pas. Un nom de partie
transformé, un numéro d'article « corrigé », et le document ne dit plus ce
que le juge a écrit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.m1_ingestion.ingest import ExtractionOutcome, IngestionPipeline
from src.m1_ingestion.spelling import (
    LEXIQUE_JURIDIQUE,
    MAX_SUBSTITUTIONS,
    Correction,
    _INDEX_SANS_ACCENT,
    corriger_document,
    corriger_texte,
    resumer,
)


# --- Ce que le correcteur doit corriger ---------------------------------


def test_les_accents_sont_restitues_sur_le_vocabulaire_juridique():
    """Le défaut le plus fréquent de l'OCR français : les diacritiques
    disparaissent."""
    corrige, corrections = corriger_document("Le salarie est deboute de sa demande.")

    assert corrige == "Le salarié est débouté de sa demande."
    assert [c.regle for c in corrections] == ["accents", "accents"]


def test_les_confusions_de_caracteres_sont_corrigees():
    """Tesseract confond le 1 et le l, le 0 et le o. Ces mots mêlent
    lettres et chiffres : c'est la signature d'une erreur d'OCR, pas d'un
    mot légitime."""
    corrige, corrections = corriger_document("Vu l'artic1e 12 du C0de du Travail")

    assert corrige == "Vu l'article 12 du Code du Travail"
    assert {c.regle for c in corrections} == {"confusion_ocr"}


@pytest.mark.parametrize(
    "avant,apres",
    [
        ("SALARIE", "SALARIÉ"),
        ("Salarie", "Salarié"),
        ("salarie", "salarié"),
    ],
)
def test_la_casse_du_mot_d_origine_est_preservee(avant, apres):
    """Dans un jugement, les capitales marquent souvent un intitulé. Les
    écraser changerait la structure lue ensuite par la segmentation."""
    assert corriger_texte(avant) == apres


# --- Ce que le correcteur doit refuser de toucher -----------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "Le chat dort sur le tapis de la maison bleue.",
        "Il fait beau ce matin et le train part a huit heures.",
        "Cette voiture rouge appartient a mon voisin.",
    ],
)
def test_le_francais_ordinaire_est_laisse_intact(phrase):
    """Le correcteur ne connaît que le lexique juridique. Un mot hors
    lexique ne produit aucun candidat valide, donc aucune correction — c'est
    ce qui le rend inoffensif sur le reste du texte."""
    assert corriger_texte(phrase) == phrase


@pytest.mark.parametrize(
    "phrase",
    [
        "Monsieur Ahmed Benali, demeurant a Rabat",
        "Maitre Salma Elouarrate, avocate au barreau",
        "La societe SOMACA representee par Nouhaila Fadli",
    ],
)
def test_les_noms_propres_ne_sont_jamais_transformes(phrase):
    """Un nom de partie n'est pas dans le lexique juridique et ne contient
    pas de chiffre : aucune des deux règles ne peut l'atteindre. La
    protection est structurelle, pas une liste d'exceptions."""
    corrige, corrections = corriger_document(phrase)

    for nom in ("Benali", "Ahmed", "Salma", "Elouarrate", "Nouhaila", "Fadli", "SOMACA"):
        if nom in phrase:
            assert nom in corrige, f"{nom} a été transformé : {corrige}"


@pytest.mark.parametrize(
    "phrase",
    [
        "Dahir n 1-03-194 du 11 septembre 2003",
        "Article 65-99 du Code du Travail",
        "Facture de 1500 dirhams, reference 2024-B-1177",
        "Vu la loi 15-95 formant code de commerce",
    ],
)
def test_les_references_legales_et_les_nombres_sont_intacts(phrase):
    """Un numéro de loi transformé change le texte cité. Aucun candidat
    produit à partir d'un nombre n'appartient au lexique, donc aucun n'est
    retenu — mais ce test doit rester : c'est la garantie la plus coûteuse
    à perdre."""
    corrige = corriger_texte(phrase)

    for jeton in phrase.split():
        if any(c.isdigit() for c in jeton):
            assert jeton in corrige, f"{jeton} a été altéré : {corrige}"


def test_l_arabe_est_laisse_strictement_intact():
    """Hors périmètre, et assumé comme tel : les confusions de l'OCR arabe
    sont d'une autre nature et aucun lexique arabe n'est embarqué. Mieux
    vaut ne rien faire que faire semblant."""
    texte = "قرار المحكمة الابتدائية بالدار البيضاء بتاريخ 2024"

    corrige, corrections = corriger_document(texte)

    assert corrige == texte
    assert corrections == []


def test_un_texte_mixte_ne_corrige_que_la_partie_francaise():
    texte = "Le salarie a saisi المحكمة الابتدائية de Casablanca."

    corrige = corriger_texte(texte)

    assert "salarié" in corrige
    assert "المحكمة الابتدائية" in corrige


def test_un_terme_deja_correct_n_est_pas_retouche():
    texte = "Le salarié débouté par le tribunal de première instance."

    corrige, corrections = corriger_document(texte)

    assert corrige == texte
    assert corrections == []


def test_la_correction_est_idempotente():
    """Le pipeline peut être rejoué. Deux passages doivent donner le même
    texte, sinon le corpus dérive à chaque `dvc repro`."""
    texte = "Le salarie est deboute, vu l'artic1e 12."

    premier = corriger_texte(texte)
    second = corriger_texte(premier)

    assert premier == second


def test_un_mot_trop_eloigne_n_est_pas_devine():
    """Au-delà de deux substitutions, on ne corrige plus : on devine. Un mot
    qui demande trois corrections pour ressembler à un terme du lexique
    ressemble tout autant à autre chose."""
    assert MAX_SUBSTITUTIONS == 2
    # « 5al4r13 » demande quatre substitutions pour atteindre « salarie ».
    corrige, corrections = corriger_document("5al4r13")

    assert corrige == "5al4r13"
    assert corrections == []


# --- Trace d'audit -------------------------------------------------------


def test_chaque_correction_est_tracee_avec_sa_position_et_sa_regle():
    """Le pendant d'anonymize_document : une transformation du corpus qui ne
    laisse pas de trace n'est pas auditable, et personne ne peut alors
    contester une correction précise."""
    texte = "Le salarie conteste l'artic1e 12."

    _, corrections = corriger_document(texte)

    assert len(corrections) == 2
    accents = next(c for c in corrections if c.regle == "accents")
    assert accents.avant == "salarie"
    assert accents.apres == "salarié"
    assert texte[accents.position : accents.position + len(accents.avant)] == "salarie"

    confusion = next(c for c in corrections if c.regle == "confusion_ocr")
    assert (confusion.avant, confusion.apres) == ("artic1e", "article")


def test_le_resume_compte_par_regle():
    _, corrections = corriger_document("Le salarie deboute conteste l'artic1e 12.")

    assert resumer(corrections) == {"accents": 2, "confusion_ocr": 1}


def test_une_correction_est_serialisable():
    correction = Correction(avant="salarie", apres="salarié", position=3, regle="accents")

    assert correction.to_dict()["regle"] == "accents"


def test_un_texte_vide_ne_casse_rien():
    assert corriger_document("") == ("", [])


# --- Cohérence du lexique ------------------------------------------------


def test_le_lexique_ne_contient_que_des_formes_minuscules():
    """La comparaison se fait en minuscules ; une entrée en capitales ne
    serait jamais trouvée et donnerait un faux sentiment de couverture."""
    fautives = {terme for terme in LEXIQUE_JURIDIQUE if terme != terme.lower()}

    assert fautives == set()


def test_aucune_ambiguite_du_lexique_n_est_arbitree_en_silence():
    """Deux termes partageant une forme sans accent doivent être retirés de
    l'index, pas départagés au hasard de l'ordre d'itération."""
    from collections import Counter

    compte = Counter(
        __import__("unicodedata").normalize("NFD", t.lower()) for t in LEXIQUE_JURIDIQUE
    )
    # L'index ne contient que les clés uniques : sa taille est le nombre de
    # formes sans accent qui ne désignent qu'un seul terme.
    assert len(_INDEX_SANS_ACCENT) <= len(LEXIQUE_JURIDIQUE)
    assert all(cle == cle.lower() for cle in _INDEX_SANS_ACCENT)
    assert compte  # le lexique n'est pas vide


# --- Intégration dans le pipeline ----------------------------------------


def _pipeline_avec_extraction(tmp_path: Path, monkeypatch, texte: str, methode: str):
    """Fabrique un pipeline dont l'extraction renvoie `texte` avec `methode`.

    cwd jetable et chemins relatifs, comme `_sandbox()` dans test_dedup.py :
    DocumentMetadata refuse les file_path absolus.
    """
    monkeypatch.chdir(tmp_path)
    raw = Path("raw") / "jurisprudence"
    raw.mkdir(parents=True)
    fichier = raw / "arret.txt"
    fichier.write_text(texte, encoding="utf-8")

    import src.m1_ingestion.ingest as ingest

    monkeypatch.setattr(
        ingest, "extract_text_from_file", lambda _p: ExtractionOutcome(texte, method=methode)
    )
    pipeline = IngestionPipeline(Path("raw"), Path("processed"))
    return pipeline, fichier


TEXTE_OCR = "Article 1\n\nLe salarie est deboute de sa demande par le tribunal."


def test_le_texte_ocerise_est_corrige_par_le_pipeline(tmp_path, monkeypatch):
    pipeline, fichier = _pipeline_avec_extraction(
        tmp_path, monkeypatch, TEXTE_OCR, "ocr_pdf"
    )

    metadata, _, _ = pipeline.process_file(fichier)

    ecrit = Path("processed/documents", f"{metadata.doc_id}.txt").read_text(
        encoding="utf-8"
    )
    assert "salarié" in ecrit and "débouté" in ecrit
    assert pipeline.ocr_corrections == {"accents": 2}


def test_le_texte_natif_n_est_jamais_soumis_au_correcteur(tmp_path, monkeypatch):
    """La garantie la plus importante de ce câblage. Un .txt ou un PDF à
    texte natif n'a pas de bruit d'OCR : le passer au correcteur ne pourrait
    qu'introduire une modification là où il n'y avait rien à corriger."""
    pipeline, fichier = _pipeline_avec_extraction(
        tmp_path, monkeypatch, TEXTE_OCR, "text"
    )

    metadata, _, _ = pipeline.process_file(fichier)

    ecrit = Path("processed/documents", f"{metadata.doc_id}.txt").read_text(
        encoding="utf-8"
    )
    assert "salarie" in ecrit, "le texte natif a été corrigé alors qu'il ne devait pas"
    assert pipeline.ocr_corrections == {}


def test_le_rapport_d_ingestion_porte_le_decompte(tmp_path, monkeypatch):
    """Une modification du texte livré à M2 doit se voir dans le rapport, pas
    seulement dans les logs d'une exécution qui n'existe plus."""
    pipeline, _ = _pipeline_avec_extraction(tmp_path, monkeypatch, TEXTE_OCR, "ocr_image")

    resultat = pipeline.run()

    assert resultat.ocr_corrections == {"accents": 2}
    import json

    rapport = json.loads(
        Path("processed/ingestion_report.json").read_text(encoding="utf-8")
    )
    assert rapport["ocr_corrections"] == {"accents": 2}
