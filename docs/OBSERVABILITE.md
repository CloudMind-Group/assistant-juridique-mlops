# Contrats d'observabilité — M7

Document de référence du module **M7 — Model Monitoring & Observability**.

Il définit deux interfaces, **avant** que les producteurs existent, pour qu'aucune des deux
n'ait à être réécrite ensuite :

| Contrat | Sens | Partie prenante |
|---|---|---|
| **Métriques** | M5 → M7 | Nouhaila expose, Youssef consomme |
| **Journal d'audit** | M7 → M8 | Youssef produit, Taha audite |

Le second met en œuvre l'action **A-5** de [`AIPD.md`](AIPD.md) (*journal d'audit des accès au
corpus et aux réponses*, portée conjointe M8 + M7) et applique la décision **A-4** (durée de
conservation fixée à trois ans).

---

## 1. Contrat de métriques — M5 → M7

### 1.1 Exposition

- **Endpoint :** `GET /metrics`, format d'exposition Prometheus (texte).
- **Accès :** non exposé publiquement — collecté par Prometheus sur le réseau interne.
  Sur Kubernetes, la découverte se fait par annotation de service (M4).
- **Fréquence de collecte :** 15 s.

### 1.2 Conventions imposées

- Unités de base SI : durées en **secondes**, tailles en **octets**. Jamais de millisecondes
  dans un nom de métrique.
- Suffixe `_total` pour tout compteur, `_seconds` pour toute durée.
- **Cardinalité :** aucun label ne doit contenir un identifiant d'utilisateur, un identifiant de
  session, ou le texte d'une question. Le label `route` porte le **gabarit** (`/v1/ask`) et non
  le chemin concret. Une seule violation de cette règle suffit à faire exploser la base de
  séries temporelles.

### 1.3 Métriques attendues

| Nom | Type | Labels | Ce qu'elle permet |
|---|---|---|---|
| `http_requests_total` | counter | `method`, `route`, `status` | Débit, taux d'erreur |
| `http_request_duration_seconds` | histogram | `method`, `route` | Latence API (SLO P95 < 2,5 s) |
| `rag_retrieval_duration_seconds` | histogram | — | Latence du retriever (SLO P50 < 120 ms) |
| `rag_documents_retrieved` | histogram | — | Nombre de passages remontés par requête |
| `llm_request_duration_seconds` | histogram | `model` | Latence de génération |
| `llm_tokens_total` | counter | `model`, `type` (`prompt`\|`completion`) | Consommation et coût |
| `llm_requests_failed_total` | counter | `model`, `reason` | Échecs côté modèle |
| `cache_lookups_total` | counter | `result` (`hit`\|`miss`) | Efficacité du cache Redis (cible ≥ 35 %) |
| `app_info` | gauge (=1) | `version`, `commit` | Corréler un incident à une version déployée |

### 1.4 Intervalles d'histogramme recommandés

Calés sur les objectifs publiés dans [`ARCHITECTURE.md`](ARCHITECTURE.md) — un intervalle doit
encadrer la cible, sinon le quantile calculé est inexploitable.

```python
HTTP_BUCKETS      = (0.1, 0.25, 0.5, 1, 2, 2.5, 5, 10)      # cible P95 = 2,5 s
RETRIEVAL_BUCKETS = (0.01, 0.05, 0.1, 0.12, 0.25, 0.5, 1)   # cible P50 = 120 ms
```

### 1.5 Grandeurs dérivées — calculées par M7, pas par M5

M5 n'a **aucun taux ni pourcentage à calculer**. Elle expose des compteurs bruts ; les ratios
sont dérivés côté Prometheus :

```promql
# taux d'erreur serveur
sum(rate(http_requests_total{status=~"5.."}[5m]))
  / sum(rate(http_requests_total[5m]))

# latence P95 par route
histogram_quantile(0.95,
  sum by (le, route) (rate(http_request_duration_seconds_bucket[5m])))
```

### 1.6 Mise en œuvre côté M5

Le strict nécessaire, sans dépendance lourde :

```python
# requirements : prometheus-client
from prometheus_client import Counter, Histogram, make_asgi_app

app.mount("/metrics", make_asgi_app())
```

Une instrumentation automatique des routes HTTP est possible via
`prometheus-fastapi-instrumentator` ; les métriques `rag_*` et `llm_*` restent à déclarer à la
main, elles sont spécifiques au domaine.

