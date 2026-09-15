"""M1 — tests du nettoyage : en-têtes, pieds de page et paginations.

Symétrie volontaire avec les tests de segmentation et d'anonymisation :
on vérifie autant ce qui doit disparaître que ce qui doit survivre. Une
règle de nettoyage trop large abîme le fond juridique sans rien signaler,
et c'est ce mode d'échec qui coûte le plus cher en aval.
"""

from __future__ import annotations

from src.m1_ingestion.ingest import (
    MIN_HEADER_OCCURRENCES,
    clean_text,
    strip_page_artifacts,
    strip_repeated_headers,
)

# --------------------------------------------------------------------------
# Paginations : ce qui doit disparaître
# --------------------------------------------------------------------------

PAGINATIONS = [
    "Page 1",
    "Page 2/4",
    "Page 2 sur 4",
    "page n° 3",
    "- 2 -",
    "3/12",
    "صفحة 2",
]


def test_les_lignes_de_pagination_sont_supprimees():
    for pagination in PAGINATIONS:
        text = f"Article 1 - Objet.\n{pagination}\nArticle 2 - Durée."
        cleaned = strip_page_artifacts(text)

        assert pagination not in cleaned, f"pagination conservée : {pagination!r}"
        assert "Article 1 - Objet." in cleaned
        assert "Article 2 - Durée." in cleaned


def test_une_pagination_citee_dans_une_phrase_est_conservee():
    """« page 2 » au fil du texte fait partie du contenu juridique."""
    text = "Les modalités prévues page 2 du présent contrat restent applicables."

    assert strip_page_artifacts(text) == text


def test_un_numero_d_article_seul_n_est_pas_pris_pour_une_pagination():
    text = "Article 4\n\nLe présent article régit les litiges."

    assert "Article 4" in strip_page_artifacts(text)


# --------------------------------------------------------------------------
# En-têtes répétés : ce qui doit disparaître
# --------------------------------------------------------------------------


def _document_multipage(header: str, pages: int = 4) -> str:
    corps = [
        "Attendu que la rupture du contrat de travail est abusive.",
        "Attendu que les pièces versées établissent l'absence de procédure.",
        "Par ces motifs, la Cour déclare le licenciement abusif.",
        "Et condamne l'employeur au versement des indemnités légales.",
    ]
    return "\n".join(f"{header}\n{corps[i % len(corps)]}" for i in range(pages))


def test_en_tete_repete_sur_chaque_page_est_supprime():
    text = _document_multipage("Cour d'Appel de Casablanca")
    cleaned = strip_repeated_headers(text)

    assert "Cour d'Appel de Casablanca" not in cleaned
    assert "Par ces motifs, la Cour déclare le licenciement abusif." in cleaned


def test_le_corps_du_jugement_survit_integralement():
    text = _document_multipage("Tribunal de Première Instance de Fès")
    cleaned = strip_repeated_headers(text)

    for phrase in (
        "Attendu que la rupture du contrat de travail est abusive.",
        "Par ces motifs, la Cour déclare le licenciement abusif.",
        "Et condamne l'employeur au versement des indemnités légales.",
    ):
        assert phrase in cleaned, f"contenu juridique perdu : {phrase!r}"


def test_en_tete_arabe_repete_est_supprime():
    header = "محكمة الاستئناف بالدار البيضاء"
    corps = [
        "حيث تمسك الطالب بالفصل التعسفي من العمل.",
        "وحيث إن الوثائق المدلى بها تثبت غياب مسطرة تأديبية.",
        "فإنه لهذه الأسباب تصرح المحكمة بأن الفصل تعسفي.",
        "وتحكم على المشغل بأداء التعويضات القانونية.",
    ]
    text = "\n".join(f"{header}\n{ligne}" for ligne in corps)
    cleaned = strip_repeated_headers(text)

    assert header not in cleaned
    for ligne in corps:
        assert ligne in cleaned, f"contenu arabe perdu : {ligne!r}"


def test_un_document_entierement_repetitif_n_est_pas_efface():
    """Garde-fou : mieux vaut garder les en-têtes qu'un document vide."""
    text = "\n".join(["Cour d'Appel de Casablanca"] * 5)
    cleaned = strip_repeated_headers(text)

    assert cleaned.strip(), "le document a été entièrement effacé"
    assert "Cour d'Appel de Casablanca" in cleaned


# --------------------------------------------------------------------------
# En-têtes répétés : ce qui doit survivre
# --------------------------------------------------------------------------


