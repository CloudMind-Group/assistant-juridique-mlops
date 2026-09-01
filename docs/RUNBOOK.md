# Procédure de réponse à incident — M7

Livrable 3 du module M7, avec les règles d'alerte de
[`monitoring/prometheus/rules/alerts.yml`](../monitoring/prometheus/rules/alerts.yml).

Chaque alerte porte une annotation `runbook` qui pointe vers la section
correspondante de ce document. Une alerte sans procédure écrite est une alerte
qui sera ignorée : si vous ajoutez une règle, ajoutez sa section ici dans la
même pull request.

---

## 1. Niveaux de gravité

| Niveau | Signification | Délai de prise en charge | Canal |
|---|---|---|---|
| `critical` | Service indisponible ou fortement dégradé pour tous | Immédiat | `#cloudmind-astreinte` + courriel |
| `warning` | Dégradation visible, service utilisable | Heures ouvrées | `#cloudmind-alertes` |

Une alerte `warning` qui persiste plus de vingt-quatre heures doit être soit
traitée, soit fermée avec une justification écrite. Une alerte que l'on
apprend à ignorer a un coût supérieur à son absence.

## 2. Réflexe commun — les cinq premières minutes

1. **Confirmer** que l'alerte reflète la réalité : ouvrir le tableau de bord
   *M7 · API & chaîne RAG* dans Grafana. Une alerte isolée sans effet visible
   sur le débit est probablement un défaut de règle, pas un incident.
2. **Dater** le début : comparer avec la dernière livraison via `app_info`.
   Une dégradation qui commence à l'horodatage d'un déploiement est un
   problème de déploiement jusqu'à preuve du contraire.
3. **Circonscrire** : une seule route, un seul modèle, ou tout le service ?
   Le tableau de bord répond en deux panneaux.
4. **Décider** : atténuer d'abord, comprendre ensuite. Un retour à la version
   précédente est toujours préférable à un diagnostic sous pression.
5. **Écrire** : noter l'heure et les actions dans le fil de l'alerte. Sans
   trace, le post-mortem n'aura rien à analyser.

---

## 3. Procédures par alerte

### CibleInjoignable

**Sens.** Prometheus ne parvient plus à collecter l'API depuis une minute.
C'est le seul cas où le silence des autres alertes n'est pas rassurant : sans
collecte, plus rien ne peut se déclencher.

**À vérifier, dans l'ordre.**
1. Le service répond-il ? `curl -sf http://<api>/v1/health`
2. Le conteneur tourne-t-il ? Sinon, chercher la cause du redémarrage côté M4.
3. L'endpoint `/metrics` est-il exposé ? Une régression fréquente est un
   changement de port ou l'oubli de l'intergiciel d'instrumentation.
4. Un pare-feu ou une règle réseau a-t-il changé ?

**Atténuation.** Redémarrer le service. S'il redémarre en boucle, revenir à la
version précédente sans chercher davantage.

**Escalade.** M4 (Salma) si l'infrastructure est en cause, M5 (Nouhaila) si le
service démarre mais n'expose plus ses métriques.

---

### TauxErreurEleve · TauxErreurCritique

**Sens.** Plus de 1 % (respectivement 5 %) des requêtes retournent un code 5xx.

**À vérifier.**
1. Les erreurs sont-elles concentrées sur une route ? Panneau *Requêtes par
   code de statut*, puis *Latence par route*.
2. Coïncident-elles avec un déploiement ? Comparer avec `app_info`.
3. `llm_requests_failed_total` augmente-t-il en parallèle ? Si oui, la cause
   est en aval : modèle, quota, ou délai d'attente dépassé.
4. Sinon, chercher dans Loki : `{job="audit"} | json | outcome="error"`.

**Atténuation.** Si l'incident suit une livraison, revenir en arrière. Si la
cause est un quota de modèle, réduire temporairement le débit accepté.

