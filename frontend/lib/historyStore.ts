import { create } from "zustand";
import type { HistoryEntry } from "@/types";

interface HistoryState {
  entries: HistoryEntry[];
  addEntry: (entry: HistoryEntry) => void;
  setFeedback: (id: string, feedback: "up" | "down") => void;
}

// Seed data: the same items previously hardcoded separately in the sidebar
// (mockData.sidebarHistory) and the dashboard table (mockData.consultationHistory).
// Both views now read from this single store, so a new consultation or a
// newly analyzed document shows up in *both* places automatically instead of
// requiring two mock arrays to be kept in sync by hand.
const seedEntries: HistoryEntry[] = [
  {
    id: "seed_doc_1",
    kind: "document",
    title: "Contrat de prestation Nexus",
    date: "2026-09-08T11:32:00",
  },
  {
    id: "seed_doc_2",
    kind: "document",
    title: "NDA — Partenariat Arvalis",
    date: "2026-09-07T15:04:00",
  },
  {
    id: "seed_doc_3",
    kind: "document",
    title: "CGV e-commerce Bloom & Co.",
    date: "2026-09-05T00:00:00",
  },
  {
    id: "seed_doc_4",
    kind: "document",
    title: "Bail commercial — Rue de Rivoli",
    date: "2026-09-03T00:00:00",
  },
  {
    id: "seed_c_1",
    kind: "consultation",
    title: "Quelles clauses limitent la responsabilité du prestataire ?",
    date: "2026-09-08T09:10:00",
    feedback: "up",
  },
  {
    id: "seed_c_2",
    kind: "consultation",
    title: "Le délai de préavis est-il conforme au droit français ?",
    date: "2026-09-07T14:20:00",
    feedback: "up",
  },
  {
    id: "seed_c_3",
    kind: "consultation",
    title: "Y a-t-il des clauses abusives dans ce contrat de bail ?",
    date: "2026-09-05T10:00:00",
    feedback: "down",
  },
  {
    id: "seed_c_4",
    kind: "consultation",
    title: "Résumé des obligations du distributeur dans l'accord Medixa",
    date: "2026-09-03T16:45:00",
    feedback: "up",
  },
  {
    id: "seed_c_5",
    kind: "consultation",
    title: "Vérifier la conformité RGPD des clauses de données personnelles",
    date: "2026-09-01T08:30:00",
    feedback: "up",
  },
];

export const useHistoryStore = create<HistoryState>()((set, get) => ({
  entries: seedEntries,
  addEntry: (entry) => {
    // New activity always goes first — both the sidebar and the dashboard
    // table render entries in the order they appear here.
    set({ entries: [entry, ...get().entries] });
  },
  setFeedback: (id, feedback) => {
    set({
      entries: get().entries.map((entry) =>
        entry.id === id ? { ...entry, feedback } : entry
      ),
    });
  },
}));
