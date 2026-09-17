"use client";

import { useTranslation } from "react-i18next";
import { CheckCircle2, FileText, XCircle } from "lucide-react";
import Card from "@/components/ui/Card";
import { useUploadStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const barColor: Record<string, string> = {
  en_telechargement: "bg-sky-400",
  ocr: "bg-gold-400",
  analyse: "bg-forest-500",
  termine: "bg-forest-600",
  echec: "bg-clay-500",
};

export default function ProcessingStatusList() {
  const { t } = useTranslation();
  const documents = useUploadStore((s) => s.documents);

  if (documents.length === 0) return null;

  return (
    <Card className="mt-6 p-5">
      <h2 className="font-display text-base font-semibold text-ink-900 dark:text-sand-50">
        {t("analysis.queueTitle")}
      </h2>
      <ul className="mt-4 space-y-4">
        {documents.map((doc) => (
          <li key={doc.id} className="flex items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sand-100 text-ink-400 dark:bg-forest-800 dark:text-sand-400">
              {doc.status === "termine" ? (
                <CheckCircle2 size={18} className="text-forest-600" />
              ) : doc.status === "echec" ? (
                <XCircle size={18} className="text-clay-500" />
              ) : (
                <FileText size={18} />
              )}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-sm font-medium text-ink-800 dark:text-sand-100">
                  {doc.name}
                </p>
                <span className="shrink-0 text-xs text-ink-400 dark:text-sand-400">
                  {doc.sizeLabel}
                </span>
              </div>
              <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-sand-100 dark:bg-forest-800">
                <div
                  className={cn("h-full rounded-full transition-all", barColor[doc.status])}
                  style={{ width: `${doc.progress}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-ink-500 dark:text-sand-400">
                {t(`analysis.status.${doc.status}`)}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