**Escalade.** M5 (Nouhaila) pour l'API, M2 (Imane) si les échecs viennent de
la chaîne d'inférence.

---

### LatenceApiDegradee

**Sens.** Le P95 dépasse l'objectif de 2,5 s pendant dix minutes.

**À vérifier.**
1. Décomposer : la latence vient-elle de la récupération
   (`rag_retrieval_duration_seconds`) ou de la génération
   (`llm_request_duration_seconds`) ? Le tableau de bord sépare les deux.
2. Le taux de cache a-t-il chuté ? Un cache qui s'effondre déplace la charge
   sur le modèle et allonge mécaniquement la latence.
3. Le nombre de passages remontés a-t-il augmenté ? Un `top_k` modifié coûte
   directement en temps de génération.

**Atténuation.** Rétablir le `top_k` antérieur, ou réchauffer le cache. Si la
génération est en cause et qu'aucune régression n'est identifiée, réduire la
longueur maximale de réponse est la mesure la plus rapide.

**Escalade.** M2 (Imane) pour la récupération et la génération, M5 (Nouhaila)
pour le cache.

---

### RetrieverLent

**Sens.** Le P50 de la récupération dépasse 120 ms.

**À vérifier.** Taille de l'index, présence de filtres coûteux, ré-indexation
en cours. Une ré-indexation dégrade la latence de façon attendue : dans ce
cas, taire l'alerte pendant l'opération plutôt que la subir.

**Escalade.** M2 (Imane).

---

### EchecsModele

**Sens.** Plus de 0,1 échec par seconde sur cinq minutes.

**À vérifier.** L'étiquette `reason` donne directement la cause :
`timeout` (modèle saturé ou prompt trop long), `rate_limit` (quota),
`invalid_response` (format de sortie modifié — souvent un changement de
version du modèle non annoncé).

**Escalade.** M2 (Imane).

---

### ConsommationJetonsAnormale

**Sens.** La consommation a doublé par rapport à la même fenêtre la veille.

C'est la seule alerte qui ne signale pas une panne mais un coût. Aucun test ne
la détecte : seule la supervision la voit.

**À vérifier.** Une boucle de relance, un prompt système rallongé, un
changement de `top_k` qui gonfle le contexte, ou un trafic légitimement en
hausse — vérifier `http_requests_total` avant de conclure à une anomalie.

**Escalade.** M2 (Imane) pour le prompt, M7 (Youssef) si la métrique
elle-même est suspecte.

---

### CacheInefficace

**Sens.** Le taux de succès du cache est sous 35 % depuis trente minutes.

**À vérifier.** Redis répond-il ? La clé de cache a-t-elle changé de forme
(une modification du calcul d'empreinte invalide tout le cache d'un coup) ?
La durée de vie a-t-elle été réduite ?

**Escalade.** M5 (Nouhaila).

---

## 4. Après l'incident

Tout incident `critical` donne lieu à une note de cinq lignes au maximum,
publiée dans une issue étiquetée `incident` :

- ce qui s'est passé, en une phrase ;
- la fenêtre horaire exacte ;
- la cause identifiée, ou l'aveu qu'elle ne l'est pas ;
- ce qui a rétabli le service ;
- l'action qui empêchera la récurrence, avec un responsable nommé.

Aucune recherche de responsabilité individuelle. Un incident qui se reproduit
à l'identique signale un défaut de procédure, pas un défaut de personne.

## 5. Limites connues de cette procédure

- Les alertes ne sont pas encore branchées sur un service réel : elles sont
  vérifiées contre le simulateur de M7 tant que M5 n'expose pas `/metrics`.
- Il n'existe pas de rotation d'astreinte formelle. En l'état, toute alerte
  `critical` est traitée par M7 (Youssef), avec escalade vers le pilote du
  module concerné.
- Les tableaux de bord d'infrastructure sont absents tant que M4 n'a pas
  déployé la pile : l'axe « ressources » du diagnostic est donc aveugle.
