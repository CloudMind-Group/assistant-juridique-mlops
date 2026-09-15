import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Badge from "@/components/ui/Badge";

describe("Badge", () => {
  it("renders its label", () => {
    render(<Badge tone="success">Terminé</Badge>);
    expect(screen.getByText("Terminé")).toBeInTheDocument();
  });

  it("applies a different tone class per status", () => {
    const { rerender } = render(<Badge tone="danger">Échec</Badge>);
    expect(screen.getByText("Échec").className).toMatch(/clay/);

    rerender(<Badge tone="neutral">En attente</Badge>);
    expect(screen.getByText("En attente").className).toMatch(/sand|ink/);
  });
});
