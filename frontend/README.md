## Corrections apportées suite à la review PR #74

- **`store.ts` — bug corrigé** : `simulateProcessing` plafonnait à 75 % au
  lieu de 100 % (division par `stages.length` au lieu de `stages.length - 1`).
  La barre de progression atteint maintenant 100 % quand le statut passe à
  "Terminé".
- **i18n complet** : les `aria-label` codés en dur en français dans
  `Topbar.tsx`, `Sidebar.tsx`, `FeedbackWidget.tsx` et
  `ConsultationsHistoryTable.tsx`, ainsi que le "Jour {n}" du tooltip dans
  `ActivityChart.tsx`, passent maintenant par `locales/fr.json` /
  `locales/ar.json`. Un lecteur d'écran en session arabe entend désormais de
  l'arabe partout, pas seulement le texte visible.
- **`lib/api.ts` — couche frontière** : traduit le format `/chat` de M5
  (`answer` / `citations[].chunk_id,title,excerpt` / `refused`) vers le
  format interne (`content` / `sources[].id,label,excerpt`) sans toucher un
  seul composant. Bascule vers l'API réelle en remplaçant uniquement le corps
  de `fetchChatReply` — voir le commentaire en tête de fichier.
  Champ `reference` : en attente de la réponse d'Iman (issue #76) — utilise
  `title + date` pour l'instant, marqué `TODO` dans le code.
- **`refused` traité visuellement** : une réponse hors périmètre (guardrail
  M2) s'affiche maintenant dans une bulle distincte (bordure/fond doré +
  étiquette "Hors périmètre"), jamais comme une réponse normale — voir
  `MessageBubble.tsx`.
- **Historique connecté** : `lib/historyStore.ts` centralise les
  consultations et les documents analysés. La sidebar (visible sur toutes les
  pages, y compris Analyse de contrat) et la table "Historique des
  consultations" du tableau de bord se mettent maintenant à jour
  automatiquement dès qu'une consultation se termine ou qu'un document
  atteint le statut "Terminé" — plus besoin de rafraîchir.
- **Design system retiré de la navigation** (page supprimée, plus de lien
  dans la sidebar) — non nécessaire pour la démo.
- **Corrections mineures** : type de `ChatComposer` (un `KeyboardEvent` était
  passé à un handler typé `FormEvent`), `baseUrl` manquant dans
  `tsconfig.json`, timers factices non réinitialisés dans
  `chatStore.test.ts` (ajout de `afterEach(() => vi.useRealTimers())`).

`npx tsc --noEmit` passe sans erreur sur l'ensemble du projet après ces
correctifs.

---

# Assistant Juridique — Frontend (Oumaïma · Design system & UX)

Interface produit de la plateforme **Assistant Juridique Intelligent** (CloudMind Group).
Ce dossier contient uniquement la partie **frontend / UX** du projet (à ne pas confondre
avec `assistant-juridique-mlops`, le dépôt du pipeline MLOps + site de pilotage d'équipe).

Construit avec le stack demandé : **React · TypeScript · Next.js (App Router) · Tailwind CSS
· Zustand · Vitest · i18next**.

## Ce qui est livré

| Écran | Route | Contenu |
|---|---|---|
| Tableau de bord | `/tableau-de-bord` | KPIs, activité des consultations (aire), statut des documents (donut), table des documents analysés, historique des consultations exportable |
| Consultation | `/consultation` | Interface conversationnelle en flux, historique persistant (Zustand), citations de sources, widget de feedback 👍/👎 + commentaire |
| Analyse de contrat | `/analyse-de-contrat` | Upload par glisser-déposer ou sélecteur de fichiers, file de traitement avec barre de progression (téléchargement → OCR → analyse → terminé) |

La barre latérale (navigation + historique) et l'en-tête (titre de page, sélecteur de
période, bouton Actualiser, thème, langue) sont communs à tous les écrans via `AppShell`.

## Correspondance avec les tâches du brief

