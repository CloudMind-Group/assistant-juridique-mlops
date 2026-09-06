/**
 * Vérifie les invariants du modèle de données du tableau de bord.
 * Exécuté par la CI : une incohérence dans assets/js/data.js bloque la fusion.
 *
 *   node .github/scripts/check-data.mjs
 */
import { readFileSync } from 'node:fs';
import { createContext, runInContext } from 'node:vm';

/* data.js déclare ses données avec `const` : on les remonte sur l'objet global
   du contexte pour pouvoir les inspecter depuis ce script. */
const EXPORTS = 'STATUS,MEMBERS,STAGES,LANES,STACK,QUALITY,TIMELINE,DELIVERABLES,SUPPORTS,WEEKS,RACI_LEGEND,raciRole,DEPENDENCIES,RELEASES,ROADMAP';
const source = readFileSync('assets/js/data.js', 'utf8')
  + `\n;Object.assign(globalThis,{${EXPORTS}});`;

const ctx = createContext({});
runInContext(source, ctx, { filename: 'data.js' });

const {
  STATUS, MEMBERS, STAGES, LANES, STACK, QUALITY, TIMELINE, DELIVERABLES,
  SUPPORTS, WEEKS, raciRole, DEPENDENCIES, RELEASES, ROADMAP
} = ctx;

const errors = [];
const check = (condition, message) => { if (!condition) errors.push(message); };

/* ------------------------------------------------------------ équipe */
check(MEMBERS.length === 8, `MEMBERS doit contenir 8 membres (trouvé ${MEMBERS.length})`);
check(new Set(MEMBERS.map(m => m.id)).size === 8, 'les identifiants de module doivent être uniques');

for (const m of MEMBERS) {
  const at = `[${m.id}] ${m.name}`;
  check(Object.hasOwn(STATUS, m.status), `${at} : statut inconnu « ${m.status} »`);
  check(Number.isInteger(m.progress) && m.progress >= 0 && m.progress <= 100,
        `${at} : progress doit être un entier de 0 à 100 (trouvé ${m.progress})`);
  check(m.subs.length > 0, `${at} : aucune sous-tâche`);
  check(m.subs.every(s => s[1] === 0 || s[1] === 1),
        `${at} : l'état d'une sous-tâche doit valoir 0 ou 1`);
  check(m.tools.length > 0, `${at} : aucun outil déclaré`);
  check(m.deliverables.length > 0, `${at} : aucun livrable déclaré`);
  check(typeof m.week === 'string' && m.week.length > 0, `${at} : fenêtre de planning manquante`);

  /* l'avancement affiché doit refléter les sous-tâches réellement terminées */
  const ratio = Math.round(m.subs.filter(s => s[1]).length / m.subs.length * 100);
  check(Math.abs(ratio - m.progress) <= 10,
        `${at} : progress=${m.progress}% incohérent avec les sous-tâches (${ratio}%)`);

  /* cohérence statut / avancement */
  if (m.status === 'done')    check(m.progress === 100, `${at} : statut « done » mais progress=${m.progress}%`);
  if (m.status === 'planned') check(m.progress === 0,   `${at} : statut « planned » mais progress=${m.progress}%`);
}

/* -------------------------------------------------------------- RACI */
for (const mod of MEMBERS) {
  const pilots = MEMBERS.filter(m => raciRole(m, mod.id) === 'A');
  check(pilots.length === 1,
        `module ${mod.id} : ${pilots.length} pilote(s) (A) au lieu d'un seul`);
}
for (const [id, supports] of Object.entries(SUPPORTS)) {
  check(MEMBERS.some(m => m.id === id), `SUPPORTS : identifiant inconnu « ${id} »`);
  check(!supports.includes(id), `SUPPORTS[${id}] : un pilote ne peut pas être son propre contributeur`);
  check(new Set(supports).size === supports.length, `SUPPORTS[${id}] : doublon`);
  for (const s of supports) {
    check(MEMBERS.some(m => m.id === s), `SUPPORTS[${id}] : module inconnu « ${s} »`);
  }
}
check(Object.keys(WEEKS).length === MEMBERS.length, 'WEEKS doit couvrir les 8 modules');

/* ------------------------------------------------- workflow, stack, métriques */
STAGES.forEach((s, i) => check(MEMBERS[s.owner] !== undefined, `STAGES[${i}] : propriétaire invalide`));
LANES.forEach((l, i) => check(MEMBERS[l.owner] !== undefined, `LANES[${i}] : propriétaire invalide`));
STACK.forEach((row, i) => check(MEMBERS[row[3]] !== undefined, `STACK[${i}] : responsable invalide`));
QUALITY.forEach(([label, , pct], i) =>
  check(pct >= 0 && pct <= 100, `QUALITY[${i}] (${label}) : pourcentage hors bornes`));

