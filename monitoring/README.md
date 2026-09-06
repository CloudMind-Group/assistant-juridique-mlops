# Pile d'observabilité — M7

Mise en œuvre du module **M7 — Model Monitoring & Observability**.
Les interfaces avec les autres modules sont spécifiées dans
[`docs/OBSERVABILITE.md`](../docs/OBSERVABILITE.md) ; la conduite à tenir en
cas d'alerte dans [`docs/RUNBOOK.md`](../docs/RUNBOOK.md).

## Démarrage

```bash
# 1. Créer les fichiers de secrets, jamais versionnés
mkdir -p monitoring/alertmanager/secrets
echo "https://hooks.slack.com/services/REMPLACER" > monitoring/alertmanager/secrets/slack_url
echo "REMPLACER" > monitoring/alertmanager/secrets/smtp_password

# 2. Définir les identifiants Grafana — obligatoires, sans valeur par défaut
export GRAFANA_USER=admin
export GRAFANA_PASSWORD="un-mot-de-passe-choisi"

# 3. Démarrer la pile
docker compose -f monitoring/docker-compose.yml up -d
```

> **Pourquoi aucune valeur par défaut pour Grafana.** Un défaut `admin`/`admin` fait
> démarrer l'instance avec des identifiants publiquement connus, et l'accès
> administrateur ouvre les sources de données — donc Loki, donc le journal d'audit.
> Un défaut d'authentification qui passe inaperçu est plus dangereux qu'une
> configuration absente qui empêche le démarrage : la pile refuse ici de monter tant
> que les deux variables ne sont pas fournies.
>
> **Tous les ports sont liés à `127.0.0.1`.** Sans adresse explicite, Docker publie sur
> `0.0.0.0` ; or Prometheus et Alertmanager n'ont aucune authentification native. Sur un
> réseau partagé, n'importe quel poste du même segment pourrait interroger l'API Loki et
> les cibles Prometheus. Le jour où M4 déploiera la pile, l'exposition redeviendra un
> choix explicite plutôt qu'un héritage.

| Service | Adresse | Rôle |
|---|---|---|
| Grafana | http://localhost:3000 | Tableaux de bord (identifiants définis par `GRAFANA_USER` / `GRAFANA_PASSWORD`) |
| Prometheus | http://localhost:9090 | Collecte et évaluation des règles |
| Alertmanager | http://localhost:9093 | Routage des notifications |
| Loki | http://localhost:3100 | Journaux et journal d'audit |
| Tempo | http://localhost:3200 | Magasin de traces (lecture seule ; écriture par le collecteur) |
| Collecteur OTel | `localhost:4317` / `4318` | Point d'entrée des traces — **et seul endroit où elles sont expurgées** |
| Simulateur | http://localhost:8000/metrics | Métriques et traces conformes au contrat |

Le tableau de bord *M7 · API & chaîne RAG* est provisionné automatiquement :
aucun import manuel. Il est versionné dans le dépôt et l'édition depuis
l'interface Grafana est désactivée — toute modification passe par une pull
request.

## Ce qui est réel et ce qui ne l'est pas

**Réel.** La pile complète, les règles d'alerte, le routage par gravité, les
règles d'inhibition, le tableau de bord, la rétention Loki à trois ans, le
module d'instrumentation que M5 importera tel quel, et la chaîne de traçage
jusqu'à Tempo.

### Pourquoi un collecteur, et pas Tempo directement

Tempo reçoit l'OTLP : le collecteur n'est pas nécessaire pour transporter.
Il est là pour une raison, et une seule — **c'est le seul endroit où une trace
peut être expurgée avant d'être stockée**.

Une trace de requête RAG porte l'URL appelée, les en-têtes, et tout attribut
que l'appelant a jugé utile d'ajouter : une question juridique en clair, un
jeton, une adresse. Le §2.3 du contrat l'interdit pour le journal d'audit ;
rien ne serait cohérent à l'interdire là et à le tolérer ici.

Le faire côté application supposerait que chaque service y pense. Le faire
dans le collecteur, c'est le garantir pour tous — y compris pour un service
écrit plus tard par quelqu'un qui n'aura pas lu ce fichier.

