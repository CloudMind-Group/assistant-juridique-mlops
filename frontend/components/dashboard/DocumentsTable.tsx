"use client";

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Search } from "lucide-react";
import Card from "@/components/ui/Card";
import Badge, { type BadgeTone } from "@/components/ui/Badge";
import { analyzedDocuments } from "@/lib/mockData";
import { formatDate } from "@/lib/format";

const statusTone: Record<string, BadgeTone> = {
  termine: "success",
  ocr_en_cours: "warning",
  echec: "danger",
  en_attente: "neutral",
};

export default function DocumentsTable() {
  const { t, i18n } = useTranslation();
  const [query, setQuery] = useState("");

  const filtered = useMemo(
    () =>
      analyzedDocuments.filter((doc) =>
        doc.name.toLowerCase().includes(query.toLowerCase())
      ),
    [query]
  );

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-base font-semibold text-ink-900 dark:text-sand-50">
          {t("dashboard.documentsTable.title")}
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
            placeholder={t("dashboard.documentsTable.search") ?? undefined}
            className="h-9 w-56 rounded-lg border border-sand-300 bg-white ps-9 pe-3 text-sm text-ink-700 outline-none placeholder:text-ink-400 focus:border-forest-500 dark:border-forest-700 dark:bg-forest-900 dark:text-sand-100"
          />
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[480px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-sand-200 text-start text-xs uppercase tracking-wide text-ink-400 dark:border-forest-800 dark:text-sand-400">
              <th className="py-2 text-start font-medium">
                {t("dashboard.documentsTable.columnDocument")}
              </th>
              <th className="py-2 text-start font-medium">
                {t("dashboard.documentsTable.columnDate")}
              </th>
              <th className="py-2 text-start font-medium">
                {t("dashboard.documentsTable.columnStatus")}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((doc) => (
              <tr
                key={doc.id}
                className="border-b border-sand-100 last:border-0 dark:border-forest-800/60"
              >
                <td className="py-3 pe-3 font-medium text-ink-800 dark:text-sand-100">
                  {doc.name}
                </td>
                <td className="py-3 pe-3 text-ink-500 dark:text-sand-400">
                  {formatDate(doc.date, i18n.language)}
                </td>
                <td className="py-3">
                  <Badge tone={statusTone[doc.status] ?? "neutral"}>
                    {t(`dashboard.statusLabels.${doc.status}`)}
                  </Badge>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={3} className="py-6 text-center text-ink-400">
                  —
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
