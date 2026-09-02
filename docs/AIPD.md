# Analyse d'impact relative à la protection des données (AIPD)

**Responsable :** Taha Kachmar — M8, Sécurité, Gouvernance & Conformité
**Version :** 1.2 — 30 août 2026
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

**Durée de conservation.** **Trois ans à compter de l'ingestion** (décision A-4,
29 août 2026), avec réingestion des sources toujours pertinentes au terme.
L'option retenue est la plus simple à démontrer face à un contrôle : une date
d'ingestion et une règle fixe suffisent, là où une conservation liée à la
validité des textes aurait supposé de suivre l'état d'abrogation de chaque
source. Elle impose en contrepartie une réingestion périodique, dont
l'automatisation revient au pipeline de M1.

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
fichier. 32 tests de non-régression en CI.

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
de son objet dans la plupart des cas. Pour les cas résiduels, une exigence avait
été transmise à M2 **avant le début de ses travaux** : l'index doit permettre la
suppression ciblée d'un `doc_id`.

**Exigence satisfaite — vérifié le 02/09/2026.** `vector_store.delete_document(doc_id)`
existe sur l'interface et dans les deux implémentations, avec un filtre sur le
champ, et il est testé (PR #28). L'effacement est donc une opération réelle et
non un droit théorique.

C'est la seule mesure de cette analyse qui aurait été **impossible à rattraper
après coup** : un index construit sans cette capacité ne se corrige pas, il se
reconstruit. Elle illustre à elle seule pourquoi l'AIPD se rédige avant le
traitement et non après — l'exigence a été posée alors que M2 n'avait pas écrit
une ligne, et elle n'a rien coûté à intégrer.

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
| Vraisemblance sans mesure | Importante |
| Vraisemblance après mesures | Négligeable |

**Mesures.** Dépôt passé en privé le 27/08/2026, puis **remote DVC migré vers le
compte de l'organisation** le 29/08/2026 (PR #15). L'accès au corpus ne dépend
plus d'une personne, et son administration revient à l'organisation. A-2 close.

### R-04 — Accès non autorisé au corpus

**Scénario.** Toute personne disposant du lien et des identifiants accède à
l'intégralité du corpus. Aucun contrôle par rôle, aucun journal d'accès.

| | |
|---|---|
| Gravité | Importante |
| Vraisemblance | Limitée |

**Mesures.** Le dépôt est privé et hébergé par l'organisation, ce qui rend le
contrôle d'accès exerçable. Il n'est pas configuré pour autant, et la
journalisation a désormais un contrat arrêté ([`OBSERVABILITE.md`](OBSERVABILITE.md)
§2) mais aucune source d'événements — M5 n'existe pas (écart E-04) : l'absence de journal
empêche aujourd'hui de répondre à « qui a consulté le corpus ».

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
qualité, et la propagation opère désormais dans les deux écritures.

> **Correction — 30 août 2026.** Une version antérieure de cette analyse
> affirmait que la propagation était « indépendante de la langue ». **C'était
> faux**, et l'affirmation n'avait pas été vérifiée par l'exécution : l'extracteur
> de jetons exigeait une majuscule latine initiale, or l'arabe n'a pas de casse.
> La propagation ne produisait donc **aucun** jeton sur un nom arabe. Un test
> sur cinq formulations arabes donnait 2 réussites ; la mesure annoncée n'existait
> pas dans cette écriture.

L'écart était en réalité double, et dans les deux sens :

| | avant correction | après |
|---|---|---|
| Répétition d'un nom déjà ancré (ar) | non masquée | masquée |
| Verbe suivant le nom (ar) | **détruit** | préservé |
| Formulations arabes du banc de test | 2 / 5 | 4 / 5 |

Le second point était le plus grave : faute de majuscule pour marquer la fin
d'un nom propre, la règle arabe comptait les mots et emportait le verbe —
« تقدم », « حضر », « أدلى » — c'est-à-dire l'acte même que la décision constate.
Une liste de mots-outils et de verbes de procédure lui sert désormais de borne.

**Sur-masquage — issue #31.** Le 2 septembre, M1 a signalé que des termes
juridiques arabes (« المشغل », « الطالب ») étaient traités comme des indices
d'identité, ce qui masquait la suite de la phrase. Reproduit sur six
formulations, dont une reprise mot pour mot du générateur de corpus : le défaut
touchait donc le corpus présent dans le dépôt. Les qualités procédurales
n'ancrent plus un nom à elles seules en arabe ; il faut un titre, un
deux-points ou les deux. C'est un arbitrage de précision contre rappel, motivé
au registre.

**Risque résiduel.** Il reste celui de la langue française : un nom jamais ancré
n'amorce rien. Et en arabe, celui du nom qui n'apparaît qu'après une qualité nue. La parité de couverture demeure un objectif du passage au NER
(écart E-01), qui devra être **évalué séparément sur chaque langue** — un
détecteur performant en français et muet en arabe reproduirait l'inégalité au
lieu de la corriger, ce qui est précisément la raison du rejet de Presidio.

### Synthèse

| Risque | Gravité | Vraisemblance résiduelle | Traité par |
|---|---|---|---|
| R-01 Divulgation d'identité | Maximale | Limitée | E-01 |
| R-02 Effacement impossible | Importante | Négligeable | exigence transmise à M2 |
| R-03 Perte de maîtrise | Limitée | Négligeable | migration du corpus — close |
| R-04 Accès non autorisé | Importante | Limitée | E-04 |
| R-05 Réponse erronée | Importante | Importante | §5 |
| R-06 Ré-identification | Limitée | Importante | accepté, documenté |
| R-07 Inégalité fr/ar | Importante | Importante | E-01 |

## 4. Classification au regard du règlement européen sur l'IA

Le règlement (UE) 2024/1689 est retenu comme cadre de référence : il constitue
l'état de l'art, et s'appliquerait si le service était ouvert à des résidents de
l'Union.

> **Décision A-3 — usage cible arrêté le 29 août 2026.**
> Le système s'adresse aux **professionnels du droit et aux particuliers**
> cherchant à s'informer. **Tout usage par une juridiction, ou pour le compte
> d'une juridiction, est formellement écarté.**
> Soumise à l'équipe avec un délai d'objection de 24 h ; aucune objection reçue.

Deux qualifications étaient possibles, et l'écart entre elles est considérable :

- **utilisé par une autorité judiciaire, ou pour son compte**, afin de
  rechercher et d'interpréter les faits et le droit : le système relèverait de
  l'annexe III, point 8 — **haut risque**. S'ensuivraient un système de gestion
  des risques, une documentation technique, une journalisation, un contrôle
  humain et une évaluation de conformité ;
- **utilisé par des professionnels du droit ou des particuliers** pour
  s'informer : le système ne relève pas de l'annexe III.

**Motivation.** La finalité inscrite au registre est d'informer, non d'assister
une décision de justice. Retenir la première branche aurait imposé des
obligations qui se conçoivent en amont et ne se rattrapent pas — les assumer
sans les avoir prévues aurait été une conformité de façade. La seconde branche
correspond à ce que le produit fait réellement.

**Conséquences.**

Le système reste soumis aux **obligations de transparence de l'article 50** :
l'utilisateur doit savoir clairement qu'il interagit avec une IA. Elles sont
couvertes par les garde-fous du §5 — mention du caractère généré et clause de
non-conseil — dont l'implémentation incombe à M6.

L'exclusion doit être **opposable, pas seulement documentée**. À porter dans les
conditions d'usage du service ainsi que dans la clause de non-conseil, qui
renvoie déjà à un professionnel habilité pour toute situation particulière.

Cette décision devient caduque si le produit est un jour proposé à une
juridiction : la qualification bascule alors en haut risque et la présente
analyse doit être reprise (§8).

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
| A-5 | Journal d'audit des accès au corpus et aux réponses. Contrat arrêté par M7 (`OBSERVABILITE.md` §2) ; reste la source d'événements | R-04 | M8 + M5 | avant ouverture du service |
| A-6 | Intégrer les garde-fous du §5 aux prompts, à l'API et à l'interface | R-05 | M2, M5, M6 | S4 |

### Actions closes

Les trois arbitrages qui ne relevaient pas de M8 seul ont été soumis à l'équipe
avec un délai d'objection de 24 h. Aucune objection n'a été reçue ; ils sont
consignés ici pour que la décision vive dans le dépôt et non dans une
conversation.

| Réf | Décision arrêtée le 29/08/2026 | Consignée en |
|---|---|---|
| A-3 | Usage cible : professionnels du droit et particuliers. Usage juridictionnel formellement écarté | §4 |
| A-4 | Conservation : trois ans à compter de l'ingestion, avec réingestion des sources pertinentes | §2 |
| A-8 | Origine des décisions : recueils publiés dont l'identification a déjà été retirée à la publication | §2, et fiche T-01 du registre |

Une quatrième action est close depuis, par une contribution de M1 :

| Réf | Réalisation | Effet |
|---|---|---|
| A-2 | Remote DVC migré vers `dagshub.com/CloudMind-Group` (PR #15, 29/08/2026) | R-03 et R-04 réduits : l'accès au corpus ne dépend plus d'une personne. Le contrôle d'accès et la journalisation restent à configurer (A-5) |
| A-7 | Suppression ciblée par `doc_id` implémentée et testée par M2 (PR #28, vérifié le 02/09/2026) | R-02 ramené à une vraisemblance négligeable. L'exigence avait été transmise avant que M2 ne commence — c'est ce qui l'a rendue gratuite |

**Portée de A-8 sur l'analyse.** C'est l'arbitrage qui change le plus la charge
de M8. Un recueil déjà pseudonymisé réduit fortement le volume de données
personnelles entrant, et fait de l'anonymisation du pipeline une **seconde
barrière** plutôt que l'unique. Deux précisions s'imposent néanmoins :

- la pseudonymisation à la publication **n'est pas garantie exhaustive** : les
  noms subsistent fréquemment dans le corps des motifs, même lorsque l'en-tête
  a été traité. Le dispositif du pipeline reste donc nécessaire, et A-1 conserve
  sa priorité ;
- toute source **hors de ce périmètre** — pièces brutes, archives de cabinet,
  décisions non publiées — sort du cadre de la présente analyse et impose sa
  révision préalable (§8).

Cette décision lève A-8 comme point bloquant, sans lever A-1 ni A-2.

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
avant la réalisation de A-1.** C'est désormais le seul point bloquant de la
présente analyse.

Les deux autres réserves initiales sont levées. **A-2** l'est par la migration
du corpus vers le compte de l'organisation (PR #15). **A-8** l'est par la
décision du 29/08/2026 : les sources retenues sont des recueils publiés déjà
pseudonymisés — ce qui réduit le volume de données personnelles entrant sans
dispenser du dispositif du pipeline, la pseudonymisation à la publication
n'étant pas exhaustive dans le corps des motifs.

Le rappel de la détection reste donc la dernière condition à lever.

## 8. Révision

Cette analyse est révisée à chaque évolution du traitement, et
**obligatoirement** :

- avant la première ingestion d'un corpus judiciaire réel ;
- avant toute ouverture du service à des utilisateurs externes ;
- si l'usage cible au sens du règlement IA est modifié.
