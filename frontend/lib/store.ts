import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ChatMessage, Locale, Theme, UploadedDocument } from "@/types";
import { generateId } from "@/lib/utils";
import { fetchChatReply, mapChatResponse } from "@/lib/api";
import { useHistoryStore } from "@/lib/historyStore";

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

    // Goes through the API boundary layer (lib/api.ts) so this store never
    // has to know the backend's wire shape. Swap fetchChatReply's internals
    // for a real call once M5 is merged — nothing here changes.
    fetchChatReply(content).then((response) => {
      const reply = mapChatResponse(response);
      set({ messages: [...get().messages, reply], isResponding: false });

      // Every finished consultation — refused or not — is worth keeping in
      // the audit trail shown in the sidebar and in the dashboard's
      // "Historique des consultations" table.
      useHistoryStore.getState().addEntry({
        id: reply.id,
        kind: "consultation",
        title: content,
        date: reply.createdAt,
        feedback: null,
      });
    });
  },
  setFeedback: (messageId, feedback) => {
    set({
      messages: get().messages.map((m) =>
        m.id === messageId ? { ...m, feedback } : m
      ),
    });
    // Keep the dashboard's history table in sync with feedback given inline
    // in the chat — the message id and the history entry id are the same
    // (see mapChatResponse / sendMessage above).
    useHistoryStore.getState().setFeedback(messageId, feedback);
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
    entries.forEach((entry) => simulateProcessing(entry.id, entry.name, set, get));
  },
  reset: () => set({ documents: [] }),
}));

function simulateProcessing(
  id: string,
  name: string,
  set: (partial: Partial<UploadState>) => void,
  get: () => UploadState
) {
  const stages: UploadedDocument["status"][] = [
    "en_telechargement",
    "ocr",
    "analyse",
    "termine",
  ];
  const lastStageIndex = stages.length - 1;
  let stageIndex = 0;

  const tick = () => {
    stageIndex += 1;
    // Index is always within [0, lastStageIndex] by construction.
    const status = stages[Math.min(stageIndex, lastStageIndex)]!;
    // BUGFIX: this used to divide by stages.length (4), so the final tick
    // (stageIndex === lastStageIndex === 3) produced 75% instead of 100%,
    // leaving the progress bar visibly short even once the badge said
    // "Terminé". Dividing by lastStageIndex makes the first stage 0% and the
    // last stage exactly 100%.
    const progress = Math.min(
      100,
      Math.round((stageIndex / lastStageIndex) * 100)
    );
    const documents = get().documents.map((doc) =>
      doc.id === id ? { ...doc, status, progress } : doc
    );
    set({ documents });

    if (stageIndex < lastStageIndex) {
      setTimeout(tick, 700);
    } else {
      // Document finished processing — record it in the shared history so
      // it shows up in the sidebar (including on this very page) without a
      // manual refresh.
      useHistoryStore.getState().addEntry({
        id: generateId("hist"),
        kind: "document",
        title: name,
        date: new Date().toISOString(),
      });
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
