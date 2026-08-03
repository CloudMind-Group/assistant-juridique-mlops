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

Le traitement des corpus juridiques (anonymisation avant indexation, contrôle d'accès,
journal d'audit, registre RGPD) est décrit dans
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) et [`docs/TEAM.md`](docs/TEAM.md).
