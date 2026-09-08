export function formatDate(isoDate: string, locale: string): string {
  const date = new Date(isoDate);
  const localeTag = locale === "ar" ? "ar-MA" : "fr-FR";
  return new Intl.DateTimeFormat(localeTag, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}
