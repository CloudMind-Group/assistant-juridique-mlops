import type { ChatMessage, SourceCitation } from "@/types";
import { generateId } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Wire shape returned by the real backend (M5, /chat — Nouhaila), confirmed
// against her branch on 2026-09-xx:
//
// {
//   "answer": "Selon l'article 230 du DOC, les obligations...",
//   "citations": [{ doc_id, chunk_id, title, source, date, category,
//                    language, excerpt, score }],
//   "refused": false,
//   "from_cache": false
// }
//
// Nothing outside this file should import these Api* types or call the
// backend directly. Every component consumes ChatMessage / SourceCitation
// (types/index.ts), which are stable regardless of what the API looks like.
// When M5 is merged, only fetchChatReply's body needs to change — the
// mapping and every component downstream of it stay untouched.
// ---------------------------------------------------------------------------

export interface ApiCitation {
  doc_id: string;
  chunk_id: string;
  title: string;
  source: string;
  date: string;
  category: string;
  language: string;
  excerpt: string;
  score: number;
}

export interface ApiChatResponse {
  answer: string;
  citations: ApiCitation[];
  refused: boolean;
  from_cache: boolean;
}

function mapCitation(citation: ApiCitation): SourceCitation {
  return {
    id: citation.chunk_id,
    label: citation.title,
    excerpt: citation.excerpt,
    // TODO(issue #76 — waiting on Iman): confirm whether a legal reader
    // needs "title + date" here or the raw doc_id. Using title + date for
    // now since it's the readable option and doesn't block the merge.
    reference: `${citation.title} — ${citation.date}`,
  };
}

export function mapChatResponse(response: ApiChatResponse): ChatMessage {
  return {
    id: generateId("msg"),
    role: "assistant",
    content: response.answer,
    sources: response.citations.map(mapCitation),
    refused: response.refused,
    feedback: null,
    createdAt: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Mock transport — matches the exact shape above. Replace the body of this
// function with a real `fetch("/api/chat", { method: "POST", ... })` once M5
// is merged. mapChatResponse and every UI component stay exactly as they are.
// ---------------------------------------------------------------------------
export async function fetchChatReply(question: string): Promise<ApiChatResponse> {
  await new Promise((resolve) => setTimeout(resolve, 900));

  const isOutOfScope = /météo|recette|sport|football/i.test(question);
  if (isOutOfScope) {
    return {
      answer:
        "Cette question sort du périmètre de l'assistant, qui se limite au conseil juridique documentaire. Reformulez votre question autour d'un contrat, d'un texte de loi ou d'une clause spécifique.",
      citations: [],
      refused: true,
      from_cache: false,
    };
  }

  return {
    answer:
      "Selon l'article 230 du DOC, les obligations contractuelles valablement formées tiennent lieu de loi à ceux qui les ont faites et ne peuvent être révoquées que de leur consentement mutuel, ou pour les causes que la loi autorise. La clause de responsabilité analysée reste donc opposable sauf faute lourde ou dol.",
    citations: [
      {
        doc_id: "bo-dahir-65-99-art230",
        chunk_id: generateId("chunk"),
        title: "Dahir des Obligations et Contrats — article 230",
        source: "Bulletin Officiel",
        date: "1913-08-12",
        category: "code",
        language: "fr",
        excerpt: "Les obligations contractuelles valablement formées...",
        score: 0.87,
      },
      {
        doc_id: "contrat-nexus-sas-art9",
        chunk_id: generateId("chunk"),
        title: "Contrat Nexus SAS — Prestation Q3.pdf, art. 9",
        source: "Documents analysés",
        date: "2026-09-08",
        category: "contrat",
        language: "fr",
        excerpt:
          "La responsabilité du Prestataire est limitée, tous préjudices confondus, au montant des sommes versées…",
        score: 0.81,
      },
    ],
    refused: false,
    from_cache: false,
  };
}
