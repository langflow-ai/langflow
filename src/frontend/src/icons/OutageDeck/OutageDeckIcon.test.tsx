import { render, screen } from "@testing-library/react";

import { OutageDeckIcon } from "./index";

const fills = () =>
  [
    ...screen
      .getByRole("img", { name: "OutageDeck" })
      .querySelectorAll("rect, circle"),
  ].map((shape) => shape.getAttribute("fill"));

describe("OutageDeckIcon", () => {
  it("renders the light-theme palette and forwards SVG attributes", () => {
    render(<OutageDeckIcon className="provider-icon" />);

    expect(screen.getByRole("img", { name: "OutageDeck" })).toHaveClass(
      "provider-icon",
    );
    expect(fills()).toEqual([
      "#111827",
      "#FFFFFF",
      "#34D399",
      "#94A3B8",
      "#64748B",
    ]);
  });

  it("renders the dark-theme palette without forwarding isDark to the DOM", () => {
    render(<OutageDeckIcon isDark />);

    const icon = screen.getByRole("img", { name: "OutageDeck" });
    expect(icon).not.toHaveAttribute("isDark");
    expect(fills()).toEqual([
      "#F8FAFC",
      "#0F172A",
      "#10B981",
      "#475569",
      "#64748B",
    ]);
  });
});
