"""M1 — tests de segmentation par articles et alinéas.

Deux choses sont protégées ici, symétriquement :

1. Les vraies frontières sont détectées (fr/ar, en début de ligne comme en
   milieu de paragraphe — les contrats du corpus enchaînent les articles
   sur une seule ligne).
2. Les *renvois* ne le sont pas. « conformément à l'article 41 » cite un
   autre texte ; le traiter comme un titre découperait le document à un
   endroit arbitraire. C'est le mode d'échec qui a déjà été constaté sur
   les règles d'anonymisation : une règle trop large abîme le texte.
"""

from __future__ import annotations

from src.m1_ingestion.segmentation import segment_document

# --------------------------------------------------------------------------
# Ce qui DOIT être détecté comme frontière
# --------------------------------------------------------------------------


def test_articles_en_debut_de_ligne():
    text = "Article 1\n\nConformément aux dispositions de la loi n° 65-99."
    segments = segment_document(text)

    assert len(segments) == 1
    assert segments[0].kind == "article"
    assert segments[0].label == "Article 1"
    assert segments[0].number == "1"


def test_articles_enchaines_sur_une_seule_ligne():
    """Format réel des contrats types du corpus."""
    text = (
        "il a été convenu ce qui suit : Article 1 - Objet du contrat. "
        "Article 2 - Obligations des parties. Article 3 - Durée et résiliation."
    )
    segments = segment_document(text)

    assert [s.number for s in segments] == ["1", "2", "3"]
    assert segments[0].text.startswith("Article 1")
    assert "Objet du contrat" in segments[0].text


def test_article_arabe():
    text = "المادة 3\n\nطبقا لأحكام القانون رقم 65.99 المتعلق بمدونة الشغل."
    segments = segment_document(text)

    assert len(segments) == 1
    assert segments[0].number == "3"
    assert segments[0].label == "المادة 3"


def test_articles_arabes_enchaines():
    text = "تم الاتفاق على ما يلي: المادة 1 - موضوع العقد. المادة 2 - التزامات الأطراف."
    segments = segment_document(text)

    assert [s.number for s in segments] == ["1", "2"]


def test_alineas_fr_et_ar():
    assert segment_document("Alinéa 2\n\nTexte de l'alinéa.")[0].kind == "alinea"
    assert segment_document("الفقرة 2\n\nنص الفقرة.")[0].kind == "alinea"


def test_article_avec_suffixe_latin():
    segments = segment_document("Article 12 bis\n\nDisposition additionnelle.")

    assert len(segments) == 1
    assert segments[0].number == "12 bis"


# --------------------------------------------------------------------------
# Ce qui ne DOIT PAS être détecté : les renvois à d'autres textes
# --------------------------------------------------------------------------

RENVOIS = [
    "La Cour condamne au titre de l'article 41 du Code du Travail.",
    "Conformément à l'article 24, l'employeur est tenu de garantir la sécurité.",
    "يعرض المشغل للعقوبات المنصوص عليها في المادة 5 من هذا الظهير.",
    "طبقا لأحكام المادة 12 من مدونة الشغل.",
]


def test_les_renvois_ne_creent_pas_de_frontiere():
    for text in RENVOIS:
        assert segment_document(text) == [], (
            f"renvoi traité à tort comme un titre de section : {text!r}"
        )


def test_document_sans_structure_ne_produit_aucun_segment():
    text = "Cour d'Appel de Casablanca - Arrêt n° 1006/2018\n\nAttendu que la partie."

    assert segment_document(text) == []


# --------------------------------------------------------------------------
# Découpage : couverture et bornes
# --------------------------------------------------------------------------


def test_les_segments_couvrent_le_texte_jusqu_a_la_fin():
    text = "Article 1 - Premier. Article 2 - Deuxième et dernier."
    segments = segment_document(text)

    assert segments[-1].end == len(text)
    assert segments[0].end == segments[1].start


def test_le_texte_avant_le_premier_article_est_exclu():
    """Un en-tête de juridiction n'est pas un article."""
    text = "Cour de Cassation - Arrêt n° 99.\n\nArticle 1 - Objet."
    segments = segment_document(text)

    assert len(segments) == 1
    assert "Cour de Cassation" not in segments[0].text
    assert segments[0].start > 0
