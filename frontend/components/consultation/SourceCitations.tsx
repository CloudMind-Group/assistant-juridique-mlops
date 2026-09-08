"use client";

import { useTranslation } from "react-i18next";
import { Quote } from "lucide-react";
import type { SourceCitation } from "@/types";

export default function SourceCitations({ sources }: { sources: SourceCitation[] }) {
  const { t } = useTranslation();

  if (sources.length === 0) return null;

  return (
    <div className="mt-3 space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-400 dark:text-sand-400">
        {t("consultation.sourcesLabel")}
      </p>
      <ul className="space-y-2">
        {sources.map((source) => (
          <li
            key={source.id}
            className="rounded-xl border border-sand-200 bg-sand-50 p-3 text-sm dark:border-forest-800 dark:bg-forest-800/60"
          >
            <div className="flex items-start gap-2">
              <Quote size={14} className="mt-0.5 shrink-0 text-gold-500" aria-hidden="true" />
              <div>
                <p className="font-medium text-ink-800 dark:text-sand-100">
                  {source.label}
                </p>
                <p className="mt-1 italic text-ink-500 dark:text-sand-400">
                  {source.excerpt}
                </p>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
