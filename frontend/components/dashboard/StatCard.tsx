"use client";

import { useTranslation } from "react-i18next";
import { Clock, FileText, MessageSquare, Smile, TrendingDown, TrendingUp } from "lucide-react";
import Card from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { StatSummary } from "@/types";

const icons = {
  chat: MessageSquare,
  document: FileText,
  smile: Smile,
  clock: Clock,
};

const accentClasses = {
  gold: "bg-gold-300/50 text-gold-600 dark:bg-gold-500/15 dark:text-gold-300",
  forest: "bg-forest-100 text-forest-700 dark:bg-forest-800 dark:text-forest-200",
  sage: "bg-sage-300/50 text-sage-600 dark:bg-sage-500/15 dark:text-sage-300",
  sky: "bg-sky-300/50 text-sky-500 dark:bg-sky-500/15 dark:text-sky-300",
};

export default function StatCard({ stat }: { stat: StatSummary }) {
  const { t } = useTranslation();
  const Icon = icons[stat.icon];
  const DeltaIcon = stat.deltaDirection === "up" ? TrendingUp : TrendingDown;

  return (
    <Card className="p-5">
      <div className="flex items-center gap-2.5 text-sm font-medium text-ink-600 dark:text-sand-300">
        <span
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-lg",
            accentClasses[stat.accent]
          )}
        >
          <Icon size={16} aria-hidden="true" />
        </span>
        {t(stat.labelKey)}
      </div>
      <p className="mt-3 font-display text-3xl font-semibold text-ink-900 dark:text-sand-50">
        {stat.value}
      </p>
      <p
        className={cn(
          "mt-1 flex items-center gap-1 text-xs font-medium",
          stat.deltaDirection === "up"
            ? "text-forest-600 dark:text-forest-300"
            : "text-sky-500 dark:text-sky-300"
        )}
      >
        <DeltaIcon size={13} aria-hidden="true" />
        {t(stat.deltaLabel)}
      </p>
    </Card>
  );
}
