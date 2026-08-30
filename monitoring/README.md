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
| Simulateur | http://localhost:8000/metrics | Métriques conformes au contrat |

Le tableau de bord *M7 · API & chaîne RAG* est provisionné automatiquement :
aucun import manuel. Il est versionné dans le dépôt et l'édition depuis
l'interface Grafana est désactivée — toute modification passe par une pull
request.

## Ce qui est réel et ce qui ne l'est pas

**Réel.** La pile complète, les règles d'alerte, le routage par gravité, les
règles d'inhibition, le tableau de bord, la rétention Loki à trois ans, et le
module d'instrumentation que M5 importera tel quel.

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

instrumenter(app)   # expose /metrics et mesure toutes les routes
```

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
├── grafana/
│   ├── provisioning/             # sources de données et provisionnement
│   └── dashboards/api-rag.json   # tableau de bord versionné
├── mock_exporter/                # simulateur conforme au contrat
└── instrumentation/
    ├── metrics.py                # module importé par M5
    └── tracing.py                # squelette OpenTelemetry
```

## Ce qui reste bloqué

| Élément | Bloqué par |
|---|---|
| Instrumentation réelle des routes | M5 |
| Traçage distribué de bout en bout | M5 + M2 |
| Tableaux de bord d'infrastructure | M4 |
| Détection de dérive (Evidently) | M2 + M5 en fonctionnement |
| Surveillance de la qualité des réponses | M2 + M5 en fonctionnement |
| Boucle de rétroaction vers le ré-entraînement | l'ensemble de la chaîne |

Ces éléments ne dépendent pas de M7 : ils attendent l'existence d'un système
à observer.
