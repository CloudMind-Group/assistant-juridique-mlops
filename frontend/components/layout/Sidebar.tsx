"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslation } from "react-i18next";
import { FileText, LayoutDashboard, MessageSquare, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useHistoryStore } from "@/lib/historyStore";
import { useUiStore } from "@/lib/store";
import { formatDate } from "@/lib/format";

const navItems = [
  { href: "/tableau-de-bord", key: "nav.dashboard", icon: LayoutDashboard },
  { href: "/consultation", key: "nav.consultation", icon: MessageSquare },
  { href: "/analyse-de-contrat", key: "nav.analysis", icon: FileText },
] as const;

const MAX_HISTORY_ITEMS = 6;

function formatHistoryTime(iso: string, locale: string, todayLabel: string): string {
  const date = new Date(iso);
  const now = new Date();
  const isToday =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();

  if (isToday) {
    const time = new Intl.DateTimeFormat(locale === "ar" ? "ar-MA" : "fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
    return `${todayLabel}, ${time}`;
  }
  return formatDate(iso, locale);
}

export default function Sidebar({
  variant = "static",
  onClose,
}: {
  variant?: "static" | "drawer";
  onClose?: () => void;
}) {
  const { t, i18n } = useTranslation();
  const pathname = usePathname();
  const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed);
  const entries = useHistoryStore((s) => s.entries);
  const recentEntries = entries.slice(0, MAX_HISTORY_ITEMS);

  return (
    <nav
      aria-label={t("common.mainNav") ?? undefined}
      className={cn(
        "flex h-full w-72 shrink-0 flex-col border-e border-sand-200 bg-white",
        "dark:border-forest-800 dark:bg-forest-900",
        variant === "static" && "hidden lg:flex",
        sidebarCollapsed && variant === "static" && "lg:w-[76px]"
      )}
    >
      <div className="flex items-center justify-between gap-2 px-5 py-6">
        <Link href="/tableau-de-bord" className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-forest-800 text-white">
            <FileText size={18} aria-hidden="true" />
          </span>
          {!sidebarCollapsed && (
            <span className="font-display text-lg font-semibold text-forest-800 dark:text-sand-50">
              {t("app.name")}
            </span>
          )}
        </Link>
        {variant === "drawer" && (
          <button
            type="button"
            onClick={onClose}
            aria-label={t("common.closeMenu") ?? undefined}
            className="rounded-lg p-2 text-ink-500 hover:bg-sand-100 dark:text-sand-300 dark:hover:bg-forest-800"
          >
            <X size={18} />
          </button>
        )}
      </div>

      <ul className="flex flex-col gap-1 px-3">
        {navItems.map(({ href, key, icon: Icon }) => {
          const active = pathname?.startsWith(href);
          return (
            <li key={href}>
              <Link
                href={href}
                onClick={onClose}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-forest-800 text-white"
                    : "text-ink-600 hover:bg-sand-100 dark:text-sand-200 dark:hover:bg-forest-800"
                )}
              >
                <Icon size={18} aria-hidden="true" className="shrink-0" />
                {!sidebarCollapsed && <span>{t(key)}</span>}
              </Link>
            </li>
          );
        })}
      </ul>

      {!sidebarCollapsed && (
        <div className="mt-8 flex-1 overflow-y-auto px-5 pb-6">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-400 dark:text-sand-400">
            {t("history.title")}
          </h2>
          <ul className="flex flex-col gap-4">
            {recentEntries.map((entry) => {
              const EntryIcon = entry.kind === "consultation" ? MessageSquare : FileText;
              return (
                <li key={entry.id} className="flex items-start gap-2.5">
                  <EntryIcon
                    size={14}
                    className="mt-0.5 shrink-0 text-ink-400 dark:text-sand-500"
                    aria-hidden="true"
                  />
                  <button
                    type="button"
                    className="block min-w-0 flex-1 rounded-lg text-start hover:text-forest-700 dark:hover:text-gold-300"
                  >
                    <p className="truncate text-sm font-medium text-ink-700 dark:text-sand-100">
                      {entry.title}
                    </p>
                    <p className="text-xs text-ink-400 dark:text-sand-400">
                      {formatHistoryTime(entry.date, i18n.language, t("common.today"))}
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </nav>
  );
}
