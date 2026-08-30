# Registre des traitements de données à caractère personnel

**Responsable du registre :** Taha Kachmar — M8, Sécurité, Gouvernance & Conformité
**Version :** 1.1 — 29 août 2026
**Textes applicables :** Loi 09-08 (Maroc) · RGPD (UE), applicable si le service est ouvert à des résidents de l'Union
**Autorité de contrôle :** CNDP

> Ce document est tenu à jour en même temps que le code. Toute modification du
> pipeline d'ingestion, du stockage ou de l'indexation qui change ce qui est
> décrit ici doit mettre à jour ce registre dans la même pull request.

---

## Sommaire

- [1. Périmètre](#1-périmètre)
- [2. État du corpus à ce jour](#2-état-du-corpus-à-ce-jour)
- [3. Fiches de traitement](#3-fiches-de-traitement)
- [4. Droits des personnes](#4-droits-des-personnes)
- [5. Registre des écarts](#5-registre-des-écarts)
- [6. Preuves](#6-preuves)
- [7. Révision](#7-révision)

---

## 1. Périmètre

Le système ingère des textes juridiques marocains et les restitue via un
assistant conversationnel qui cite ses sources.

Trois sources sont admises, définies par
[`metadata_schema.SourceType`](../src/m1_ingestion/metadata_schema.py) :

| Source | Données personnelles attendues |
|---|---|
| Bulletin Officiel | Aucune — un texte de loi ne nomme pas de particulier |
| Contrat Type | Aucune — modèle vierge, parties désignées par un rôle |
| **Jurisprudence** | **Oui — identités des parties, témoins et conseils** |

**Une seule source sur trois porte des données personnelles.** C'est elle qui
fait entrer le projet dans le champ de la loi 09-08, et c'est sur elle que
portent les mesures décrites ici.

Le fait qu'une décision de justice soit publiée ne dispense pas du présent
registre : la republication sous forme de moteur de réponse constitue un
traitement distinct de la publication d'origine.

## 2. État du corpus à ce jour

**Volume de données personnelles réellement traitées : zéro.**

Le corpus en circulation est intégralement synthétique — 121 fichiers, environ
60 documents, 37 Ko — produit par
[`dataset_generator.py`](../src/m1_ingestion/dataset_generator.py) pour permettre
à M2 de démarrer sans attendre la collecte réelle. Vérification faite sur les
gabarits du générateur : les jugements y désignent les parties par leur rôle
(« la partie demanderesse », « l'employeur ») et les contrats par
« Partie A n° _i_ » ; aucun nom, numéro de CIN, téléphone, adresse ou e-mail
n'y figure.

Ce registre décrit donc le traitement **tel qu'il s'appliquera dès l'arrivée du
corpus réel**, la chaîne technique étant déjà en place. Il est rédigé avant
l'incident, non après.

> **Origine des sources — décision du 29 août 2026.** Les décisions de justice
> proviendront exclusivement de **recueils publiés dont l'identification a déjà
> été retirée à la publication**. Les pièces brutes, archives de cabinet et
> décisions non publiées sont écartées.
>
> Cela réduit fortement le volume de données personnelles entrant et fait de
> l'anonymisation du pipeline une **seconde barrière** plutôt que l'unique.
> Deux réserves : la pseudonymisation à la publication n'est pas exhaustive —
> les noms subsistent fréquemment dans le corps des motifs, même en-tête traité
> — et toute source hors de ce périmètre impose de réviser l'analyse d'impact
> au préalable. Motivation détaillée en [AIPD.md](AIPD.md), §6.

## 3. Fiches de traitement

### T-01 — Ingestion, nettoyage et anonymisation

| | |
|---|---|
| **Finalité** | Constituer une base de connaissances juridiques interrogeable |
| **Base légale** | Intérêt légitime — art. 6 RGPD / loi 09-08 |
| **Catégories de données** | Noms de personnes physiques · numéros CIN · téléphones · adresses postales · adresses e-mail |
| **Personnes concernées** | Parties, témoins, conseils et magistrats cités dans les décisions |
| **Responsable opérationnel** | Douae Moussaoui (M1) — règles définies par M8 |
| **Destinataires** | M2 (indexation) → M5 (API) → M6 (interface) → utilisateur final |
| **Durée de conservation** | **Trois ans** à compter de l'ingestion, puis réingestion des sources toujours pertinentes (décision du 29/08/2026) |
| **Transfert hors Maroc** | Oui — hébergement DagsHub (voir T-02) |

**Mesure principale.** L'anonymisation s'exécute **dans le pipeline, entre le
nettoyage et l'écriture** :

```
extraction → nettoyage → anonymisation → écriture dans data/processed/
```

Ce placement est la mesure de fond du dispositif. Il est le dernier point où
retirer une personne reste une édition de texte : après le découpage et la
vectorisation par M2, la même opération devient une reconstruction d'index.
Aucune donnée personnelle n'atteint `data/processed/`, donc aucune n'atteint
l'indexation.

**Règles appliquées** — dix règles, définies dans
[`anonymization_schema.py`](../src/m1_ingestion/anonymization_schema.py) :

| Catégorie | Règles | Traitement |
|---|---|---|
| CIN | annoncée par sa mention · isolée | remplacée par `[CIN]` |
| Nom | civilité (fr) · qualité procédurale (fr) · `ENTRE` · لقب (ar) · صفة في الدعوى (ar) | remplacé par `[NOM]` |
| Téléphone | fixe et mobile, `+212` ou `0` | masquage partiel, `06******78` |
| E-mail | — | remplacé par `[EMAIL]` |
| Adresse | voie, quartier, lotissement, résidence | remplacée par `[ADRESSE]` |

Le masquage partiel du téléphone est délibéré : il permet de constater que deux
occurrences désignent la même personne sans révéler laquelle, ce qu'un
remplacement total interdirait.

**Mesures de non-destruction.** Une règle de masquage trop large est une panne
silencieuse : rien n'échoue, le rapport de qualité affiche 100 % de succès, et
l'assistant répond avec des décisions amputées. Deux garde-fous :

- les identifiants d'affaire, d'entreprise et de publication (`RC`, `BO`, `RG`,
  `TP`, `IF`, `ICE`, `TVA`, `CNSS`, `AMO`) sont explicitement exclus de la règle
  CIN, ainsi que les montants ;
- une règle ancrée sur un marqueur juridique ne masque que le nom, pas le
  marqueur : « le salarié X » devient « le salarié `[NOM]` », la qualité
  procédurale — qui est un fait du jugement — survit.

**Minimisation.** Répondre à une question de droit ne requiert pas de savoir qui
étaient les parties : la règle et le raisonnement suffisent. Ces données n'ont
donc pas à entrer dans le système, ce qui fonde l'ensemble du dispositif.

**Identifiants.** `doc_id` et `title` sont dérivés du dossier source et d'une
empreinte, jamais du nom de fichier. Un document collecté sous
`arret_ahmed_benali_2024.pdf` porterait sinon une identité réelle jusque dans
les citations affichées à l'utilisateur, en survivant à tout masquage du texte.

**Traçabilité.** Chaque exécution journalise le nombre d'occurrences masquées,
par document et au total (`IngestResult.pii_masked`). Un jugement traité avec
zéro masquage est un signal à examiner.

**Propagation des noms.** Les règles ancrées exigent une civilité ou une qualité
procédurale, alors qu'une partie est introduite une fois puis désignée nue
pendant des pages. Une seconde passe masque donc, dans le même document, toute
autre occurrence d'un nom déjà identifié par une règle ancrée. Sur un jugement
représentatif, le rappel sur les noms passe de 50 % à 100 % (§6). Seules les
détections ancrées amorcent le mécanisme : un faux positif reste local au lieu
d'être amplifié. Le vocabulaire d'institution et de procédure en est exclu, de
sorte que « Cour », « Tribunal » ou « salarié » ne soient jamais masqués à
l'échelle du document.

**Limite connue.** Le dispositif repose sur des expressions régulières, et la
propagation s'amorce sur les détections ancrées : un nom qui n'apparaît
**jamais** accompagné d'une civilité ou d'une qualité procédurale échappe
encore à la détection. Voir écart E-01.

### T-02 — Stockage et versionnement du corpus

| | |
|---|---|
| **Finalité** | Traçabilité et reproductibilité des jeux de données |
| **Support** | DVC — remote déclaré dans [`.dvc/config`](../.dvc/config) |
| **Localisation** | `dagshub.com/CloudMind-Group` — **compte de l'organisation** (migré le 29/08/2026, PR #15) |
| **Volume** | 121 fichiers · 37 Ko · corpus synthétique |
| **Visibilité** | **Privé** — vérifié le 27/08/2026 (voir §6) |
| **Contrôle d'accès** | Non exerçable par l'organisation |
| **Journal d'accès** | Indisponible |
| **Chiffrement au repos** | Non documenté |

Le dépôt était public jusqu'au 27/08/2026 et a été passé en privé le jour même.
Le corpus exposé était synthétique : aucune donnée personnelle n'a été publiée.

Le remote pointait jusqu'au 29/08/2026 vers le compte personnel de la
responsable de M1. Deux risques en découlaient, indépendants du contenu : la
fermeture de ce compte aurait fait perdre le corpus — `dvc.yaml` et `dvc.lock`
pointant alors dans le vide, le pipeline cessant d'être reproductible — et les
obligations de contrôle d'accès et de journalisation incombant à M8 n'étaient
pas exerçables sur le compte d'un tiers.

**Le remote a été migré vers le compte de l'organisation** (PR #15). Les deux
risques sont levés dans leur principe : l'accès ne dépend plus d'une personne,
et l'administration du dépôt revient à l'organisation.

**Reste à faire :** le contrôle d'accès par rôle et la journalisation ne sont
pas configurés pour autant — la migration les rend possibles, elle ne les
réalise pas. Voir écart E-04. Le chiffrement au repos demeure non documenté
(E-06).

### T-03 — Indexation et restitution *(à venir — M2, M5, M6)*

Non mis en œuvre : M2 n'a pas démarré. Cette fiche sera renseignée dès que le
schéma d'indexation sera arrêté.

**Exigence à intégrer dès la conception, et non après :** l'index vectoriel doit
permettre la suppression ciblée d'un `doc_id`. Sans cela, le droit à l'effacement
devient non pas coûteux mais **techniquement inapplicable** — un texte vectorisé
n'est plus consultable ni modifiable comme du texte, et la seule voie de
suppression serait la reconstruction complète de l'index.

Exigence transmise à M2 et consignée dans le
[README du paquet d'ingestion](../src/m1_ingestion/README.md).

## 4. Droits des personnes

| Droit | Exerçable aujourd'hui | Condition de maintien |
|---|---|---|
| Information | Oui — le présent registre | Tenu à jour avec le code |
| Accès | Sans objet — aucune donnée réelle traitée | — |
| Rectification | Sans objet | — |
| **Effacement** | **Oui**, au niveau du pipeline | Suppression ciblée par `doc_id` dans l'index de M2 |
| Opposition | Sans objet | — |

Le droit à l'effacement est celui qui structure l'architecture. Il est
aujourd'hui satisfait par construction — les identités n'entrent pas — et le
restera tant que l'exigence portée à la fiche T-03 sera respectée.

## 5. Registre des écarts

| Réf | Écart | Gravité | Responsable | Échéance |
|---|---|---|---|---|
| E-01 | Détection par regex, pas par NER. La propagation des noms a fortement réduit l'écart, mais un nom qui n'est **jamais** ancré dans le document échappe encore au masquage | Moyenne *(était élevée)* | M8 | S4 |
| E-04 | Aucun journal d'audit des accès au corpus | Moyenne | M8 + M7 | S4 |
| E-06 | Chiffrement au repos du corpus non documenté | Faible | M8 + M1 | S4 |
| E-08 | M8 et M2 n'ont pas d'interface dans la matrice RACI, alors que M2 réalise l'opération après laquelle l'effacement devient impraticable | Faible | M8 | S4 |
| E-09 | `Dockerfile` et `docker-compose.yml` ne relèvent d'aucune règle `CODEOWNERS` de l'équipe `security` : image de base, utilisateur d'exécution, ports et secrets d'exécution échappent à la revue de conformité | Moyenne | M8 + M4 | S4 |

### Écarts résolus

| Réf | Écart | Résolution |
|---|---|---|
| E-R1 | Anonymisation implémentée mais jamais appelée : les données personnelles atteignaient `data/processed/` puis l'indexation | PR #16 |
| E-R2 | Règle CIN masquant montants, numéros de dossier, de registre et de Bulletin Officiel | PR #16 |
| E-R3 | `doc_id` et `title` dérivés du nom de fichier, propageant une identité jusque dans les citations | PR #16 |
| E-R4 | Aucune vérification automatisée du masquage | PR #16 — 13 tests exécutés en CI |
| E-R5 | Corpus accessible publiquement | Dépôt passé en privé le 27/08/2026 |
| E-R6 | Aucune analyse de sécurité du code Python ni des dépendances ; le scan de secrets, limité à une recherche textuelle, ne détecterait pas une clé d'API dépourvue de mot-clé | Bandit et pip-audit ajoutés à la CI, exécutés à chaque pull request |
| E-R7 | Durée de conservation non définie | Trois ans à compter de l'ingestion — décision d'équipe du 29/08/2026, motivée en [AIPD.md](AIPD.md) §6 |
| E-R8 | Origine des décisions de justice non arrêtée | Recueils publiés déjà pseudonymisés — décision d'équipe du 29/08/2026, §1 ci-dessus |
| E-R9 | Corpus hébergé sur un compte personnel hors organisation | Remote DVC migré vers `dagshub.com/CloudMind-Group` (PR #15). Le contrôle d'accès et la journalisation restent à configurer — voir E-04 |

## 6. Preuves

**Anonymisation** — exécution du pipeline sur un jugement de test, 27/08/2026.
Entrée :

```
Attendu que Monsieur Ahmed Benali, titulaire de la CIN AB123456, demeurant
Rue Al Massira a Rabat, joignable au 0612345678 et a l'adresse
a.benali@cabinet.ma, a saisi la Cour d'Appel de Casablanca ;
Attendu que le salarie Youssef Idrissi a temoigne a l'audience ;
Attendu que les pieces versees au dossier n 123456 etablissent l'absence de
procedure disciplinaire reguliere, conformement a l'article 62 du Code du
Travail et au dahir n 1-58-250 ;
Par ces motifs, la Cour declare le licenciement abusif et condamne
l'employeur au versement de 150000 dirhams.
```

Sortie — `6 PII masked` :

```
Attendu que [NOM], titulaire de la CIN [CIN], demeurant
[ADRESSE], joignable au 06******78 et a l'adresse
[EMAIL], a saisi la Cour d'Appel de Casablanca ;
Attendu que le salarie [NOM] a temoigne a l'audience ;
Attendu que les pieces versees au dossier n 123456 etablissent l'absence de
procedure disciplinaire reguliere, conformement a l'article 62 du Code du
Travail et au dahir n 1-58-250 ;
Par ces motifs, la Cour declare le licenciement abusif et condamne
l'employeur au versement de 150000 dirhams.
```

Le fichier source était nommé `arret_ahmed_benali_2024.txt` ; l'identifiant
produit est `jurisprudence-bb9d12fae65829c8` et le titre `Jurisprudence — 1900`.
Aucun élément du nom de fichier n'a été propagé.

La juridiction, le numéro de dossier, l'article, le dahir et le montant sont
intacts. La qualité de salarié survit à la suppression du nom.

**Propagation des noms** — mesure du 29/08/2026 sur un jugement représentatif
comportant seize occurrences de noms, chacune introduite une fois puis répétée
nue :

| | occurrences restantes | rappel |
|---|---|---|
| Règles ancrées seules | 8 sur 16 | 50 % |
| Avec propagation | **0 sur 16** | **100 %** |

Références préservées dans les deux cas : juridiction, numéro de dossier,
montant, article, et la dénomination sociale de la partie défenderesse — une
personne morale n'étant pas une donnée à caractère personnel.

Ce chiffre vaut pour ce document. Il ne se généralise pas : il dépend de ce que
chaque nom soit ancré au moins une fois quelque part dans le texte.

**Non-régression** — [`tests/test_anonymization.py`](../tests/test_anonymization.py),
21 tests exécutés à chaque pull request. Dix d'entre eux vérifient que montants,
numéros de dossier et de registre, articles, dahirs et juridictions **ne sont
pas** masqués. Un test consigne explicitement la limite subsistante : un nom
jamais ancré n'est pas détecté, et le jour où cela changera, ce test le dira.

**Absence de données personnelles dans le corpus actuel** — vérifiée sur les
gabarits de [`dataset_generator.py`](../src/m1_ingestion/dataset_generator.py).

**Visibilité du dépôt de données** — vérifiée le 27/08/2026 depuis une session
non authentifiée : le dépôt et son contenu ne sont pas accessibles
publiquement.

## 7. Révision

Ce registre est revu :

- à chaque modification du pipeline d'ingestion, du stockage ou de l'indexation ;
- **avant la première collecte d'un corpus réel** — révision bloquante ;
- à la revue de sécurité mensuelle (M8 et pilotes concernés).

L'analyse d'impact requise par ce traitement — données judiciaires de personnes
physiques, traitement automatisé, restitution à un public — s'appuie sur le
présent registre et fait l'objet d'un document distinct :
**[AIPD.md](AIPD.md)**.

Elle conclut que le traitement est proportionné à sa finalité, sous une réserve
bloquante : **l'ingestion d'un corpus judiciaire réel ne doit pas commencer
avant la résolution de l'écart E-01.** Les deux autres points de cette réserve
sont levés : E-07 par la décision du 29/08/2026 sur l'origine des sources, E-02
par la migration du corpus vers le compte de l'organisation.
