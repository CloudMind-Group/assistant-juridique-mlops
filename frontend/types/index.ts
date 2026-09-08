export type Locale = "fr" | "ar";

export type Theme = "light" | "dark";

export type DocumentStatus =
  | "termine"
  | "ocr_en_cours"
  | "echec"
  | "en_attente"
  | "en_cours"
  | "en_revision"
  | "approuve"
  | "rejete";

export interface AnalyzedDocument {
  id: string;
  name: string;
  date: string;
  status: DocumentStatus;
}

export interface ConsultationHistoryEntry {
  id: string;
  question: string;
  date: string;
  feedback: "up" | "down" | null;
}

export interface SourceCitation {
  id: string;
  label: string;
  excerpt: string;
  reference: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceCitation[];
  feedback?: "up" | "down" | null;
  streaming?: boolean;
  createdAt: string;
}

export interface UploadedDocument {
  id: string;
  name: string;
  sizeLabel: string;
  progress: number;
  status: "en_telechargement" | "ocr" | "analyse" | "termine" | "echec";
}

export interface StatSummary {
  key: string;
  labelKey: string;
  value: string;
  deltaLabel: string;
  deltaDirection: "up" | "down";
  icon: "chat" | "document" | "smile" | "clock";
  accent: "gold" | "forest" | "sage" | "sky";
}

export interface DonutSegment {
  key: DocumentStatus;
  labelKey: string;
  value: number;
  percent: number;
  color: string;
}
