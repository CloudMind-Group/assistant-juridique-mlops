import type { AnalyzedDocument, DonutSegment, StatSummary } from "@/types";

export const statSummaries: StatSummary[] = [
  {
    key: "consultations",
    labelKey: "dashboard.stats.consultations",
    value: "128",
    deltaLabel: "dashboard.stats.consultationsDelta",
    deltaDirection: "up",
    icon: "chat",
    accent: "forest",
  },
  {
    key: "documents",
    labelKey: "dashboard.stats.documents",
    value: "43",
    deltaLabel: "dashboard.stats.documentsDelta",
    deltaDirection: "up",
    icon: "document",
    accent: "gold",
  },
  {
    key: "satisfaction",
    labelKey: "dashboard.stats.satisfaction",
    value: "87%",
    deltaLabel: "dashboard.stats.satisfactionDelta",
    deltaDirection: "up",
    icon: "smile",
    accent: "sage",
  },
  {
    key: "latence",
    labelKey: "dashboard.stats.latence",
    value: "2.4 s",
    deltaLabel: "dashboard.stats.latenceDelta",
    deltaDirection: "down",
    icon: "clock",
    accent: "sky",
  },
];

// Daily consultation activity for the last 30 days — used by the area chart.
// Values are illustrative: a noisy but generally upward trend, as in the target design.
export const activitySeries: { day: number; value: number }[] = [
  2, 4, 3, 6, 5, 8, 7, 9, 6, 8, 10, 9, 12, 10, 13, 11, 14, 13, 16, 14, 17, 15,
  18, 17, 19, 18, 21, 19, 22, 24,
].map((value, index) => ({ day: index + 1, value }));

export const documentStatusSegments: DonutSegment[] = [
  {
    key: "en_attente",
    labelKey: "dashboard.status.enAttente",
    value: 12,
    percent: 16,
    color: "#e0ac5c",
  },
  {
    key: "en_cours",
    labelKey: "dashboard.status.enCours",
    value: 19,
    percent: 25,
    color: "#6c8874",
  },
  {
    key: "en_revision",
    labelKey: "dashboard.status.enRevision",
    value: 8,
    percent: 11,
    color: "#93b7c7",
  },
  {
    key: "approuve",
    labelKey: "dashboard.status.approuve",
    value: 31,
    percent: 41,
    color: "#26543a",
  },
  {
    key: "rejete",
    labelKey: "dashboard.status.rejete",
    value: 5,
    percent: 7,
    color: "#b5473f",
  },
];

export const analyzedDocuments: AnalyzedDocument[] = [
  {
    id: "doc_1",
    name: "Contrat Nexus SAS — Prestation Q3.pdf",
    date: "2026-09-08",
    status: "termine",
  },
  {
    id: "doc_2",
    name: "NDA Arvalis Group — v2.docx",
    date: "2026-09-07",
    status: "ocr_en_cours",
  },
  {
    id: "doc_3",
    name: "CGV Bloom & Co. — Sept 2026.pdf",
    date: "2026-09-05",
    status: "termine",
  },
  {
    id: "doc_4",
    name: "Bail Rue de Rivoli — Projet.pdf",
    date: "2026-09-03",
    status: "echec",
  },
  {
    id: "doc_5",
    name: "Accord distribution Medixa — Final.pdf",
    date: "2026-09-01",
    status: "en_attente",
  },
];


