import { cn } from "@/lib/utils";

export default function Card({
  className,
  children,
  as: Tag = "div",
}: {
  className?: string;
  children: React.ReactNode;
  as?: keyof JSX.IntrinsicElements;
}) {
  const Component = Tag as React.ElementType;
  return (
    <Component
      className={cn(
        "rounded-2xl border border-sand-200 bg-white shadow-card",
        "dark:border-forest-800 dark:bg-forest-900",
        className
      )}
    >
      {children}
    </Component>
  );
}