---

## 2. Contrat de journal d'audit — M7 → M8

### 2.1 Forme et conservation

| Propriété | Valeur |
|---|---|
| Format | JSON Lines — un événement par ligne, UTF-8 |
| Transport | Promtail → Loki |
| Mutabilité | **Ajout seul.** Aucune API de modification ni de suppression unitaire |
| Conservation | **3 ans** à compter de l'écriture — décision A-4 |
| Horodatage | RFC 3339, UTC, systématiquement |

### 2.2 Champs

| Champ | Type | Requis | Description |
|---|---|:--:|---|
| `ts` | string | oui | Horodatage RFC 3339 en UTC |
| `event_id` | uuid | oui | Identifiant unique de l'événement |
| `event_type` | enum | oui | Voir §2.4 |
| `actor_id` | string | oui | **Pseudonyme stable** (empreinte), jamais un nom ni un e-mail |
| `actor_role` | string | oui | Rôle applicatif au moment de l'action |
| `resource_ids` | string[] | selon | `doc_id` des documents consultés |
| `query_hash` | string | selon | SHA-256 de la question normalisée — **jamais la question** |
| `answer_id` | uuid | selon | Identifiant de la réponse produite |
| `sources_cited` | string[] | selon | `doc_id` effectivement cités dans la réponse |
| `model` | string | selon | Modèle ayant produit la réponse |
| `duration_ms` | integer | non | Durée de traitement |
| `outcome` | enum | oui | `success` \| `error` |
| `error_code` | string | selon | Renseigné si `outcome = error` |
| `trace_id` | string | non | Corrélation avec la trace OpenTelemetry |

### 2.3 Ce qui ne doit jamais être journalisé

Interdictions fermes — leur violation transformerait le journal d'audit lui-même en un second
traitement de données personnelles, alors qu'il existe précisément pour en attester la maîtrise :

- le **texte brut** d'une question ou d'une réponse ;
- toute donnée personnelle extraite d'un document (risque **R-01** de l'AIPD) ;
- une **adresse IP brute** (risque **R-04**) ;
- un jeton d'authentification, même expiré.

L'exigence d'A-5 — pouvoir auditer les accès au corpus et aux réponses — est satisfaite par des
**identifiants et des empreintes**. Deux consultations identiques produisent le même `query_hash`,
ce qui suffit à détecter un usage anormal sans conserver la moindre phrase.

### 2.4 Événements minimaux

| `event_type` | Déclencheur |
|---|---|
| `auth.login` | Ouverture de session |
| `auth.denied` | Accès refusé |
| `corpus.read` | Lecture d'un ou plusieurs documents du corpus |
| `answer.generated` | Réponse produite et servie |
| `answer.exported` | Réponse exportée ou copiée hors du système |

### 2.5 Exemple

```json
{"ts":"2026-08-30T09:14:22Z","event_id":"3f2b…","event_type":"answer.generated",
 "actor_id":"u_9c41…","actor_role":"juriste","query_hash":"a4d1…",
 "answer_id":"7e08…","sources_cited":["BO-2019-4821","JUR-2021-0093"],
 "model":"legal-fr-v2","duration_ms":1840,"outcome":"success","trace_id":"b7c2…"}
```

---

## 3. Ce que M7 fournit en contrepartie

Les deux contrats sont des demandes ; voici ce qui est livré en face, sans effort
supplémentaire pour M5 ni pour M8 :

- pile d'observabilité **Prometheus + Grafana + Loki + Alertmanager** prête à démarrer ;
- tableaux de bord Grafana préconfigurés sur les métriques du §1.3 ;
- règles d'alerte et procédure de réponse à incident ;
- politique de conservation Loki alignée sur la décision A-4.

---

## 4. État

| Élément | Dépend de | État |
|---|---|---|
| Contrat de métriques | — | **Défini** — en attente d'implémentation par M5 |
| Contrat de journal d'audit | décision A-4 | **Défini** — clôt l'action A-5 côté M7 |
| Pile d'observabilité locale | — | À construire |
| Instrumentation réelle | M5 | Bloqué |
| Détection de dérive (Evidently) | M2 + M5 | Bloqué |

Toute évolution de l'un de ces deux contrats doit être discutée avec la partie prenante
concernée **avant** d'être fusionnée : ce sont des interfaces, pas de la documentation.
