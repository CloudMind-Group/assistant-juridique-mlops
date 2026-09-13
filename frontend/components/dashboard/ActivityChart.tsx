"use client";

import { useTranslation } from "react-i18next";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";
import Card from "@/components/ui/Card";
import { activitySeries } from "@/lib/mockData";

const tickDays = [6, 11, 16, 21, 26];

export default function ActivityChart() {
  const { t } = useTranslation();

  return (
    <Card className="col-span-1 p-5 lg:col-span-2">
      <h2 className="font-display text-base font-semibold text-ink-900 dark:text-sand-50">
        {t("dashboard.activity.title")}
      </h2>
      <div className="mt-4 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={activitySeries} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="activityFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#193826" stopOpacity={0.16} />
                <stop offset="100%" stopColor="#193826" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="day"
              ticks={tickDays}
              type="number"
              domain={["dataMin", "dataMax"]}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#7b8279", fontSize: 12 }}
              dy={8}
            />
            <Tooltip
              cursor={{ stroke: "#d3cbb4", strokeWidth: 1 }}
              contentStyle={{
                borderRadius: 10,
                border: "1px solid #e4e0d2",
                fontSize: 12,
              }}
              labelFormatter={(day) => t("dashboard.activity.dayLabel", { day })}
              formatter={(value: number) => [value, t("dashboard.activity.title")]}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#193826"
              strokeWidth={2}
              fill="url(#activityFill)"
              isAnimationActive
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
