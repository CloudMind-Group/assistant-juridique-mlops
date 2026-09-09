"""M8 — tests du contrôle des artefacts publiés.

Le cas qui a motivé ce module est réel et s'est produit deux fois : la valeur
reproduite dans `expectations_report.json` par la PR #52, six jours après que
la PR #44 eut retiré la même chose d'`ingestion_report.json`.
"""

from __future__ import annotations

import json

from src.m8_compliance.artefacts_publies import (
    Constat,
    analyser_valeur,
    verifier,
)

# Noms fabriqués, du genre que produit une collecte réelle.
DOC_IDS = frozenset({"bo-dahir-65-99-art001", "jurisprudence-2021-0093"})


def _motifs(valeur: str, doc_ids: frozenset[str] = DOC_IDS) -> list[str]:
    return [c.motif for c in analyser_valeur("champ", valeur, "f.json", doc_ids)]


# --------------------------------------------------------------------------
# Ce qui doit être signalé
# --------------------------------------------------------------------------


def test_le_chemin_absolu_reproduit_par_la_pr_52_est_signale():
    """La valeur exacte que @DOUAEM449 a reproduite avant de la corriger."""
    motifs = _motifs("C:/Users/douae/corpus/arret_ahmed_benali_2024.txt")
    assert "chemin absolu" in motifs
    assert "nom de fichier source" in motifs


def test_un_chemin_vers_le_corpus_brut_est_signale():
    assert "chemin vers le corpus brut" in _motifs(
        "data/raw/jurisprudence/jugement_El_Amrani.pdf"
    )


def test_le_separateur_windows_ne_fait_pas_echapper():
    assert "chemin vers le corpus brut" in _motifs(
        "data\\raw\\jurisprudence\\jugement_El_Amrani.pdf"
    )


def test_un_nom_de_fichier_nu_est_signale():
    """Sans répertoire, le nom seul suffit à porter une identité."""
    assert "nom de fichier source" in _motifs("arret_ahmed_benali_2024.txt")


def test_un_chemin_absolu_unix_est_signale():
    assert "chemin absolu" in _motifs("/home/douae/corpus/arret.pdf")


# --------------------------------------------------------------------------
# Ce qui ne doit pas l'être — la moitié qui décide de l'utilité du contrôle
# --------------------------------------------------------------------------


def test_la_sortie_derivee_du_doc_id_est_silencieuse():
    """`metadata.jsonl` porte un `file_path` vers la sortie. Le signaler
    rendrait le contrôle inutilisable : cinquante lignes de bruit par corpus."""
    assert not _motifs("data/processed/documents/bo-dahir-65-99-art001.txt")


def test_la_reference_de_diagnostic_est_silencieuse():
    """La forme produite par `ingest.diagnostic_ref` identifie sans nommer, et
    reste valable même pour un document jamais ingéré."""
    assert not _motifs("jurisprudence-0b2de421019f4dda.pdf")


def test_une_extension_seule_n_est_pas_un_nom_de_fichier():
    assert not _motifs(".txt")


def test_un_doc_id_sans_extension_est_silencieux():
    assert not _motifs("jurisprudence-2021-0093")


def test_un_texte_ordinaire_est_silencieux():
    assert not _motifs("Cour d'Appel de Casablanca")
    assert not _motifs("bulletin_officiel")


# --------------------------------------------------------------------------
# Sur des fichiers réels
# --------------------------------------------------------------------------


def _corpus(tmp_path, rapport: dict) -> None:
    (tmp_path / "metadata.jsonl").write_text(
        "\n".join(
            json.dumps({"doc_id": d, "file_path": f"data/processed/documents/{d}.txt"})
            for d in sorted(DOC_IDS)
        ),
        encoding="utf-8",
    )
    (tmp_path / "rapport.json").write_text(
        json.dumps(rapport, ensure_ascii=False), encoding="utf-8"
    )


def test_un_corpus_conforme_ne_produit_aucun_constat(tmp_path):
    _corpus(tmp_path, {"processed": 2, "raw_dir": "data/raw", "errors": []})
    assert verifier(tmp_path) == []


def test_la_fuite_est_trouvee_quelle_que_soit_sa_profondeur(tmp_path):
    """Le champ fautif peut être ajouté n'importe où par n'importe qui : c'est
    tout l'objet de ce contrôle, et le motif ne doit pas dépendre du nom du
    champ ni de son niveau d'imbrication."""
    _corpus(
        tmp_path,
        {
            "attentes": {
                "echecs": [
                    {"colonne": "file_path", "exemples": ["arret_ahmed_benali_2024.txt"]}
                ]
            }
        },
    )
    constats = verifier(tmp_path)
    assert constats
    assert "exemples" in constats[0].chemin_champ


