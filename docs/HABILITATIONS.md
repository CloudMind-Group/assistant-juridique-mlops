# Matrice des habilitations

**Responsable :** Taha Kachmar — M8, Sécurité, Gouvernance & Conformité
**Version :** 1.0 — 2 septembre 2026
**Documents liés :** [`RGPD.md`](RGPD.md) · [`AIPD.md`](AIPD.md) · [`OBSERVABILITE.md`](OBSERVABILITE.md)

> Ce document est écrit **avant** que M5 n'implémente l'authentification. C'est
> délibéré : un modèle de rôles figé dans le code se corrige mal, et l'exigence
> transmise à M2 avant qu'elle ne construise l'index (suppression ciblée par
> `doc_id`) a montré ce que vaut une contrainte posée au bon moment — elle n'a
> rien coûté à intégrer.

---

## Sommaire

- [1. Ce que ce document décide, et ce qu'il ne décide pas](#1-ce-que-ce-document-décide-et-ce-quil-ne-décide-pas)
- [2. Les rôles](#2-les-rôles)
- [3. Les ressources](#3-les-ressources)
- [4. La matrice](#4-la-matrice)
- [5. Le cloisonnement multi-cabinets](#5-le-cloisonnement-multi-cabinets)
- [6. Trois règles qui ne se déduisent pas de la matrice](#6-trois-règles-qui-ne-se-déduisent-pas-de-la-matrice)
- [7. État de mise en œuvre](#7-état-de-mise-en-œuvre)

---

## 1. Ce que ce document décide, et ce qu'il ne décide pas

**Il décide** qui peut accéder à quoi, et sous quelle trace.

**Il ne décide pas** comment l'authentification est implémentée — JWT, OAuth2,
sessions : c'est le périmètre de M5. Ce qui suit doit tenir quel que soit le
mécanisme retenu.

Le principe directeur est le **moindre privilège** : un rôle reçoit ce dont il a
besoin pour sa tâche, et rien de plus. Ce n'est pas une posture de méfiance —
c'est ce qui rend un incident circonscrit au lieu de total.

## 2. Les rôles

### Côté application

| Rôle | `actor_role` | Qui | Ce qu'il vient faire |
|---|---|---|---|
| **Particulier** | `particulier` | Une personne qui s'informe sur ses droits | Poser une question, lire une réponse sourcée |
| **Juriste** | `juriste` | Avocat, juriste d'entreprise, notaire | Idem, plus l'historique de ses recherches |
| **Gestionnaire de cabinet** | `gestionnaire` | Responsable d'un cabinet client | Gérer les comptes de son cabinet, et **rien au-delà** |
| **Administrateur** | `admin` | Exploitant du service | Gérer comptes et cabinets, sans lire les contenus |

La valeur de `actor_role` alimente le champ du même nom dans le journal d'audit
([`OBSERVABILITE.md`](OBSERVABILITE.md) §2.2).

### Côté équipe

| Rôle | Qui | Portée |
|---|---|---|
| **Ingénieur données** | M1 | Corpus brut et traité, pipeline |
| **Ingénieur modèle** | M2, M3 | Index, expérimentations, registre de modèles |
| **Exploitant** | M4, M7 | Infrastructure, pile d'observabilité |
| **Conformité** | M8 | Journal d'audit, registre, revue des règles |

## 3. Les ressources

| Ressource | Où | Contient |
|---|---|---|
| **Corpus brut** | `data/raw/` — remote DVC | Textes non anonymisés — **le seul endroit où subsistent des données personnelles** |
| **Corpus traité** | `data/processed/` | Textes anonymisés, prêts pour l'indexation |
| **Index vectoriel** | Qdrant / ChromaDB | Vecteurs et passages, anonymisés (fiche T-03) |
| **Journal d'audit** | Loki | Identifiants pseudonymes sous HMAC, `doc_id`, aucune donnée personnelle |
| **Métriques et tableaux de bord** | Prometheus / Grafana | Agrégats — aucune donnée personnelle |
| **Registre de modèles** | MLflow | Métriques agrégées, Model Cards |
| **Comptes utilisateurs** | Base applicative | Identités des utilisateurs du service |

## 4. La matrice

`L` lecture · `E` écriture · `—` aucun accès

### Rôles applicatifs

| | Corpus brut | Corpus traité | Index | Journal d'audit | Comptes | Réponses |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| Particulier | — | — | — | — | siennes | siennes |
| Juriste | — | — | — | — | siennes | siennes |
| Gestionnaire | — | — | — | — | son cabinet | — |
| Administrateur | — | — | — | — | `L`/`E` | — |

**Aucun rôle applicatif n'accède directement au corpus ni à l'index.** L'accès
se fait par l'API, qui ne restitue que les extraits cités dans une réponse.

Et **l'administrateur ne lit pas les réponses des utilisateurs.** Gérer des
comptes n'exige pas de lire ce que les gens demandent. Cette séparation vaut
d'être défendue explicitement, parce qu'elle est la première à sauter quand on
implémente un « panneau d'administration » sans y réfléchir.

### Rôles de l'équipe

| | Corpus brut | Corpus traité | Index | Journal d'audit | Métriques | MLflow |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| Ingénieur données (M1) | `L`/`E` | `L`/`E` | — | — | `L` | `L` |
| Ingénieur modèle (M2, M3) | — | `L` | `L`/`E` | — | `L` | `L`/`E` |
| Exploitant (M4, M7) | — | — | — | `L` | `L`/`E` | `L` |
| Conformité (M8) | `L` | `L` | `L` | `L` | `L` | `L` |

**M8 lit et n'écrit pas.** C'est volontaire : celui qui contrôle ne doit pas
pouvoir modifier ce qu'il contrôle, sinon son attestation ne vaut rien.

**M2 n'accède pas au corpus brut.** Elle travaille sur `data/processed/`,
c'est-à-dire sur du texte déjà anonymisé. Rien dans son travail ne nécessite les
originaux, et c'est ce qui garantit qu'aucune donnée personnelle ne peut entrer
dans l'index par cette voie.

## 5. Le cloisonnement multi-cabinets

L'architecture prévoit un service utilisable par plusieurs cabinets
([`ARCHITECTURE.md`](ARCHITECTURE.md)). Deux conséquences, à traiter séparément.

**Le corpus juridique est commun.** Les textes de loi et la jurisprudence
publiée ne sont propres à personne : tous les cabinets interrogent le même
index, et il n'y a rien à cloisonner de ce côté.

**Tout le reste est cloisonné par cabinet** : historique des recherches,
documents déposés, comptes. Un gestionnaire voit son cabinet et aucun autre.

**Le cloisonnement se fait côté requête, jamais côté affichage.** Un filtre
appliqué au rendu laisse les données traverser le service et se contourne par
n'importe quel appel direct à l'API. Le `cabinet_id` doit être une contrainte de
la requête, dérivée du jeton d'authentification et **jamais** d'un paramètre
fourni par le client — sans quoi il suffit de le changer pour lire le cabinet
voisin.

## 6. Trois règles qui ne se déduisent pas de la matrice

### 6.1 Le journal d'audit se lit, ne se modifie pas

Deux rôles y accèdent en lecture : l'exploitant (M7) pour l'incident, la
conformité (M8) pour le contrôle. **Personne n'y écrit à la main, personne n'en
supprime une ligne.** Le contrat le pose déjà en ajout seul
([`OBSERVABILITE.md`](OBSERVABILITE.md) §2.1) ; la matrice le confirme du côté
des droits.

Un journal modifiable par celui qu'il surveille ne prouve rien.

### 6.2 L'accès au corpus brut est le plus sensible du système

C'est le **seul endroit** où subsistent des données personnelles non
anonymisées. Deux rôles y accèdent : M1 qui l'alimente, M8 qui le contrôle en
lecture.

Trois exigences en découlent :

- l'accès passe par le compte de l'organisation, jamais par un compte personnel
  (écart E-R9, résolu le 29/08) ;
- il est **journalisé** — c'est l'écart E-04, ouvert : DagsHub ne fournit pas
  aujourd'hui de journal exploitable par l'organisation ;
- il est réexaminé à chaque départ d'un membre de l'équipe.

### 6.3 Le rôle est porté par le jeton, jamais par la requête

Le `actor_role` inscrit au journal doit venir du jeton d'authentification
vérifié côté serveur. S'il vient d'un en-tête ou d'un champ de la requête, il
est déclaratif — et un journal d'audit qui enregistre le rôle que le client
prétend avoir documente une fiction.

## 7. État de mise en œuvre

| Élément | Dépend de | État |
|---|---|---|
| Rôles applicatifs | M5 | **Défini ici, non implémenté** — M5 n'a pas commencé |
| Cloisonnement multi-cabinets | M5 + M2 | Défini, non implémenté |
| Droits de l'équipe sur le corpus | M1 + M8 | Partiellement appliqué — dépôt privé sur le compte de l'organisation, sans contrôle par rôle |
| Journal des accès au corpus | hébergeur | **Non disponible** — écart E-04 |
| Lecture du journal d'audit | M7 | Contrat prêt, aucune source d'événements |

**Rien de ce document n'est appliqué techniquement à ce jour.** Le service
n'existe pas : ni API, ni interface, ni utilisateurs. Ce qui est appliqué, c'est
la restriction d'accès au dépôt et au corpus, et elle repose sur les droits
GitHub et DagsHub, pas sur un modèle de rôles.

Ce document est donc une **spécification adressée à M5**, pas un état des lieux.
Il sera repris en état des lieux quand l'authentification existera — et la
différence entre les deux sera alors, elle aussi, un écart à consigner.

---

## Révision

À réviser lorsque M5 implémente l'authentification, lorsqu'un rôle est ajouté ou
retiré, et à chaque départ d'un membre de l'équipe.
