# Analyse d'impact relative à la protection des données (AIPD)

**Responsable :** Taha Kachmar — M8, Sécurité, Gouvernance & Conformité
**Version :** 1.0 — 27 août 2026
**Traitement analysé :** Assistant juridique augmenté par IA générative — ingestion, indexation et restitution de textes juridiques marocains
**Registre associé :** [`RGPD.md`](RGPD.md)

---

## 1. Pourquoi cette analyse est requise

Une AIPD s'impose lorsqu'un traitement est susceptible d'engendrer un risque
élevé pour les personnes. Trois critères sont réunis :

- **données judiciaires** relatives à des personnes physiques identifiées ;
- **traitement automatisé à grande échelle**, sans intervention humaine entre
  la collecte et la restitution ;
- **rediffusion à un public**, sous une forme — le moteur de réponse — distincte
  de la publication d'origine.

L'analyse s'appuie sur le registre des traitements et n'en reprend pas la
description. Elle porte sur les risques et sur ce qui les réduit.

## 2. Nécessité et proportionnalité

**Finalité.** Répondre à une question de droit en s'appuyant sur des sources
citées et vérifiables.

**Minimisation — point central.** Répondre à une question de droit ne requiert
jamais de savoir *qui* étaient les parties. La valeur juridique d'une décision
tient à la règle dégagée et au raisonnement suivi, non à l'identité des
justiciables. Les données personnelles présentes dans les jugements sont donc
**sans utilité pour la finalité poursuivie** : elles n'ont pas à entrer dans le
système.

C'est ce constat, et non une contrainte technique, qui justifie l'ensemble du
dispositif d'anonymisation. Il rend également la position défendable : la
mesure n'est pas « nous avons essayé de protéger », mais « ces données n'avaient
pas lieu d'être collectées ».

**Proportionnalité.** Le traitement conserve les juridictions, les dates, les
numéros d'articles et de dahirs, les montants et les qualités procédurales —
tout ce qui porte la valeur juridique — et écarte les identités. Le rapport
entre ce qui est traité et ce qui est nécessaire est donc favorable.

**Durée de conservation.** Non définie à ce jour. Voir écart E-03 du registre et
§6 ci-dessous.

## 3. Analyse des risques

Échelle employée pour la gravité et la vraisemblance : *négligeable, limitée,
importante, maximale*.

### R-01 — Divulgation de l'identité d'une partie dans une réponse

**Scénario.** Un utilisateur interroge l'assistant ; la réponse cite un extrait
de décision contenant le nom, la CIN ou l'adresse d'un justiciable. La personne
n'a jamais eu de relation avec le service et ignore que ses données y figurent.

**Impact.** Divulgation d'une situation judiciaire — licenciement, divorce,
litige — à un tiers quelconque, de façon indexable et répétable.

| | |
|---|---|
| Gravité | **Maximale** |
| Vraisemblance sans mesure | Maximale |
| Vraisemblance après mesures | Limitée |

**Mesures en place.** Anonymisation exécutée dans le pipeline, entre nettoyage
et écriture ; aucune donnée personnelle n'atteint `data/processed/` ni, par
conséquent, l'indexation. Les identifiants et titres ne dérivent pas du nom de
fichier. 13 tests de non-régression en CI.

**Propagation des noms.** Depuis le 29/08/2026, toute occurrence d'un nom déjà
identifié par une règle ancrée est masquée dans l'ensemble du document. C'est
la mesure qui traite le cas dominant : une partie est introduite une fois, puis
désignée nue pendant des pages. Mesuré sur un jugement représentatif, le rappel
passe de 50 % à 100 % (registre, §6).

**Risque résiduel.** Un nom qui n'apparaît **jamais** accompagné d'une civilité
ou d'une qualité procédurale n'amorce pas la propagation et échappe encore à la
détection (écart E-01). Le passage à un détecteur NER reste la mesure de
réduction prévue.