def test_le_constat_designe_le_champ_et_non_le_fichier(tmp_path):
    """Un rapport qui dit « quelque part dans ce fichier » fait perdre le temps
    de celui qui doit corriger."""
    _corpus(tmp_path, {"errors": [{"file": "arret_ahmed_benali_2024.txt"}]})
    constat = verifier(tmp_path)[0]
    assert constat.chemin_champ == "errors[0].file"
    assert constat.fichier == "rapport.json"


def test_les_lignes_d_un_jsonl_sont_reperees_individuellement(tmp_path):
    (tmp_path / "metadata.jsonl").write_text(
        json.dumps({"doc_id": "bo-dahir-65-99-art001"})
        + "\n"
        + json.dumps({"doc_id": "x", "source": "arret_ahmed_benali_2024.txt"}),
        encoding="utf-8",
    )
    constats = verifier(tmp_path)
    assert len(constats) == 1
    assert constats[0].chemin_champ.startswith("L2.")


def test_un_repertoire_absent_ne_leve_pas(tmp_path):
    assert verifier(tmp_path / "inexistant") == []


def test_le_constat_est_lisible():
    constat = Constat("rapport.json", "errors[0].file", "chemin absolu", "C:/x/y.txt")
    rendu = str(constat)
    assert "rapport.json" in rendu and "errors[0].file" in rendu


# --------------------------------------------------------------------------
# Un chemin cité à l'intérieur d'une phrase
#
# Défaut relevé par @youssefelalem sur la PR #66, et le reproche portait :
# les ancres `^` et le test `endswith` laissaient passer la forme *exacte*
# d'E-R13. Mon rapport de la PR #44 disait pourtant, noir sur blanc, que
# j'avais trouvé le chemin dans le *message* de l'exception — et un message
# est précisément ce que contient le champ `errors` du rapport d'ingestion.
#
# Le contrôle n'aurait donc pas attrapé l'écart qui l'a fait naître.
# --------------------------------------------------------------------------


def test_un_chemin_cite_dans_un_message_est_signale():
    """La forme exacte d'E-R13 : le chemin figurait dans le *message* de
    l'exception, pas seulement dans un champ dédié."""
    motifs = _motifs(
        "echec de lecture de C:/Users/douae/corpus/arret_ahmed_benali_2024.txt"
    )
    assert "chemin absolu" in motifs
    assert "nom de fichier source" in motifs


def test_un_nom_suivi_de_texte_est_signale():
    """`endswith` ne voyait rien dès qu'un mot suivait le nom de fichier."""
    motifs = _motifs("fichier introuvable : /home/douae/corpus/arret_benali.pdf (code 2)")
    assert "chemin absolu" in motifs
    assert "nom de fichier source" in motifs


def test_une_valeur_fautive_n_est_signalee_qu_une_fois_par_motif():
    constats = analyser_valeur(
        "champ",
        "echec sur arret_benali.pdf puis sur arret_amrani.pdf",
        "f.json",
        DOC_IDS,
    )
    assert [c.motif for c in constats] == ["nom de fichier source"]


# --------------------------------------------------------------------------
# L'apostrophe — le faux positif qui a coûté un caractère
# --------------------------------------------------------------------------

DOC_ID_APOSTROPHE = "contrat-contrat-de-bail-à-usage-d'habitation"


def test_un_doc_id_a_apostrophe_reste_dans_la_liste_blanche():
    """Un jeton qui exclurait l'apostrophe couperait ce `doc_id` en deux : la
    souche ne correspondrait plus à la liste blanche, et le contrôle
    signalerait une sortie parfaitement légitime.

    Mesuré sur le corpus réel avant correction : quatre faux positifs, pour ce
    seul caractère. Le corpus synthétique en produit quatre à chaque
    génération, donc la régression serait visible — mais seulement pour qui
    exécute le contrôle sur un corpus, et pas pour qui lit le motif.
    """
    doc_ids = frozenset({DOC_ID_APOSTROPHE})
    assert not _motifs(
        f"data/processed/documents/{DOC_ID_APOSTROPHE}.txt", doc_ids
    )
    assert not _motifs(f"{DOC_ID_APOSTROPHE}.txt", doc_ids)


def test_un_nom_a_apostrophe_hors_liste_blanche_reste_signale():
    """La tolérance porte sur la liste blanche, pas sur l'apostrophe : un nom
    de partie qui en contient une doit rester détecté."""
    assert "nom de fichier source" in _motifs("arret_d'ahmed_benali_2024.txt")