**Vérifié en exécutant**, le 6 septembre 2026 : une trace portant onze
attributs a été envoyée au collecteur. Tempo en a stocké trois.

| Envoyé | Stocké |
|---|---|
| `rag.question`, `rag.query`, `llm.prompt`, `llm.completion` | — supprimés |
| `user.email`, `client.address` | — supprimés |
| `authorization`, `cookie` | — supprimés |
| `enduser.id` = `utilisateur-4821` | `741cc1f5…` — condensé |
| `http.route`, `http.response.status_code` | conservés |

Ces suppressions sont gardées par `monitoring/tests/test_collecteur.py`, qui
échoue si une règle disparaît ou si un exportateur est ajouté hors du chemin
d'expurgation.

**Simulé.** Les données. `mock-exporter` produit un trafic plausible en
appliquant le contrat §1.3 à la lettre — mêmes noms, mêmes types, mêmes
étiquettes, mêmes intervalles d'histogramme.

Ce simulateur n'est pas une décoration : il rend la chaîne vérifiable de bout
en bout avant que M5 existe, et il sert de référence exécutable en cas de
divergence entre l'implémentation de M5 et le contrat écrit.

## Bascule vers l'API réelle

Une seule ligne à changer, dans `prometheus/prometheus.yml` :

```yaml
  - job_name: api
    static_configs:
      - targets: ["mock-exporter:8000"]   # ← remplacer par l'hôte de M5
```

Puis retirer le service `mock-exporter` du `docker-compose.yml`. Les règles
d'alerte, le tableau de bord et le runbook restent valables sans modification :
c'est précisément ce que garantit le fait d'avoir écrit le contrat d'abord.

Côté M5, l'instrumentation tient en deux lignes :

```python
from monitoring.instrumentation.metrics import instrumenter
from monitoring.instrumentation.tracing import activer_tracage

instrumenter(app)                            # expose /metrics et mesure les routes
activer_tracage(app, service="assistant-api")  # traces vers le collecteur
```

`activer_tracage` reste silencieux si `OTEL_EXPORTER_OTLP_ENDPOINT` n'est pas
défini : l'API démarre sans la pile d'observabilité. Avec la pile lancée, la
variable vaut `http://localhost:4318`.

## Structure

```
monitoring/
├── docker-compose.yml            # la pile complète
├── prometheus/
│   ├── prometheus.yml            # collecte, 15 s
│   └── rules/alerts.yml          # 8 règles, deux niveaux de gravité
├── alertmanager/
│   └── alertmanager.yml          # routage + inhibitions ; secrets montés
├── loki/loki-config.yml          # rétention 3 ans (décision A-4)
├── promtail/promtail-config.yml  # acheminement du journal d'audit
├── tempo/tempo-config.yml        # magasin de traces, rétention 30 jours
├── otel-collector/               # expurgation avant stockage
├── grafana/
│   ├── provisioning/             # sources de données et provisionnement
│   └── dashboards/api-rag.json   # tableau de bord versionné
├── mock_exporter/                # simulateur conforme au contrat
└── instrumentation/
    ├── metrics.py                # module importé par M5
    └── tracing.py                # activation en une ligne côté M5
```

## Ce qui reste bloqué

| Élément | Bloqué par |
|---|---|
| Instrumentation réelle des routes | M5 |
| Traces issues de vraies requêtes | M5 — la chaîne, elle, est prête |
| Détection de dérive | M2 + M5 |
| Tableaux de bord d'infrastructure | M4 |

Le traçage n'y figure plus. Il l'était par un collecteur que personne
n'avait déployé — et ce collecteur relevait de M7, pas de M4 ni de M5.
| Détection de dérive (Evidently) | M2 + M5 en fonctionnement |
| Surveillance de la qualité des réponses | M2 + M5 en fonctionnement |
| Boucle de rétroaction vers le ré-entraînement | l'ensemble de la chaîne |

Ces éléments ne dépendent pas de M7 : ils attendent l'existence d'un système
à observer.