def test_une_ligne_repetee_deux_fois_seulement_survit():
    """Deux occurrences peuvent être une coïncidence, pas une structure."""
    text = "Fait à Casablanca.\nCorps du contrat.\nFait à Casablanca."

    assert strip_repeated_headers(text).count("Fait à Casablanca.") == 2


def test_un_marqueur_structurel_repete_survit():
    """Supprimer « Article 2 » casserait la segmentation."""
    text = "\n".join(["Article 2"] * MIN_HEADER_OCCURRENCES + ["Corps du texte."])
    cleaned = strip_repeated_headers(text)

    assert cleaned.count("Article 2") == MIN_HEADER_OCCURRENCES


def test_un_marqueur_structurel_arabe_repete_survit():
    text = "\n".join(["المادة 3"] * MIN_HEADER_OCCURRENCES + ["نص المادة."])

    assert strip_repeated_headers(text).count("المادة 3") == MIN_HEADER_OCCURRENCES


def test_un_dispositif_de_jugement_repete_survit():
    """Cas signalé par Youssef en revue de la PR #41.

    Un jugement qui tranche plusieurs demandes répète sa phrase de
    dispositif — courte, donc sous le seuil de longueur, et répétée autant
    de fois qu'il y a de demandes. Le seuil de trois occurrences ne la
    protégeait pas : les trois disparaissaient. Le discriminant est la
    ponctuation finale — un en-tête n'en a pas, une phrase de jugement si.
    """
    dispositif = "Le salarié est débouté de sa demande."
    texte = "\n".join(
        [
            "Sur la première demande.",
            dispositif,
            "Sur la deuxième demande.",
            dispositif,
            "Sur la troisième demande.",
            dispositif,
            "Par ces motifs, la Cour statue comme suit.",
        ]
    )

    cleaned = strip_repeated_headers(texte)

    assert cleaned.count(dispositif) == 3, (
        "le dispositif du jugement a été supprimé — la décision rendue "
        "disparaît du corpus sans qu'aucune erreur ne soit levée"
    )


def test_un_dispositif_arabe_repete_survit():
    dispositif = "ترفض المحكمة الطلب."
    texte = "\n".join(["في الطلب الأول.", dispositif, "في الطلب الثاني.", dispositif,
                       "في الطلب الثالث.", dispositif])

    assert strip_repeated_headers(texte).count(dispositif) == 3


def test_un_en_tete_sans_ponctuation_finale_est_toujours_supprime():
    """Contrôle de non-régression du correctif : il ne doit pas neutraliser
    la règle pour les vrais en-têtes."""
    texte = _document_multipage("Cour d'Appel de Casablanca")

    assert "Cour d'Appel de Casablanca" not in strip_repeated_headers(texte)


def test_une_ligne_longue_repetee_survit():
    """Un attendu répété n'est pas un en-tête : il porte le raisonnement."""
    attendu = (
        "Attendu que les pièces versées au dossier établissent sans ambiguïté "
        "l'absence de toute procédure disciplinaire régulière préalable."
    )
    text = "\n".join([attendu] * MIN_HEADER_OCCURRENCES)

    assert strip_repeated_headers(text).count(attendu) == MIN_HEADER_OCCURRENCES


# --------------------------------------------------------------------------
# Intégration dans clean_text()
# --------------------------------------------------------------------------


def test_clean_text_combine_pagination_et_en_tetes():
    text = (
        "Cour d'Appel de Casablanca\nPage 1\nArticle 1 - Objet du contrat.\n"
        "Cour d'Appel de Casablanca\nPage 2\nArticle 2 - Obligations.\n"
        "Cour d'Appel de Casablanca\nPage 3\nArticle 3 - Durée."
    )
    cleaned = clean_text(text)

    assert "Cour d'Appel de Casablanca" not in cleaned
    assert "Page 1" not in cleaned and "Page 3" not in cleaned
    for article in ("Article 1 - Objet du contrat.", "Article 2 - Obligations.",
                    "Article 3 - Durée."):
        assert article in cleaned


def test_clean_text_reste_idempotent():
    text = "Cour d'Appel\nArticle 1 - Objet.\nCour d'Appel\nArticle 2.\nCour d'Appel"

    once = clean_text(text)
    assert clean_text(once) == once


def test_clean_text_preserve_un_document_sans_en_tete():
    text = "Article 1\n\nConformément aux dispositions de la loi n° 65-99."

    assert clean_text(text) == text
