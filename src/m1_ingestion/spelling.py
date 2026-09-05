"""
Module 1 — Correction orthographique adaptée au vocabulaire juridique.

Le cahier des charges (carte 01) demande une correction orthographique
« adaptée au vocabulaire juridique » sur les documents océrisés. L'adjectif
porte tout le sens : un correcteur généraliste est **dangereux** sur un
corpus de droit. Branché sur un dictionnaire français ordinaire, il
signalerait « Dahir », « alinéa », « Chraa » comme des fautes, et
« corrigerait » les noms propres des parties et les numéros d'articles. Le
remède serait pire que le mal — le bruit d'OCR est visible, un texte
juridique silencieusement réécrit ne l'est pas.

Ce module prend donc le problème par l'autre bout : il ne sait rien du
français, il ne connaît qu'un **lexique juridique fermé**. Un mot n'est
corrigé que si la correction produit un terme de ce lexique, et qu'elle
est **la seule** à le faire. Tout le reste est laissé intact.

Deux règles, et deux seulement :

  A. **Restitution d'accents** — « salarie » → « salarié ». C'est le défaut
     le plus fréquent de l'OCR et des encodages mal négociés en français.
     Ne s'applique qu'aux mots entièrement alphabétiques dont la forme sans
     accent désigne un seul terme du lexique.

  B. **Confusions de caractères** — « artic1e » → « article », « C0ur » →
     « Cour ». Ne s'applique **qu'aux mots qui mélangent lettres et
     chiffres** (ou portent un artefact typographique comme « | »). Un mot
     tout en lettres n'est jamais soumis à cette règle : c'est ce qui
     garantit qu'aucun mot français ordinaire ni aucun nom propre ne peut
     être transformé par accident.

Ce que ce module **ne fait pas**, et qu'il ne faut pas croire fait :

  - Il ne corrige pas l'arabe. Les confusions de l'OCR arabe sont d'une
    autre nature (formes contextuelles des lettres, diacritiques), et
    constituer un lexique juridique arabe fiable est un travail à part
    entière. Les mots arabes sont détectés et laissés strictement intacts.
  - Il ne corrige pas les mots absents du lexique, donc l'essentiel du
    texte. Il ne remplace pas une relecture humaine.
  - Il ne touche jamais aux nombres, dates, numéros de loi ou d'article :
    aucun candidat produit à partir d'eux n'appartient au lexique.

Usage :
    from src.m1_ingestion.spelling import corriger_document
    texte_corrige, corrections = corriger_document(texte_ocr)
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger("m1_ingestion.spelling")


# --- Lexique juridique --------------------------------------------------
# Termes du droit marocain et du vocabulaire procédural français employés
# dans le corpus (Bulletin Officiel, jurisprudence, contrats types). Fermé
# et curé à la main : c'est volontaire. Un lexique appris sur le corpus
# apprendrait aussi ses fautes d'OCR et les tiendrait ensuite pour justes.
#
# Pour l'étendre : ajouter le terme dans sa forme correcte, accents compris.
# Un terme dont la forme sans accent est ambiguë avec un autre terme du
# lexique sera automatiquement ignoré par la règle A (voir _index_sans_accent).
LEXIQUE_JURIDIQUE: frozenset[str] = frozenset(
    {
        # Sources et textes
        "dahir", "bulletin", "officiel", "jurisprudence", "arrêt", "arrêts",
        "arrêté", "arrêtés", "décret", "décrets", "loi", "lois", "code",
        "codes", "article", "articles", "alinéa", "alinéas", "chapitre",
        "chapitres", "titre", "titres", "section", "sections", "annexe",
        "annexes", "préambule", "disposition", "dispositions", "circulaire",
        "circulaires", "ordonnance", "ordonnances", "règlement", "règlements",
        "textes", "texte", "promulgation", "promulgué", "publication",
        "abrogé", "abrogée", "abrogation", "modifié", "modifiée",
        "complété", "complétée", "vigueur",
        # Juridictions
        "tribunal", "tribunaux", "cour", "cours", "appel", "cassation",
        "chambre", "chambres", "instance", "juridiction", "juridictions",
        "commerce", "administratif", "administrative", "civil", "civile",
        "pénal", "pénale", "social", "sociale", "première", "suprême",
        "juge", "juges", "magistrat", "magistrats", "greffe", "greffier",
        "audience", "audiences", "siège", "ressort",
        # Procédure
        "requête", "requérant", "requérante", "demandeur", "demanderesse",
        "défendeur", "défenderesse", "partie", "parties", "plaidoirie",
        "assignation", "citation", "délibéré", "délibération", "jugement",
        "jugements", "ordonnance", "pourvoi", "recours", "moyen", "moyens",
        "motifs", "motif", "dispositif", "considérant", "attendu", "statuant",
        "débouté", "déboutée", "condamné", "condamnée", "condamnation",
        "irrecevable", "recevable", "recevabilité", "compétence",
        "compétent", "incompétence", "nullité", "annulation", "sursis",
        "exécution", "exécutoire", "notification", "signification",
        "prescription", "forclusion", "instruction", "expertise",
        "témoignage", "témoin", "preuve", "preuves", "présomption",
        # Droit du travail
        "salarié", "salariée", "salariés", "salaire", "salaires",
        "employeur", "employeurs", "employé", "employée", "travail",
        "travailleur", "travailleurs", "contrat", "contrats", "embauche",
        "licenciement", "licencié", "licenciée", "démission", "préavis",
        "indemnité", "indemnités", "indemnisation", "ancienneté",
        "congé", "congés", "durée", "déterminée", "indéterminée",
        "essai", "période", "syndicat", "syndicale", "grève", "convention",
        "collective", "accident", "maladie", "professionnelle", "retraite",
        "cotisation", "cotisations", "affiliation", "immatriculation",
        # Droit civil et des affaires
        "société", "sociétés", "associé", "associés", "actionnaire",
        "actionnaires", "gérant", "gérance", "capital", "part", "parts",
        "action", "actions", "assemblée", "générale", "statuts", "siège",
        "commercial", "commerciale", "commerçant", "fonds", "bail", "loyer",
        "locataire", "bailleur", "propriété", "propriétaire", "immeuble",
        "vente", "acheteur", "vendeur", "obligation", "obligations",
        "créance", "créancier", "débiteur", "dette", "garantie", "caution",
        "hypothèque", "nantissement", "faillite", "liquidation",
        "redressement", "judiciaire", "succession", "héritier", "héritiers",
        "donation", "testament", "mariage", "divorce", "filiation",
        "responsabilité", "dommage", "dommages", "intérêts", "préjudice",
        "faute", "négligence", "réparation",
        # Fiscal et administratif
        "impôt", "impôts", "fiscal", "fiscale", "taxe", "taxes", "assiette",
        "recouvrement", "contribuable", "déclaration", "exonération",
        "redevance", "amende", "pénalité", "pénalités", "douane",
        "administration", "administratif", "autorisation", "agrément",
        "licence", "concession", "marché", "publics", "publique",
        # Termes marocains et institutions
        "maroc", "marocain", "marocaine", "royaume", "chérifien", "majesté",
        "roi", "gouvernement", "ministre", "ministère", "wali", "gouverneur",
        "commune", "préfecture", "province", "région", "casablanca", "rabat",
        "marrakech", "tanger", "fès", "agadir", "meknès", "oujda", "tétouan",
        "moudawana", "chraa", "adoul", "adel", "melkia", "habous",
        # Génériques procéduraux fréquents
        "conformément", "notamment", "susvisé", "susvisée", "précité",
        "précitée", "ci-dessus", "présent", "présente", "susdit",
        "nonobstant", "ledit", "ladite", "aux", "termes", "vu", "ouï",
    }
)

# --- Confusions de caractères de l'OCR ----------------------------------
# Confusions documentées de Tesseract sur du texte imprimé. La table est
# courte à dessein : chaque entrée élargit l'espace des candidats, donc le
# risque d'une correction fortuite. Elles ne s'appliquent qu'aux mots
# mêlant lettres et chiffres (règle B).
CONFUSIONS_OCR: tuple[tuple[str, str], ...] = (
    ("0", "o"),
    ("1", "l"),
    ("1", "i"),
    ("3", "e"),
    ("4", "a"),
    ("5", "s"),
    ("6", "b"),
    ("7", "t"),
    ("8", "b"),
    ("9", "g"),
    ("|", "l"),
    ("!", "l"),
    ("¡", "i"),
    ("$", "s"),
    ("@", "a"),
)

# Au-delà de deux substitutions, on ne corrige plus : on devine. Un mot qui
# demande trois corrections pour ressembler à un terme du lexique ressemble
# tout autant à autre chose.
MAX_SUBSTITUTIONS = 2

# Garde-fou de coût : au-delà, le mot n'est pas un mot.
LONGUEUR_MAX_MOT = 30

_MOT_RE = re.compile(r"[^\W_]+", re.UNICODE)
_ARABE_RE = re.compile(r"[؀-ۿ]")
_ARTEFACTS = frozenset("|!¡$@")


@dataclass(frozen=True)
class Correction:
    """Une correction appliquée, avec de quoi la rejouer et la contester."""

    avant: str
    apres: str
    position: int
    regle: str  # "accents" | "confusion_ocr"

    def to_dict(self) -> dict[str, object]:
        return {
            "avant": self.avant,
            "apres": self.apres,
            "position": self.position,
            "regle": self.regle,
        }


def _sans_accent(mot: str) -> str:
    """Forme sans diacritiques, en minuscules."""
    decompose = unicodedata.normalize("NFD", mot.lower())
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def _construire_index_sans_accent() -> dict[str, str]:
    """clé sans accent -> terme du lexique, seulement si la clé est unique.

    Une clé qui désigne deux termes différents est retirée de l'index : on
    ne devine pas entre « pénal » et « penal » s'ils coexistaient. Aucune
    ambiguïté n'est arbitrée en silence.
    """
    par_cle: dict[str, set[str]] = {}
    for terme in LEXIQUE_JURIDIQUE:
        par_cle.setdefault(_sans_accent(terme), set()).add(terme)

    index = {cle: next(iter(termes)) for cle, termes in par_cle.items() if len(termes) == 1}
    ambigus = {cle for cle, termes in par_cle.items() if len(termes) > 1}
    if ambigus:
        logger.debug("Clés sans accent ambiguës, ignorées : %s", sorted(ambigus))
    return index


_INDEX_SANS_ACCENT = _construire_index_sans_accent()


def _appliquer_casse(modele: str, correction: str) -> str:
    """Reporte la casse du mot d'origine sur sa correction.

    « SALARIE » doit rester en capitales : dans un jugement, les capitales
    marquent souvent un intitulé, et les écraser change la structure lue
    par la segmentation.
    """
    if modele.isupper() and len(modele) > 1:
        return correction.upper()
    if modele[:1].isupper():
        return correction[:1].upper() + correction[1:]
    return correction


def _candidats_par_confusion(mot: str) -> set[str]:
    """Mots atteignables en au plus MAX_SUBSTITUTIONS confusions connues."""
    niveau = {mot.lower()}
    atteints = set()
    for _ in range(MAX_SUBSTITUTIONS):
        suivant = set()
        for courant in niveau:
            for source, cible in CONFUSIONS_OCR:
                debut = 0
                while (position := courant.find(source, debut)) != -1:
                    variante = courant[:position] + cible + courant[position + len(source) :]
                    if variante not in atteints:
                        suivant.add(variante)
                    debut = position + 1
        atteints |= suivant
        niveau = suivant
        if not niveau:
            break
    return atteints


def _corriger_mot(mot: str) -> tuple[str, str] | None:
    """Renvoie (correction, règle) ou None si le mot doit rester intact."""
    if len(mot) > LONGUEUR_MAX_MOT or len(mot) < 3:
        return None
    if _ARABE_RE.search(mot):
        # Hors périmètre, et assumé comme tel : voir l'en-tête du module.
        return None
    if mot.lower() in LEXIQUE_JURIDIQUE:
        return None

    # --- Règle A : restitution d'accents -------------------------------
    if mot.isalpha():
        terme = _INDEX_SANS_ACCENT.get(_sans_accent(mot))
        # Le terme doit réellement différer par les accents : sans quoi on
        # ne corrige rien, on renomme.
        if terme is not None and _sans_accent(terme) != terme.lower():
            return _appliquer_casse(mot, terme), "accents"
        return None

    # --- Règle B : confusions de caractères ----------------------------
    # Réservée aux mots mêlant lettres et chiffres, ou portant un artefact.
    # C'est la garantie qu'un mot français ordinaire — et un nom propre —
    # ne peut pas être réécrit par cette règle.
    a_chiffre = any(c.isdigit() for c in mot)
    a_artefact = any(c in _ARTEFACTS for c in mot)
    a_lettre = any(c.isalpha() for c in mot)
    if not a_lettre or not (a_chiffre or a_artefact):
        return None

    candidats = {c for c in _candidats_par_confusion(mot) if c in LEXIQUE_JURIDIQUE}
    # Une seule lecture possible, sinon on s'abstient. Deux candidats
    # valides signifient qu'on choisirait à la place du lecteur.
    if len(candidats) != 1:
        if len(candidats) > 1:
            logger.debug("Correction ambiguë pour %r : %s", mot, sorted(candidats))
        return None

    return _appliquer_casse(mot, candidats.pop()), "confusion_ocr"


def corriger_document(texte: str) -> tuple[str, list[Correction]]:
    """Corrige le texte et renvoie la liste des corrections appliquées.

    La liste est le pendant de l'``anonymize_document`` : une transformation
    du corpus qui ne laisse pas de trace n'est pas auditable, et personne ne
    peut alors contester une correction précise.
    """
    if not texte:
        return texte, []

    corrections: list[Correction] = []
    morceaux: list[str] = []
    curseur = 0

    for correspondance in _MOT_RE.finditer(texte):
        resultat = _corriger_mot(correspondance.group())
        if resultat is None:
            continue
        remplacement, regle = resultat
        morceaux.append(texte[curseur : correspondance.start()])
        morceaux.append(remplacement)
        curseur = correspondance.end()
        corrections.append(
            Correction(
                avant=correspondance.group(),
                apres=remplacement,
                position=correspondance.start(),
                regle=regle,
            )
        )

    if not corrections:
        return texte, []

    morceaux.append(texte[curseur:])
    return "".join(morceaux), corrections


def corriger_texte(texte: str) -> str:
    """Variante sans trace, pour les appels qui n'exploitent pas l'audit."""
    corrige, _ = corriger_document(texte)
    return corrige


def resumer(corrections: Iterable[Correction]) -> dict[str, int]:
    """Décompte par règle, pour le rapport d'ingestion."""
    resume: dict[str, int] = {}
    for correction in corrections:
        resume[correction.regle] = resume.get(correction.regle, 0) + 1
    return resume
