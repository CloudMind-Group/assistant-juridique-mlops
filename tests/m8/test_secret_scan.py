"""M8 — tests du détecteur de secrets.

Les identifiants ci-dessous sont **fabriqués** : formats publics de
documentation, aucun n'ouvre quoi que ce soit. Ils sont assemblés par
concaténation pour que ce fichier ne se signale pas lui-même — un contrôle
qui produit du bruit sur sa propre suite de tests finit désactivé.
"""

from __future__ import annotations

from pathlib import Path

from src.m8_compliance.secret_scan import (
    Finding,
    scan_text,
    scan_tree,
)

# Assemblés en deux morceaux : le fichier reste propre pour le scanner.
AWS_ACCES = "AKIA" + "IOSFODNN7EXAMPLE"
JETON_GITHUB = "gh" + "p_16C7e42F292c6912E7710c838347Ae178B4a"
CLE_OPENAI = "sk" + "-proj-abc123XYZ456def789GHI012jkl345MNO678pqr"
JETON_SLACK = "xox" + "b-2345678901-2345678901234-AbCdEfGhIjKlMnOpQrStUvWx"
JETON_DAGSHUB = "dh" + "p_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8"
ENTETE_CLE = "-----BEGIN RSA PRIVATE " + "KEY-----"


# --------------------------------------------------------------------------
# Les sept formes que l'ancienne étape de CI laissait toutes passer
# --------------------------------------------------------------------------

FORMES_CONNUES = [
    (AWS_ACCES, "cle-acces-aws"),
    (JETON_GITHUB, "jeton-github"),
    (CLE_OPENAI, "cle-openai"),
    (JETON_SLACK, "jeton-slack"),
    (JETON_DAGSHUB, "jeton-dagshub"),
    (ENTETE_CLE, "cle-privee"),
]


def test_les_formes_connues_sont_detectees():
    for valeur, genre in FORMES_CONNUES:
        findings = scan_text(f'X = "{valeur}"')
        assert findings, f"{genre} non détecté"
        assert any(f.kind == genre for f in findings), (
            f"{genre} détecté sous un autre genre : {[f.kind for f in findings]}"
        )


def test_une_forme_est_detectee_sans_nom_evocateur():
    """C'est la faille de fond de l'ancienne étape : elle exigeait un mot-clé
    dans le nom, alors qu'un jeton se reconnaît à sa forme.
    """
    findings = scan_text(f'GITHUB_PAT = "{JETON_GITHUB}"')
    assert any(f.kind == "jeton-github" for f in findings)


def test_le_nom_en_majuscules_est_detecte():
    """L'autre faille : `grep -I` n'est pas insensible à la casse, or les
    constantes s'écrivent en majuscules.
    """
    assert scan_text('SECRET = "V4l3urQu1N3stPasUnGabarit"')  # m8:autorise valeur d'essai fabriquee


def test_le_mot_cle_est_trouve_a_l_interieur_de_l_identifiant():
    """`AWS_SECRET` n'a pas de frontière de mot avant `SECRET`."""
    assert scan_text('AWS_SECRET = "wJalrXUtnFEMI7MDENGbPxRfiCY"')  # m8:autorise valeur d'essai fabriquee


def test_url_avec_identifiants():
    assert any(
        f.kind == "url-avec-identifiants"
        # m8:autorise URL d'essai fabriquee
        for f in scan_text("url = postgres://utilisateur:M0tDeP4sse@serveur/base")
    )


# --------------------------------------------------------------------------
# Ce qui ne doit pas être signalé
# --------------------------------------------------------------------------

GABARITS = [
    'password = "REMPLACER"',
    'api_key = "<votre-cle>"',
    'token = "${GITHUB_TOKEN}"',
    'secret = "xxxxxxxxxxxx"',
    'password = "votre-mot-de-passe"',
    'GRAFANA_PASSWORD="un-mot-de-passe-choisi"',
    'password = "changeme"',
]


def test_les_gabarits_ne_sont_pas_signales():
    """Un contrôle bruyant est un contrôle qu'on finit par ignorer."""
    for ligne in GABARITS:
        assert not scan_text(ligne), f"faux positif : {ligne}"


def test_une_phrase_en_minuscules_n_est_pas_un_secret():
    """Pas de chiffre, pas de majuscule : c'est une phrase, pas une entropie."""
    assert not scan_text('password = "le-mot-de-passe-de-la-demonstration"')


def test_une_valeur_courte_n_est_pas_signalee():
    assert not scan_text('token = "abc"')


# --------------------------------------------------------------------------
# Exceptions justifiées
# --------------------------------------------------------------------------


def test_le_marqueur_neutralise_sur_la_meme_ligne():
    ligne = f'CLE = "{AWS_ACCES}"  # m8:autorise exemple de documentation'
    assert not scan_text(ligne)


def test_le_marqueur_neutralise_sur_la_ligne_precedente():
    texte = f'# m8:autorise exemple de documentation\nCLE = "{AWS_ACCES}"'
    assert not scan_text(texte)


def test_le_marqueur_ne_neutralise_pas_les_lignes_suivantes():
    """Une exception vaut pour un cas, pas pour un fichier."""
    texte = (
        f'# m8:autorise exemple\nCLE = "{AWS_ACCES}"\nAUTRE = "{JETON_GITHUB}"'
    )
    findings = scan_text(texte)
    assert findings and all(f.line_no == 3 for f in findings)


# --------------------------------------------------------------------------
# Le rapport lui-même
# --------------------------------------------------------------------------


def test_le_secret_n_est_jamais_reimprime_en_entier():
    """Le rapport de CI est public : y recopier le secret le divulguerait
    une seconde fois, à l'endroit même censé le signaler."""
    findings = scan_text(f'CLE = "{AWS_ACCES}"')
    for f in findings:
        assert AWS_ACCES not in f.excerpt
        assert "*" in f.excerpt


def test_la_position_est_exacte():
    texte = f'ligne1\nligne2\nCLE = "{AWS_ACCES}"'
    assert scan_text(texte)[0].line_no == 3


# --------------------------------------------------------------------------
# Le garde-fou : le dépôt lui-même
# --------------------------------------------------------------------------


def test_le_depot_ne_contient_aucun_secret():
    racine = Path(__file__).resolve().parents[2]
    findings = scan_tree(racine)
    assert not findings, "secrets potentiels dans le dépôt :\n" + "\n".join(
        f"  {f}" for f in findings
    )