check(TIMELINE.length === 4, `TIMELINE doit compter 4 jalons hebdomadaires (trouvé ${TIMELINE.length})`);
check(DELIVERABLES.length === MEMBERS.length,
      `DELIVERABLES doit compter un artefact par module (trouvé ${DELIVERABLES.length})`);

/* ------------------------------------------------------- dépendances */
const ids = new Set(MEMBERS.map(m => m.id));

DEPENDENCIES.forEach((d, i) => {
  check(ids.has(d.from), `DEPENDENCIES[${i}] : module inconnu « ${d.from} »`);
  check(ids.has(d.on),   `DEPENDENCIES[${i}] : module inconnu « ${d.on} »`);
  check(d.from !== d.on, `DEPENDENCIES[${i}] : ${d.from} ne peut pas dépendre de lui-même`);
  check(typeof d.what === 'string' && d.what.length > 0,
        `DEPENDENCIES[${i}] : ${d.from} → ${d.on} sans objet de dépendance`);
});

check(new Set(DEPENDENCIES.map(d => `${d.from}->${d.on}`)).size === DEPENDENCIES.length,
      'DEPENDENCIES : une même dépendance est déclarée deux fois');

/* Un cycle rendrait le graphe insatisfaisable : chaque module attendrait un
   module qui l'attend. Le cas ne se lit pas à l'œil dès quatre arêtes, d'où
   ce contrôle — parcours en profondeur, pile courante marquée. */
const sortants = new Map(MEMBERS.map(m => [m.id, DEPENDENCIES.filter(d => d.from === m.id).map(d => d.on)]));
const VIERGE = 0, EN_COURS = 1, CLOS = 2;
const etat = new Map(MEMBERS.map(m => [m.id, VIERGE]));
/* Un ensemble, pas un tableau : deux arêtes parallèles font découvrir le même
   cycle deux fois, et le signaler deux fois n'apprend rien de plus. */
const cycles = new Set();

function explorer(id, chemin){
  etat.set(id, EN_COURS);
  for (const suivant of sortants.get(id) || []) {
    if (etat.get(suivant) === EN_COURS) {
      cycles.add([...chemin.slice(chemin.indexOf(suivant)), suivant].join(' → '));
    } else if (etat.get(suivant) === VIERGE) {
      explorer(suivant, [...chemin, suivant]);
    }
  }
  etat.set(id, CLOS);
}
for (const m of MEMBERS) if (etat.get(m.id) === VIERGE) explorer(m.id, [m.id]);
for (const c of cycles) check(false, `DEPENDENCIES : dépendance circulaire — ${c}`);

/* ---------------------------------------------------- feuille de route */
check(RELEASES.length > 0, 'RELEASES : aucune version déclarée');
RELEASES.forEach((r, i) => {
  check(/^v\d+\.\d+\.\d+$/.test(r.id), `RELEASES[${i}] : « ${r.id} » n'est pas une version sémantique`);
  check(Object.hasOwn(STATUS, r.state), `RELEASES[${i}] (${r.id}) : statut inconnu « ${r.state} »`);
});

check(Object.keys(ROADMAP).length === MEMBERS.length,
      `ROADMAP doit couvrir les ${MEMBERS.length} modules (trouvé ${Object.keys(ROADMAP).length})`);
for (const [id, cells] of Object.entries(ROADMAP)) {
  check(ids.has(id), `ROADMAP : module inconnu « ${id} »`);
  check(cells.length === RELEASES.length,
        `ROADMAP[${id}] : ${cells.length} case(s) pour ${RELEASES.length} version(s)`);
  cells.forEach((cell, i) => {
    if (cell === null) return;
    check(Object.hasOwn(STATUS, cell[0]), `ROADMAP[${id}][${i}] : statut inconnu « ${cell[0]} »`);
    check(typeof cell[1] === 'string' && cell[1].length > 0, `ROADMAP[${id}][${i}] : libellé vide`);
  });
}

/* ----------------------------------------------------------------- bilan */
if (errors.length) {
  for (const e of errors) console.error(`::error::${e}`);
  console.error(`\n${errors.length} incohérence(s) détectée(s) dans le modèle de données.`);
  process.exit(1);
}

const global = Math.round(MEMBERS.reduce((a, m) => a + m.progress, 0) / MEMBERS.length);
const subs = MEMBERS.reduce((a, m) => a + m.subs.length, 0);
const done = MEMBERS.reduce((a, m) => a + m.subs.filter(s => s[1]).length, 0);
console.log('Modèle de données cohérent.');
console.log(`  · 8 modules, 8 pilotes uniques`);
console.log(`  · sous-tâches : ${done}/${subs} terminées`);
console.log(`  · avancement global : ${global}%`);
console.log(`  · planning : ${TIMELINE.length} semaines`);
console.log(`  · dépendances : ${DEPENDENCIES.length} arêtes, aucun cycle`);
console.log(`  · feuille de route : ${RELEASES.length} versions × ${MEMBERS.length} modules`);
