import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { LangflowCounts } from "../langflow-counts";

type DarkStoreState = {
  stars: number;
  discordCount: number;
};

let mockDarkStoreState: DarkStoreState = {
  stars: 0,
  discordCount: 0,
};

jest.mock("@/stores/darkStore", () => ({
  useDarkStore: (selector: (state: DarkStoreState) => unknown) =>
    selector(mockDarkStoreState),
}));

describe("LangflowCounts", () => {
  beforeEach(() => {
    mockDarkStoreState = { stars: 0, discordCount: 0 };
  });

  it("should_have_no_axe_violations with zero counts", async () => {
    const { container } = render(<LangflowCounts />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations with non-zero counts", async () => {
    mockDarkStoreState = { stars: 42000, discordCount: 1234 };
    const { container } = render(<LangflowCounts />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("exposes accessible names for the GitHub and Discord links via sr-only text", () => {
    render(<LangflowCounts />);

    expect(
      screen.getByRole("button", { name: "Go to GitHub repo" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Go to Discord server" }),
    ).toBeInTheDocument();
  });

  it("hides the numeric star/discord counts from the accessibility tree (surfaced only via sr-only name)", () => {
    mockDarkStoreState = { stars: 42000, discordCount: 1234 };
    render(<LangflowCounts />);

    const starsCount = screen.getByText("42k");
    expect(starsCount).toHaveAttribute("aria-hidden", "true");

    const discordCountEl = screen.getByText("1k");
    expect(discordCountEl).toHaveAttribute("aria-hidden", "true");
  });
});