- **Système de design et maquettes haute-fidélité** → `/design-system` + tokens dans `tailwind.config.ts`
- **Interface conversationnelle avec rendu en flux et historique persistant** → `components/consultation/*`, `lib/store.ts` (`useChatStore`)
- **Composant d'upload avec prévisualisation et suivi de traitement** → `components/analyse/*`, `useUploadStore`
- **Affichage des sources citées avec renvoi vers l'extrait exact** → `SourceCitations.tsx`
- **Tableau de bord utilisateur (historique, documents, export PDF)** → `components/dashboard/*`
- **Accessibilité RGAA/WCAG 2.1 AA, mode sombre, i18n FR/AR** → focus visible global (`globals.css`), `dark:` variants partout, `locales/fr.json` + `locales/ar.json`, bascule RTL automatique (`dir="rtl"` sur `<html>`)
- **Widget de feedback (pouce haut/bas + commentaire)** → `FeedbackWidget.tsx`

## Démarrage

```bash
npm install
npm run dev       # http://localhost:3000
npm run test      # Vitest (jsdom + Testing Library)
npm run lint
npm run build && npm run start   # build de production
```

> Ce sandbox n'a pas d'accès réseau pour exécuter `npm install` ; le code a été écrit
> et relu manuellement contre les API connues de chaque librairie, mais lance `npm run build`
> et `npm run test` en local avant de merger, au cas où une dépendance de version aurait
> besoin d'un ajustement mineur.

## Données actuelles : mock, pas encore l'API M5

Il n'existe pas encore d'API backend exposée (M5 — FastAPI/SSE — est prévu en S2 → S3).
Toutes les données viennent donc de `lib/mockData.ts` (dashboard, historique) et de
générateurs simulés dans `lib/store.ts` :

- `useChatStore.sendMessage` simule un flux de réponse (délai + citations) — à remplacer
  par la consommation du futur endpoint SSE de M5 (`docs` : contrat d'interface à récupérer
  auprès de Nouhaila).
- `useUploadStore.addFiles` simule la progression téléchargement → OCR → analyse → terminé —
  à brancher sur l'endpoint d'upload documentaire de M5 une fois disponible.

Les deux stores sont isolés du reste des composants : brancher l'API réelle ne devrait
toucher que `lib/store.ts`, pas les composants d'UI.

## Structure

```
app/
  layout.tsx              Layout racine (polices, providers)
  providers.tsx            Sync thème/langue/dir (client)
  globals.css               Tokens CSS, focus visible, reduced-motion
  tableau-de-bord/page.tsx
  consultation/page.tsx
  analyse-de-contrat/page.tsx
  design-system/page.tsx
components/
  layout/                  Sidebar, Topbar, AppShell
  dashboard/               StatCard, ActivityChart, StatusDonut, tables
  consultation/            ChatWindow, MessageBubble, SourceCitations, FeedbackWidget
  analyse/                 UploadDropzone, ProcessingStatusList
  ui/                      Button, Badge, Card (primitives partagées)
lib/
  store.ts                 Zustand : thème/langue/sidebar, chat, upload
  i18n.ts, mockData.ts, format.ts, utils.ts
locales/
  fr.json, ar.json
types/
  index.ts
tests/
  *.test.ts(x)             Vitest + Testing Library
```

## Accessibilité & i18n — notes d'implémentation

- Toutes les positions/marges directionnelles utilisent les utilitaires logiques Tailwind
  (`ps-`, `pe-`, `start-`, `end-`) plutôt que `left`/`right`, pour un basculement RTL propre
  en arabe sans classes dupliquées.
- `prefers-reduced-motion` est respecté globalement (`globals.css`).
- Le focus clavier est toujours visible (`:focus-visible`), y compris sur les boutons de la
  sidebar et les onglets de tableau.
- Le mode sombre est piloté par une classe (`darkMode: "class"` dans Tailwind), persistée
  via Zustand + `localStorage`.

## Prochaines étapes suggérées

1. Brancher `useChatStore` et `useUploadStore` sur l'API réelle de M5 dès que le contrat
   SSE/upload est stabilisé.
2. Ajouter des tests Vitest sur `ChatWindow` et `UploadDropzone` (interactions drag & drop).
3. Passer une revue RGAA complète (lecteur d'écran) une fois l'API branchée et les vraies
   données de contenu juridique disponibles.
