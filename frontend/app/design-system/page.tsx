"use client";

import { useTranslation } from "react-i18next";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";

const swatches = [
  { name: "forest-800", className: "bg-forest-800", hex: "#193826" },
  { name: "forest-600", className: "bg-forest-600", hex: "#26543a" },
  { name: "gold-500", className: "bg-gold-500", hex: "#cf9440" },
  { name: "sage-500", className: "bg-sage-500", hex: "#6c8874" },
  { name: "sky-400", className: "bg-sky-400", hex: "#93b7c7" },
  { name: "clay-500", className: "bg-clay-500", hex: "#b5473f" },
  { name: "sand-100", className: "bg-sand-100 border border-sand-300", hex: "#f1efe7" },
  { name: "ink-900", className: "bg-ink-900", hex: "#1a1f19" },
];

export default function DesignSystemPage() {
  const { t } = useTranslation();

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-8">
      <p className="text-sm text-ink-500 dark:text-sand-400">{t("designSystem.subtitle")}</p>

      <Card className="p-6">
        <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-sand-50">
          {t("designSystem.colors")}
        </h2>
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {swatches.map((s) => (
            <div key={s.name}>
              <div className={`h-16 rounded-xl ${s.className}`} />
              <p className="mt-2 text-xs font-medium text-ink-700 dark:text-sand-200">{s.name}</p>
              <p className="text-xs text-ink-400 dark:text-sand-500">{s.hex}</p>
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-6">
        <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-sand-50">
          {t("designSystem.typography")}
        </h2>
        <div className="mt-4 space-y-3">
          <p className="font-display text-3xl font-semibold text-ink-900 dark:text-sand-50">
            Tableau de bord — Source Serif 4
          </p>
          <p className="font-display text-xl font-semibold text-ink-800 dark:text-sand-100">
            Titre de section — 20px / 600
          </p>
          <p className="text-base text-ink-700 dark:text-sand-200">
            Texte courant — Inter 16px, utilisé pour les paragraphes et le contenu des cartes.
          </p>
          <p className="text-sm text-ink-500 dark:text-sand-400">
            Texte secondaire — Inter 14px, pour les métadonnées et les légendes.
          </p>
        </div>
      </Card>

      <Card className="p-6">
        <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-sand-50">
          {t("designSystem.buttons")}
        </h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <Button variant="primary">Primaire</Button>
          <Button variant="secondary">Secondaire</Button>
          <Button variant="ghost">Discret</Button>
          <Button variant="primary" disabled>
            Désactivé
          </Button>
        </div>
      </Card>

      <Card className="p-6">
        <h2 className="font-display text-lg font-semibold text-ink-900 dark:text-sand-50">
          {t("designSystem.badges")}
        </h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <Badge tone="success">Terminé</Badge>
          <Badge tone="warning">OCR en cours</Badge>
          <Badge tone="danger">Échec</Badge>
          <Badge tone="neutral">En attente</Badge>
          <Badge tone="info">En révision</Badge>
        </div>
      </Card>
    </div>
  );
}