### R-02 — Effacement devenu techniquement impossible

**Scénario.** Une personne demande la suppression de ses données. Le texte a été
découpé et vectorisé par M2 ; il n'est plus consultable ni modifiable comme du
texte, et l'index ne permet pas de supprimer un document isolément.

**Impact.** Un droit garanti par la loi devient inexécutable. L'organisation
n'est pas en retard : elle est dans l'impossibilité de s'exécuter.

| | |
|---|---|
| Gravité | **Importante** |
| Vraisemblance sans mesure | Importante |
| Vraisemblance après mesures | Négligeable |

**Mesures.** Les identités n'entrent pas dans le système, ce qui vide la demande
de son objet dans la plupart des cas. Pour les cas résiduels, une exigence a été
transmise à M2 **avant le début de ses travaux** : l'index doit permettre la
suppression ciblée d'un `doc_id`.

**Point de vigilance.** Cette mesure n'a de valeur que si elle est intégrée dès
la conception de l'index. Rétrofitée, elle impose une reconstruction complète.

### R-03 — Perte du corpus ou perte de maîtrise

**Scénario.** Le corpus est hébergé sur le compte personnel d'un membre de
l'équipe. Fermeture du compte, départ, ou simple perte d'accès : `dvc.yaml` et
`dvc.lock` pointent dans le vide et le pipeline cesse d'être reproductible.

**Impact.** Sur les personnes, indirect : l'organisation ne peut plus démontrer
ce qu'elle a traité ni honorer une demande d'accès ou d'effacement. Sur le
projet, direct.

| | |
|---|---|
| Gravité | Limitée *(deviendra importante avec un corpus réel)* |
| Vraisemblance | Importante |

**Mesures.** Dépôt passé en privé le 27/08/2026. Migration vers le compte de
l'organisation à réaliser avant la première collecte réelle (écart E-02).

### R-04 — Accès non autorisé au corpus

**Scénario.** Toute personne disposant du lien et des identifiants accède à
l'intégralité du corpus. Aucun contrôle par rôle, aucun journal d'accès.

| | |
|---|---|
| Gravité | Importante |
| Vraisemblance | Limitée |

**Mesures.** Le dépôt est privé. Le contrôle d'accès par rôle et la
journalisation restent à mettre en place (écarts E-02, E-04). L'absence de
journal empêche aujourd'hui de répondre à « qui a consulté le corpus ».

### R-05 — Réponse juridique erronée présentée comme fiable

**Scénario.** L'assistant produit une réponse plausible mais fausse — article
inexistant, règle mal transposée, jurisprudence dépassée — et l'utilisateur agit
en conséquence : renonce à un recours, laisse expirer un délai.

**Impact.** Ce risque ne relève pas de la protection des données, mais il est le
plus probable et l'un des plus lourds pour la personne. Il est traité ici parce
que le même dispositif de garde-fous y répond.

| | |
|---|---|
| Gravité | **Importante** |
| Vraisemblance | Importante |

**Mesures prévues.** Obligation de citation, refus explicite hors périmètre,
mention systématique du caractère généré, clause de non-conseil (§5). La mesure
la plus efficace reste l'obligation de citation : une affirmation non sourcée
doit être refusée, non reformulée.

### R-06 — Ré-identification par recoupement

**Scénario.** Le masquage retire les identifiants directs, mais une décision
reste identifiable par recoupement : juridiction, date, employeur nommé,
montant, circonstances particulières.

**Impact.** Réidentification possible par une personne connaissant le contexte —
un employeur, un confrère.

| | |
|---|---|
| Gravité | Limitée |
| Vraisemblance | Importante |

**Mesures.** Aucune à ce jour. L'anonymisation traite les identifiants directs,
pas les quasi-identifiants. Réduire ce risque supposerait de dégrader les dates
ou les montants — au prix de la valeur juridique du corpus.

