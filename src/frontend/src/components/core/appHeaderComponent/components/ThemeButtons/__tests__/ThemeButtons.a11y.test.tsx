import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { ThemeButtons } from "..";

describe("ThemeButtons accessibility", () => {
  it("has no detectable axe violations", async () => {
    const { container } = render(<ThemeButtons />);

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  it("names the light, dark, and system theme buttons", () => {
    render(<ThemeButtons />);

    expect(
      screen.getByRole("button", { name: "Light theme" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Dark theme" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "System theme" }),
    ).toBeInTheDocument();
  });
});
