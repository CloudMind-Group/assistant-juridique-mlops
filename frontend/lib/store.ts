import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ChatMessage, Locale, Theme, UploadedDocument } from "@/types";
import { generateId } from "@/lib/utils";

interface UiState {
  theme: Theme;
  locale: Locale;
  sidebarCollapsed: boolean;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  setLocale: (locale: Locale) => void;
  toggleSidebar: () => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set, get) => ({
      theme: "light",
      locale: "fr",
      sidebarCollapsed: false,
      setTheme: (theme) => set({ theme }),
      toggleTheme: () =>
        set({ theme: get().theme === "light" ? "dark" : "light" }),
      setLocale: (locale) => set({ locale }),
      toggleSidebar: () => set({ sidebarCollapsed: !get().sidebarCollapsed }),
    }),
    { name: "aj-ui-preferences" }
  )
);

interface ChatState {
  messages: ChatMessage[];
  isResponding: boolean;
  sendMessage: (content: string) => void;
  setFeedback: (messageId: string, feedback: "up" | "down") => void;
  reset: () => void;
}

// Deterministic mock reply used to demonstrate streaming, grounding and
// source-citation UI without depending on the (not-yet-available) M5 API.
function buildMockReply(question: string): ChatMessage {
  return {
    id: generateId("msg"),
    role: "assistant",
    content:
      "D'après le corpus indexé, la clause de responsabilité limite l'indemnisation du prestataire au montant des honoraires perçus au titre des douze derniers mois, sauf faute lourde ou dol. Cette limitation est usuelle en droit des contrats commerciaux mais reste inopposable en cas de manquement à une obligation essentielle.",
    sources: [
      {
        id: generateId("src"),
        label: "Contrat Nexus SAS — Prestation Q3.pdf, art. 9",
        excerpt:
          "« La responsabilité du Prestataire est limitée, tous préjudices confondus, au montant des sommes versées… »",
        reference: "Article 9 — Limitation de responsabilité",
      },
      {
        id: generateId("src"),
        label: "Code civil, art. 1231-3",
        excerpt:
          "« Le débiteur n'est tenu que des dommages et intérêts prévus ou prévisibles… »",
        reference: "Code civil, article 1231-3",
      },
    ],
    feedback: null,
    createdAt: new Date().toISOString(),
  };
}

export const useChatStore = create<ChatState>()((set, get) => ({
  messages: [],
  isResponding: false,
  sendMessage: (content) => {
    const userMessage: ChatMessage = {
      id: generateId("msg"),
      role: "user",
      content,
      createdAt: new Date().toISOString(),
    };
    set({ messages: [...get().messages, userMessage], isResponding: true });

    // Simulated latency for the streamed assistant reply; the real
    // implementation will consume the SSE endpoint delivered by M5.
    setTimeout(() => {
      const reply = buildMockReply(content);
      set({ messages: [...get().messages, reply], isResponding: false });
    }, 900);
  },
  setFeedback: (messageId, feedback) => {
    set({
      messages: get().messages.map((m) =>
        m.id === messageId ? { ...m, feedback } : m
      ),
    });
  },
  reset: () => set({ messages: [], isResponding: false }),
}));

interface UploadState {
  documents: UploadedDocument[];
  addFiles: (files: File[]) => void;
  reset: () => void;
}

export const useUploadStore = create<UploadState>()((set, get) => ({
  documents: [],
  addFiles: (files) => {
    const entries: UploadedDocument[] = files.map((file) => ({
      id: generateId("upload"),
      name: file.name,
      sizeLabel: formatBytes(file.size),
      progress: 0,
      status: "en_telechargement",
    }));
    set({ documents: [...get().documents, ...entries] });

    // Mocked pipeline progression (téléchargement -> OCR -> analyse -> terminé),
    // standing in for the real ingestion + OCR + RAG pipeline (M1/M2/M5).
    entries.forEach((entry) => simulateProcessing(entry.id, set, get));
  },
  reset: () => set({ documents: [] }),
}));

function simulateProcessing(
  id: string,
  set: (partial: Partial<UploadState>) => void,
  get: () => UploadState
) {
  const stages: UploadedDocument["status"][] = [
    "en_telechargement",
    "ocr",
    "analyse",
    "termine",
  ];
  let stageIndex = 0;
  const tick = () => {
    stageIndex += 1;
    const documents = get().documents.map((doc) => {
      if (doc.id !== id) return doc;
      const status = stages[Math.min(stageIndex, stages.length - 1)];
      const progress = Math.min(100, Math.round((stageIndex / stages.length) * 100));
      return { ...doc, status, progress };
    });
    set({ documents });
    if (stageIndex < stages.length - 1) {
      setTimeout(tick, 700);
    }
  };
  setTimeout(tick, 500);
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  const units = ["Ko", "Mo", "Go"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}
