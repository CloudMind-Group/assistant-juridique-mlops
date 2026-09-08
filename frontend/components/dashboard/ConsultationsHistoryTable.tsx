"use client";

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Download, Search, ThumbsDown, ThumbsUp } from "lucide-react";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { consultationHistory } from "@/lib/mockData";
import { formatDate } from "@/lib/format";

export default function ConsultationsHistoryTable() {
  const { t, i18n } = useTranslation();
  const [query, setQuery] = useState("");

  const filtered = useMemo(
    () =>
      consultationHistory.filter((entry) =>
        entry.question.toLowerCase().includes(query.toLowerCase())
      ),
    [query]
  );

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-base font-semibold text-ink-900 dark:text-sand-50">
          {t("dashboard.historyTable.title")}
        </h2>
        <div className="relative">
          <Search
            size={16}
            className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-ink-400"
            aria-hidden="true"
          />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("dashboard.historyTable.search") ?? undefined}
            className="h-9 w-56 rounded-lg border border-sand-300 bg-white ps-9 pe-3 text-sm text-ink-700 outline-none placeholder:text-ink-400 focus:border-forest-500 dark:border-forest-700 dark:bg-forest-900 dark:text-sand-100"
          />
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-sand-200 text-start text-xs uppercase tracking-wide text-ink-400 dark:border-forest-800 dark:text-sand-400">
              <th className="py-2 text-start font-medium">
                {t("dashboard.historyTable.columnQuestion")}
              </th>
              <th className="py-2 text-start font-medium">
                {t("dashboard.historyTable.columnDate")}
              </th>
              <th className="py-2 text-start font-medium">
                {t("dashboard.historyTable.columnFeedback")}
              </th>
              <th className="py-2 text-start font-medium">
                {t("dashboard.historyTable.columnExport")}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((entry) => (
              <tr
                key={entry.id}
                className="border-b border-sand-100 last:border-0 dark:border-forest-800/60"
              >
                <td className="max-w-xs truncate py-3 pe-3 font-medium text-ink-800 dark:text-sand-100">
                  {entry.question}
                </td>
                <td className="py-3 pe-3 text-ink-500 dark:text-sand-400">
                  {formatDate(entry.date, i18n.language)}
                </td>
                <td className="py-3 pe-3">
                  {entry.feedback === "up" && (
                    <ThumbsUp
                      size={16}
                      className="text-forest-600 dark:text-forest-300"
                      aria-label="Retour positif"
                    />
                  )}
                  {entry.feedback === "down" && (
                    <ThumbsDown
                      size={16}
                      className="text-clay-500"
                      aria-label="Retour négatif"
                    />
                  )}
                </td>
                <td className="py-3">
                  <Button variant="secondary" size="sm">
                    <Download size={14} aria-hidden="true" />
                    {t("dashboard.historyTable.exportPdf")}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
