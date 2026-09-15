"""M8 — écriture du journal d'audit.

Met en œuvre le contrat de `docs/OBSERVABILITE.md` §2, jusqu'ici défini mais
jamais implémenté (écart **E-04** du registre). Le contrat couvrait le
transport — Promtail vers Loki — mais rien ne produisait d'événement conforme.

Ce module comble cette moitié-là. Il n'écrit pas dans Loki : il produit une
ligne JSON conforme et l'ajoute à un fichier que Promtail suit. M5 appelle,
M8 garantit la forme.

Trois choix de conception, dont deux se lisent mal dans le code :

**Le pseudonymat est calculé ici, jamais par l'appelant.** `journaliser()`
reçoit l'identifiant réel et le transforme lui-même. L'inverse — demander à M5
de fournir une empreinte déjà calculée — placerait l'interdiction du §2.3 dans
la discipline de l'appelant, et un seul oubli écrirait un nom en clair dans un
journal conservé trois ans. Une règle que le code rend impossible à enfreindre
vaut mieux qu'une règle écrite dans un document.

**Un contenu interdit provoque un refus, jamais un nettoyage.** Un événement
silencieusement expurgé est un événement que personne n'ira examiner, et
l'appel fautif resterait en place. L'exception est bruyante par choix.

**La clé vient de l'environnement, sans valeur de repli.** Une clé prévisible
ne protège rien : l'ensemble des comptes est énumérable, et qui détient le
journal retrouve les correspondances en quelques secondes. Mieux vaut un
service qui refuse de démarrer qu'un service qui journalise sous une clé
publique — c'est la règle appliquée aux clés de signature de M5.

Usage :
    from src.m8_compliance.audit import journaliser

    journaliser(
        type_evenement="answer.generated",
        acteur="utilisateur-4821",      # identifiant réel : jamais écrit tel quel
        role="juriste",
        question="quelles sont les conditions de rupture ?",
        sources_citees=["jurisprudence-0b2de421019f4dda"],
        modele="legal-fr-v2",
        duree_ms=1840,
    )
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

# --------------------------------------------------------------------------
# Contrat — §2.4 et matrice des habilitations
# --------------------------------------------------------------------------

TYPES_EVENEMENT = (
    "auth.login",
    "auth.denied",
    "corpus.read",
    "answer.generated",
    "answer.exported",
)

# Alignés sur `actor_role` de docs/HABILITATIONS.md. Une valeur hors liste est
# refusée : un rôle inconnu rend l'audit des accès inexploitable, puisque c'est
# le rôle qui dit si un accès était légitime.
ROLES = ("particulier", "juriste", "gestionnaire", "admin")

VARIABLE_CLE = "M8_AUDIT_HMAC_KEY"

# Répertoire suivi par Promtail — docs/OBSERVABILITE.md §2.1.
CHEMIN_DEFAUT = Path("monitoring/audit/audit.jsonl")

# --------------------------------------------------------------------------
# §2.3 — ce qui ne doit jamais être journalisé
# --------------------------------------------------------------------------

_COURRIEL = re.compile(r"[^\s@]+@[^\s@]+\.[A-Za-z]{2,}")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6 = re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){3,7}[0-9A-Fa-f]{1,4}\b")
_JETON_JWT = re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.")

INTERDITS = (
    ("adresse électronique", _COURRIEL),
    ("adresse IP", _IPV4),
    ("adresse IP", _IPV6),
    ("jeton d'authentification", _JETON_JWT),
)


class ContratAuditError(ValueError):
    """Un événement viole le contrat. Levée avant toute écriture."""


def _cle_hmac() -> bytes:
    cle = os.environ.get(VARIABLE_CLE)
    if not cle:
        raise ContratAuditError(
            f"{VARIABLE_CLE} absente de l'environnement. Le journal ne peut pas "
            "être écrit sous une clé prévisible : l'ensemble des comptes est "
            "énumérable, et un HMAC dont la clé est connue n'anonymise rien. "
            "Définir la variable, ou ne pas journaliser."
        )
    return cle.encode("utf-8")


def empreinte(valeur: str) -> str:
    """HMAC-SHA-256 tronqué à 32 caractères hexadécimaux.

    Un HMAC, jamais un condensé nu — §2.2. Un SHA-256 simple n'anonymise rien
    quand l'espace d'entrée est petit et énumérable, et celui des comptes comme
    celui des questions juridiques courantes l'est.

    Tronqué parce que le journal est relu par des humains : 128 bits restent
    hors de portée d'une collision recherchée, et la seule propriété utile ici
    est que deux consultations identiques donnent la même valeur.
    """
    return hmac.new(_cle_hmac(), valeur.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def _normaliser_question(question: str) -> str:
    """Réduire les variations de forme avant l'empreinte.

    Deux formulations identiques à la casse et aux espaces près doivent donner
    la même empreinte, sans quoi la détection d'usage anormal — le seul usage
    prévu de ce champ — ne voit que du bruit.
    """
    return re.sub(r"\s+", " ", question.strip().lower())


def _chaines(valeur: Any) -> Iterable[str]:
    if isinstance(valeur, str):
        yield valeur
    elif isinstance(valeur, (list, tuple)):
        for element in valeur:
            yield from _chaines(element)


def _refuser_contenu_interdit(evenement: dict[str, Any]) -> None:
    for cle, valeur in evenement.items():
        for texte in _chaines(valeur):
            for libelle, motif in INTERDITS:
                if motif.search(texte):
                    raise ContratAuditError(
                        f"champ « {cle} » : {libelle} détectée. Le §2.3 "
                        "l'interdit — le journal deviendrait lui-même un "
                        "traitement de données personnelles, alors qu'il existe "
                        "pour en attester la maîtrise."
                    )


def _horodatage() -> str:
    """RFC 3339, UTC, systématiquement — §2.1."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def construire(
    *,
    type_evenement: str,
    acteur: str,
    role: str,
    question: Optional[str] = None,
    ressources: Optional[list[str]] = None,
    sources_citees: Optional[list[str]] = None,
    identifiant_reponse: Optional[str] = None,
    modele: Optional[str] = None,
    duree_ms: Optional[int] = None,
    resultat: str = "success",
    code_erreur: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Construire un événement conforme, sans l'écrire.

    Séparé de l'écriture pour que M5 puisse le tester sans toucher au disque,
    et pour que la validation reste vérifiable indépendamment du transport.
    """
    if type_evenement not in TYPES_EVENEMENT:
        raise ContratAuditError(
            f"type d'événement inconnu : {type_evenement!r}. Le §2.4 en définit "
            f"cinq : {', '.join(TYPES_EVENEMENT)}."
        )
    if role not in ROLES:
        raise ContratAuditError(
            f"rôle inconnu : {role!r}. La matrice des habilitations en définit "
            f"quatre : {', '.join(ROLES)}. Un rôle hors liste rend l'audit des "
            "accès inexploitable, puisque c'est le rôle qui dit si un accès "
            "était légitime."
        )
    if resultat not in ("success", "error"):
        raise ContratAuditError(f"résultat inconnu : {resultat!r}")
    if resultat == "error" and not code_erreur:
        raise ContratAuditError(
            "résultat « error » sans code_erreur : le §2.2 le rend obligatoire. "
            "Un échec sans motif n'apprend rien à qui relit le journal."
        )
    if not acteur:
        raise ContratAuditError("acteur vide : le §2.2 rend actor_id obligatoire.")

    evenement: dict[str, Any] = {
        "ts": _horodatage(),
        "event_id": str(uuid.uuid4()),
        "event_type": type_evenement,
        # Empreinte calculée ici, jamais fournie par l'appelant.
        "actor_id": empreinte(acteur),
        "actor_role": role,
        "outcome": resultat,
    }
    if question is not None:
        evenement["query_hash"] = empreinte(_normaliser_question(question))
    if ressources:
        evenement["resource_ids"] = list(ressources)
    if sources_citees:
        evenement["sources_cited"] = list(sources_citees)
    if identifiant_reponse:
        evenement["answer_id"] = identifiant_reponse
    if modele:
        evenement["model"] = modele
    if duree_ms is not None:
        evenement["duration_ms"] = int(duree_ms)
    if code_erreur:
        evenement["error_code"] = code_erreur
    if trace_id:
        evenement["trace_id"] = trace_id

    # Contrôle en dernier : il porte sur l'événement tel qu'il sera écrit, y
    # compris les champs que l'appelant a remplis librement.
    _refuser_contenu_interdit(evenement)
    return evenement


def journaliser(chemin: Optional[Path] = None, **champs: Any) -> dict[str, Any]:
    """Construire un événement et l'ajouter au journal. Ajout seul — §2.1.

    Le fichier est ouvert en mode « a », et rien dans ce module n'expose de
    modification ni de suppression : l'immuabilité tient à ce qui n'existe pas,
    non à une promesse.
    """
    evenement = construire(**champs)
    destination = Path(chemin) if chemin else CHEMIN_DEFAUT
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as fichier:
        fichier.write(json.dumps(evenement, ensure_ascii=False) + "\n")
    return evenement
