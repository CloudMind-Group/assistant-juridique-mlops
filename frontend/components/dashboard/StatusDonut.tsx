"use client";

import { useTranslation } from "react-i18next";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import Card from "@/components/ui/Card";
import { documentStatusSegments } from "@/lib/mockData";

export default function StatusDonut() {
  const { t } = useTranslation();

  return (
    <Card className="p-5">
      <h2 className="font-display text-base font-semibold text-ink-900 dark:text-sand-50">
        {t("dashboard.status.title")}
      </h2>
      <div className="mt-2 flex items-center gap-4">
        <div className="h-40 w-40 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={documentStatusSegments}
                dataKey="value"
                nameKey="key"
                innerRadius={48}
                outerRadius={72}
                paddingAngle={2}
                startAngle={90}
                endAngle={-270}
                stroke="none"
              >
                {documentStatusSegments.map((segment) => (
                  <Cell key={segment.key} fill={segment.color} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <ul className="flex-1 space-y-2.5">
          {documentStatusSegments.map((segment) => (
            <li key={segment.key} className="flex items-center gap-2 text-sm">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: segment.color }}
                aria-hidden="true"
              />
              <span className="flex-1 text-ink-600 dark:text-sand-300">
                {t(segment.labelKey)}
              </span>
              <span className="font-medium text-ink-900 dark:text-sand-50">
                {segment.value}
              </span>
              <span className="w-9 text-end text-ink-400 dark:text-sand-400">
                {segment.percent}%
              </span>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}