**Position retenue :** risque accepté et documenté. Un jugement rendu public
demeure identifiable par son contexte ; le service n'aggrave pas cette
situation dès lors qu'il ne restitue pas les identifiants directs. À réexaminer
si le corpus s'étend à des décisions non publiées.

### R-07 — Couverture inégale entre le français et l'arabe

**Scénario.** Les règles de détection sont plus fournies en français qu'en
arabe. Un jugement rédigé en arabe est donc moins bien anonymisé.

**Impact.** Protection différenciée selon la langue de la procédure.

| | |
|---|---|
| Gravité | Importante |
| Vraisemblance | Importante |

**Mesures.** Deux règles arabes couvrent les noms précédés d'un titre ou d'une
qualité. La propagation, elle, est **indépendante de la langue** : elle masque
les répétitions de tout nom déjà ancré, quel que soit l'alphabet. Elle réduit
donc l'écart sans le supprimer, puisque l'amorçage reste tributaire de règles
ancrées plus fournies en français.

La parité de couverture demeure un objectif du passage au NER (écart E-01), qui
devra être évalué séparément sur chaque langue — un détecteur performant en
français et muet en arabe reproduirait l'inégalité au lieu de la corriger.

### Synthèse

| Risque | Gravité | Vraisemblance résiduelle | Traité par |
|---|---|---|---|
| R-01 Divulgation d'identité | Maximale | Limitée | E-01 |
| R-02 Effacement impossible | Importante | Négligeable | exigence transmise à M2 |
| R-03 Perte de maîtrise | Limitée | Importante | E-02 |
| R-04 Accès non autorisé | Importante | Limitée | E-02, E-04 |
| R-05 Réponse erronée | Importante | Importante | §5 |
| R-06 Ré-identification | Limitée | Importante | accepté, documenté |
| R-07 Inégalité fr/ar | Importante | Importante | E-01 |

## 4. Classification au regard du règlement européen sur l'IA

Le règlement (UE) 2024/1689 est retenu comme cadre de référence : il constitue
l'état de l'art, et s'appliquerait si le service était ouvert à des résidents de
l'Union.

**La classification dépend d'une décision produit qui n'est pas prise.**

- **Utilisé par une autorité judiciaire, ou pour son compte**, afin de
  rechercher et d'interpréter les faits et le droit : le système relève de
  l'annexe III, point 8 — **haut risque**. S'ensuivent un système de gestion des
  risques, une documentation technique, une journalisation, un contrôle humain
  et une évaluation de conformité.
- **Utilisé par des professionnels du droit ou des particuliers** pour
  s'informer : le système ne relève pas de l'annexe III. Restent applicables les
  obligations de transparence de l'article 50 — informer clairement l'utilisateur
  qu'il interagit avec un système d'IA.

**Recommandation.** Trancher cet usage cible dès maintenant. La première branche
impose des obligations lourdes qui se conçoivent en amont et ne se rattrapent
pas en fin de projet. À défaut de décision explicite, se conformer par précaution
aux obligations de transparence et écarter formellement, dans la documentation
et les conditions d'usage, tout usage par une juridiction.

**Modèle de fondation.** Si l'assistant s'appuie sur un modèle généraliste
fourni par un tiers, les obligations correspondantes pèsent d'abord sur ce
fournisseur ; l'équipe reste tenue de documenter le modèle retenu, sa version et
ses limites — ce que couvre la *Model Card* prévue au module M3.

## 5. Garde-fous produit

À implémenter par M2 (prompts), M5 (API) et M6 (interface). M8 en définit le
contenu et en vérifie la présence.

**Obligation de citation.** Toute affirmation juridique doit renvoyer à une
source du corpus. En l'absence de source, la réponse attendue est un refus, pas
une reformulation. C'est la mesure la plus efficace contre R-05.

**Refus hors périmètre.** Toute question sortant du droit marocain couvert par
le corpus donne lieu à un refus explicite.

**Mention du caractère généré.** Visible à chaque réponse, non repliée dans les
conditions générales.

