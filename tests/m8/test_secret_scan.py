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


# --------------------------------------------------------------------------
# Cles qui doivent venir de l'environnement
#
# Classe distincte : ici le nom est le signal et la valeur ne l'est pas. Cas
# reel, signale par @youssefelalem sur la PR #54 — la regle d'entropie
# classait « cle-secrete-temporaire-a-changer-en-production » comme gabarit
# de documentation, et elle avait raison sur sa propre question. Mais une cle
# de signature previsible n'est pas un defaut moindre qu'une cle fuitee :
# c'en est un autre, et il ne laisse aucune trace.
# --------------------------------------------------------------------------


def test_la_cle_de_signature_en_clair_est_signalee():
    findings = scan_text(
        'SECRET_KEY = "cle-secrete-temporaire-a-changer-en-production"', "s.py"  # m8:autorise valeur d'essai fabriquee, sujet meme du test
    )
    assert any(f.kind == "cle-a-charger-depuis-l-environnement" for f in findings)


def test_le_gabarit_ne_protege_pas_une_cle_de_signature():
    """Le filtre d'entropie ne s'applique pas a cette classe : pour une cle,
    tout litteral est fautif, quelle que soit son entropie."""
    assert scan_text('SIGNING_KEY = "REMPLACER"', "s.py")  # m8:autorise valeur d'essai fabriquee, sujet meme du test
    assert scan_text('JWT_SECRET = "changeme"', "s.py")  # m8:autorise valeur d'essai fabriquee, sujet meme du test


def test_la_lecture_de_l_environnement_ne_declenche_rien():
    """Le correctif attendu ne doit pas etre signale, sans quoi la regle
    punirait la bonne pratique."""
    for ligne in (
        'SECRET_KEY = os.environ["M5_JWT_SECRET"]',
        'SECRET_KEY = os.getenv("M5_JWT_SECRET")',
        'SECRET_KEY: str = Field(alias="M5_JWT_SECRET")',
    ):
        assert not scan_text(ligne, "s.py"), ligne


def test_une_interpolation_n_est_pas_un_litteral():
    """`${VAR}` est un renvoi vers l'environnement, donc exactement ce qui
    est demande — meme entre guillemets, comme l'exige YAML."""
    for ligne in (
        'JWT_SECRET: "${M5_JWT_SECRET}"',
        "JWT_SECRET: ${M5_JWT_SECRET}",
        'signing_key = "{{ vault_jwt_secret }}"',
    ):
        assert not scan_text(ligne, "compose.yml"), ligne


def test_un_fichier_d_exemple_montre_la_forme_sans_etre_fautif():
    """Un `.env.example` a pour raison d'etre de montrer la configuration :
    une valeur factice y est le contenu attendu."""
    ligne = 'SECRET_KEY="valeur-a-remplacer"'  # m8:autorise valeur d'essai fabriquee, sujet meme du test
    assert scan_text(ligne, "config.py")
    assert not scan_text(ligne, ".env.example")


def test_le_mot_de_passe_de_documentation_reste_silencieux():
    """Non-regression : la regle d'entropie garde son terrain. Le README de
    M7 documente une variable d'environnement, ce n'est pas une cle."""
    assert not scan_text('GRAFANA_PASSWORD="un-mot-de-passe-choisi"', "README.md")


def test_une_ligne_n_est_signalee_qu_une_fois():
    """`SECRET_KEY` releve des deux classes ; le rapport ne doit pas la
    compter deux fois."""
    findings = scan_text('SECRET_KEY = "V4l3ur-H4ut3-3ntr0p13-1234"', "s.py")  # m8:autorise valeur d'essai fabriquee, sujet meme du test
    assert len(findings) == 1
