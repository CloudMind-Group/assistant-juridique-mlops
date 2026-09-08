# Documentation — Assistant Juridique Intelligent

Assistant conversationnel de recherche juridique marocaine, construit par
**CloudMind Group** : huit modules MLOps, huit ingénieurs, un mois de
réalisation.

Ce site rassemble la documentation technique et de conformité du projet. Il est
construit à partir des fichiers du dépôt : ce qui est lu ici est ce qui est
versionné, sans copie intermédiaire susceptible de diverger.

---

## Par où commencer

| Vous cherchez | Allez à |
|---|---|
| Comment le système est construit | [Architecture](ARCHITECTURE.md) |
| Qui fait quoi, et de qui dépend quoi | [Équipe et matrice RACI](TEAM.md) |
| Comment contribuer sans casser la chaîne | [Gouvernance GitHub](GITHUB.md) |
| Ce que le projet fait des données personnelles | [Registre des traitements](RGPD.md) |
| Les risques identifiés et ce qui les traite | [Analyse d'impact](AIPD.md) |
| Qui a le droit de lire quoi | [Matrice des habilitations](HABILITATIONS.md) |

## Les documents de conformité

Trois documents forment le dispositif, et ils se lisent dans cet ordre.

Le **[registre des traitements](RGPD.md)** décrit ce qui est fait des données :
d'où elles viennent, ce qu'on en retire, combien de temps on les garde, et qui
peut y accéder. Il porte aussi le **registre des écarts** — la liste de ce qui
n'est pas encore conforme, avec pour chaque ligne la mesure prévue et son
échéance. Cette seconde liste est la plus utile des deux : un registre qui ne
déclarerait que ses réussites ne serait pas un registre.

L'**[analyse d'impact](AIPD.md)** examine les risques que le traitement fait
peser sur les personnes, et non sur le projet. Elle porte la classification du
système au regard du règlement européen sur l'intelligence artificielle, et la
raison pour laquelle l'usage judiciaire en est formellement exclu.

La **[matrice des habilitations](HABILITATIONS.md)** répond à une seule
question : qui peut lire quoi, et sous quelle condition. Elle sert de référence
au contrôle d'accès de l'API et au cloisonnement entre cabinets.

!!! note "Une convention de lecture"

    Ces documents décrivent l'état réel, pas l'état souhaité. Quand une mesure
    est écrite mais pas implémentée, le texte le dit. Quand une affirmation
    s'est révélée fausse, elle est corrigée par une note datée plutôt que
    réécrite en silence — une vérité corrigée sans trace est une vérité qu'on
    ne peut plus auditer.

## Les contrats entre modules

Un module qui en consomme un autre dépend d'une forme, pas d'une implémentation.
Ces contrats fixent la forme.

- **[Observabilité](OBSERVABILITE.md)** — les métriques attendues du service, et
  le journal d'audit : ses champs, ce qui n'y figure jamais, et pourquoi les
  identifiants y sont protégés par HMAC plutôt que par un condensé simple.
- **[Réponse à incident](RUNBOOK.md)** — la procédure quand la production
  dysfonctionne.
- **[Suivi des expérimentations](M3.md)** — le registre de modèles et la
  politique de promotion.

## Ce qui n'est pas ici

Le **[README](https://github.com/CloudMind-Group/assistant-juridique-mlops#readme)**
et la **[politique de sécurité](https://github.com/CloudMind-Group/assistant-juridique-mlops/blob/develop/SECURITY.md)**
vivent à la racine du dépôt, où GitHub les attend : la seconde alimente l'onglet
*Security* et le formulaire de signalement de vulnérabilité, qui cesseraient de
fonctionner si le fichier était déplacé ici.

Les modules documentent leur contrat de sortie dans leur propre `README` — voir
[`src/m1_ingestion/`](https://github.com/CloudMind-Group/assistant-juridique-mlops/tree/develop/src/m1_ingestion)
et [`src/m2_rag/`](https://github.com/CloudMind-Group/assistant-juridique-mlops/tree/develop/src/m2_rag).

---

!!! warning "Aucune donnée réelle"

    Le corpus en circulation est **intégralement synthétique**. Le dépôt
    n'accepte ni document juridique réel, ni donnée personnelle, ni identifiant
    — y compris dans les tickets, les demandes de fusion et les captures
    d'écran. Voir la
    [politique de sécurité](https://github.com/CloudMind-Group/assistant-juridique-mlops/blob/develop/SECURITY.md).
