"use client";

import { usePathname } from "next/navigation";
import { useTranslation } from "react-i18next";
import {
  ChevronDown,
  Languages,
  Menu,
  Moon,
  RefreshCw,
  Sun,
} from "lucide-react";
import Button from "@/components/ui/Button";
import { useUiStore } from "@/lib/store";

const titleByPath: Record<string, string> = {
  "/tableau-de-bord": "dashboard.title",
  "/consultation": "consultation.title",
  "/analyse-de-contrat": "analysis.title",
  "/design-system": "designSystem.title",
};

export default function Topbar({ onOpenMenu }: { onOpenMenu: () => void }) {
  const { t } = useTranslation();
  const pathname = usePathname();
  const theme = useUiStore((s) => s.theme);
  const toggleTheme = useUiStore((s) => s.toggleTheme);
  const locale = useUiStore((s) => s.locale);
  const setLocale = useUiStore((s) => s.setLocale);

  const titleKey =
    Object.entries(titleByPath).find(([path]) => pathname?.startsWith(path))?.[1] ??
    "dashboard.title";

  return (
    <header className="flex items-center justify-between gap-3 border-b border-sand-200 bg-white/80 px-5 py-4 backdrop-blur dark:border-forest-800 dark:bg-forest-950/80 sm:px-8">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onOpenMenu}
          aria-label="Ouvrir le menu de navigation"
          className="rounded-lg p-2 text-ink-600 hover:bg-sand-100 dark:text-sand-200 dark:hover:bg-forest-800 lg:hidden"
        >
          <Menu size={20} />
        </button>
        <h1 className="font-display text-2xl font-semibold text-forest-800 dark:text-sand-50">
          {t(titleKey)}
        </h1>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className="hidden items-center gap-2 rounded-lg border border-sand-300 bg-white px-3 py-2 text-sm text-ink-600 hover:bg-sand-50 dark:border-forest-700 dark:bg-forest-900 dark:text-sand-200 dark:hover:bg-forest-800 sm:flex"
        >
          {t("app.range30")}
          <ChevronDown size={16} aria-hidden="true" />
        </button>

        <Button variant="secondary" size="md" className="hidden sm:inline-flex">
          <RefreshCw size={16} aria-hidden="true" />
          {t("app.refresh")}
        </Button>

        <button
          type="button"
          onClick={() => setLocale(locale === "fr" ? "ar" : "fr")}
          aria-label={t("common.toggleLanguage") ?? "Changer de langue"}
          className="flex h-10 w-10 items-center justify-center rounded-lg border border-sand-300 text-ink-600 hover:bg-sand-50 dark:border-forest-700 dark:text-sand-200 dark:hover:bg-forest-800"
        >
          <Languages size={18} aria-hidden="true" />
        </button>

        <button
          type="button"
          onClick={toggleTheme}
          aria-label={t("common.toggleTheme") ?? "Changer de thème"}
          className="flex h-10 w-10 items-center justify-center rounded-lg border border-sand-300 text-ink-600 hover:bg-sand-50 dark:border-forest-700 dark:text-sand-200 dark:hover:bg-forest-800"
        >
          {theme === "light" ? (
            <Moon size={18} aria-hidden="true" />
          ) : (
            <Sun size={18} aria-hidden="true" />
          )}
        </button>
      </div>
    </header>
  );
}