**Clause de non-conseil.** Texte proposé, à afficher à l'ouverture d'une session
et à rappeler en pied de chaque réponse :

> **Cet assistant ne délivre pas de conseil juridique.**
> Il restitue des extraits de textes de loi, de jurisprudence et de contrats
> types, accompagnés de leurs références, à des fins d'information. Les réponses
> sont générées automatiquement et peuvent être incomplètes, dépassées ou
> inexactes. Elles ne remplacent pas l'analyse d'un avocat ou d'un professionnel
> du droit habilité, seul à même d'apprécier une situation particulière.
> Vérifiez systématiquement les références citées avant toute décision.

**Aucune donnée personnelle dans les requêtes.** L'interface doit décourager la
saisie d'informations identifiantes par l'utilisateur. Le traitement des
documents déposés par les utilisateurs relève d'une fiche de traitement
distincte, à créer lorsque M5 et M6 implémenteront le dépôt.

## 6. Plan d'action

| Réf | Action | Réduit | Responsable | Échéance |
|---|---|---|---|---|
| A-1 | Remplacer les règles regex par un détecteur NER, évalué séparément en fr et en ar. La propagation des noms (29/08/2026) a réduit l'écart sans le fermer : reste le nom jamais ancré | R-01, R-07 | M8 | S4 |
| A-2 | Migrer le corpus vers le compte de l'organisation | R-03, R-04 | M8 + M1 | avant collecte réelle |
| A-3 | Arrêter l'usage cible au sens du règlement IA | §4 | M8 + équipe | S4 |
| A-4 | Définir la durée de conservation | proportionnalité | M8 | S4 |
| A-5 | Journal d'audit des accès au corpus et aux réponses | R-04 | M8 + M7 | S4 |
| A-6 | Intégrer les garde-fous du §5 aux prompts, à l'API et à l'interface | R-05 | M2, M5, M6 | S4 |
| A-7 | Confirmer par écrit auprès de M2 la suppression ciblée par `doc_id` | R-02 | M8 | avant le début de M2 |
| A-8 | Arrêter l'origine des décisions de justice | R-01 | M8 + M1 | avant collecte réelle |

**Décision requise — A-4.** La durée de conservation relève d'un arbitrage
d'équipe, non d'un choix technique. Deux options cohérentes avec la finalité :

- *conservation liée au corpus* — les textes sont conservés tant qu'ils sont en
  vigueur ou cités, avec réexamen annuel ;
- *durée fixe* — trois ans à compter de l'ingestion, avec réingestion des
  sources toujours pertinentes.

La seconde est plus simple à démontrer. Aucune n'est retenue à ce jour.

## 7. Avis

**Le traitement, tel qu'il est conçu à ce jour, est proportionné à sa finalité.**
Le risque principal — la divulgation de l'identité d'un justiciable — est traité
à la racine : les données n'entrent pas dans le système, plutôt que d'être
masquées à l'affichage.

**Deux réserves conditionnent cet avis.**

La première : l'analyse porte sur un corpus **entièrement synthétique**. Aucune
donnée personnelle réelle n'a été traitée à ce jour. Les mesures décrites sont en
place, mais n'ont jamais été confrontées à un texte judiciaire authentique.

La seconde : le rappel du dispositif de détection est **insuffisant pour un
corpus réel** (A-1). Un nom dépourvu de civilité ou de qualité procédurale
échappe encore au masquage.

**En conséquence : l'ingestion d'un corpus judiciaire réel ne doit pas commencer
avant la réalisation de A-1, A-2 et A-8.** Cette réserve est le seul point
bloquant de la présente analyse.

## 8. Révision

Cette analyse est révisée à chaque évolution du traitement, et
**obligatoirement** :

- avant la première ingestion d'un corpus judiciaire réel ;
- avant toute ouverture du service à des utilisateurs externes ;
- si l'usage cible au sens du règlement IA est modifié.
