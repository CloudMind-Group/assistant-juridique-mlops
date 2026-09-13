import { cn } from "@/lib/utils";

export type BadgeTone = "success" | "warning" | "danger" | "neutral" | "info";

const toneClasses: Record<BadgeTone, string> = {
  success:
    "bg-forest-100 text-forest-700 dark:bg-forest-800 dark:text-forest-100",
  warning: "bg-gold-300/60 text-gold-600 dark:bg-gold-500/20 dark:text-gold-300",
  danger: "bg-clay-400/15 text-clay-600 dark:bg-clay-500/20 dark:text-clay-400",
  neutral: "bg-sand-200 text-ink-600 dark:bg-forest-800 dark:text-sand-200",
  info: "bg-sky-300/40 text-sky-500 dark:bg-sky-500/20 dark:text-sky-300",
};

export default function Badge({
  tone = "neutral",
  children,
}: {
  tone?: BadgeTone;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium",
        toneClasses[tone]
      )}
    >
      {children}
    </span>
  );
}
