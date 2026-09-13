"use client";

import StatCard from "@/components/dashboard/StatCard";
import ActivityChart from "@/components/dashboard/ActivityChart";
import StatusDonut from "@/components/dashboard/StatusDonut";
import DocumentsTable from "@/components/dashboard/DocumentsTable";
import ConsultationsHistoryTable from "@/components/dashboard/ConsultationsHistoryTable";
import { statSummaries } from "@/lib/mockData";

export default function DashboardPage() {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {statSummaries.map((stat) => (
          <StatCard key={stat.key} stat={stat} />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ActivityChart />
        <StatusDonut />
      </div>

      <DocumentsTable />
      <ConsultationsHistoryTable />
    </div>
  );
}
