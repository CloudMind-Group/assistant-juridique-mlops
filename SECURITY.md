# Politique de sécurité

Responsable : **Taha Kachmar (M8 — Security, Governance & Compliance)**.

## Périmètre

Ce dépôt contient le tableau de bord de pilotage du projet. Il ne doit contenir
**aucune donnée réelle** : pas de document juridique client, pas de donnée à caractère
personnel, pas d'identifiant, pas de clé d'API — y compris dans les issues, les pull
requests et les captures d'écran.

## Signaler une vulnérabilité

N'ouvrez **pas** d'issue publique. Utilisez l'onglet
`Security → Report a vulnerability` (GitHub Private Vulnerability Reporting),
ou contactez directement le responsable M8.

Délai de première réponse visé : **48 heures**.

## Bonnes pratiques appliquées

- Secrets stockés uniquement dans `Settings → Secrets and variables → Actions`.
- `GITHUB_TOKEN` en lecture seule par défaut ; les workflows déclarent leurs permissions.
- Actions GitHub épinglées à une version majeure et issues d'éditeurs vérifiés.
- Branche `main` protégée : revue obligatoire, historique linéaire, pas de force push.
- Vérification automatique en CI de l'absence de valeur sensible en clair.

## Données du projet applicatif

Le traitement des corpus juridiques fait l'objet d'un dossier de conformité
dédié, tenu à jour en même temps que le code :

| Document | Répond à la question |
|---|---|
| [`docs/RGPD.md`](docs/RGPD.md) | Quelles données sont traitées, d'où, pourquoi, où elles sont stockées, combien de temps |
| [`docs/AIPD.md`](docs/AIPD.md) | Quels risques pour les personnes, quelles mesures, quel risque résiduel |
| [`docs/HABILITATIONS.md`](docs/HABILITATIONS.md) | Qui accède à quoi, et sous quelle trace |
| [`docs/OBSERVABILITE.md`](docs/OBSERVABILITE.md) §2 | Ce que le journal d'audit contient, et ce qu'il ne doit jamais contenir |

L'architecture générale figure dans [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
et la répartition des responsabilités dans [`docs/TEAM.md`](docs/TEAM.md).

> **Une réserve bloquante est en vigueur.** L'ingestion d'un corpus judiciaire
> réel ne doit pas commencer avant la réalisation de l'action A-1 de l'AIPD —
> le remplacement de la détection par expressions régulières par un détecteur
> NER. Le corpus en circulation est aujourd'hui entièrement synthétique.
