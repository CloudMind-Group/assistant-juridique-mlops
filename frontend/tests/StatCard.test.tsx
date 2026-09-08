import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import StatCard from "@/components/dashboard/StatCard";
import { statSummaries } from "@/lib/mockData";

describe("StatCard", () => {
  it("renders the consultations KPI with its value and delta", () => {
    const stat = statSummaries.find((s) => s.key === "consultations")!;
    render(<StatCard stat={stat} />);

    expect(screen.getByText("128")).toBeInTheDocument();
    expect(screen.getByText(/12%/)).toBeInTheDocument();
  });

  it("renders the satisfaction KPI as a percentage", () => {
    const stat = statSummaries.find((s) => s.key === "satisfaction")!;
    render(<StatCard stat={stat} />);

    expect(screen.getByText("87%")).toBeInTheDocument();
  });
});
