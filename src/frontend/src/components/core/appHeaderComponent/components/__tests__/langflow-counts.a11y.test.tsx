import { render, screen } from "@testing-library/react";
import { LangflowCounts } from "../langflow-counts";

jest.mock("@/stores/darkStore", () => ({
  useDarkStore: (
    selector: (s: { stars: number; discordCount: number }) => unknown,
  ) => selector({ stars: 1234, discordCount: 5678 }),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        "header.goToGithub": "Go to GitHub repo",
        "header.goToDiscord": "Go to Discord server",
      };
      return map[key] ?? key;
    },
  }),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/utils/utils", () => ({
  formatNumber: (n: number) => String(n),
  cn: (...classes: (string | undefined | null | false)[]) =>
    classes.filter(Boolean).join(" "),
}));

jest.mock("@/shared/components/caseComponent", () => ({
  Case: ({
    condition,
    children,
  }: {
    condition: boolean;
    children: React.ReactNode;
  }) => (condition ? <>{children}</> : null),
}));

describe("LangflowCounts accessibility", () => {
  beforeEach(() => {
    render(<LangflowCounts />);
  });

  it("should_expose_github_button_with_accessible_name", () => {
    expect(
      screen.getByRole("button", { name: /go to github repo/i }),
    ).toBeInTheDocument();
  });

  it("should_expose_discord_button_with_accessible_name", () => {
    expect(
      screen.getByRole("button", { name: /go to discord server/i }),
    ).toBeInTheDocument();
  });

  it("should_hide_github_icon_from_assistive_technology", () => {
    const githubButton = screen.getByRole("button", {
      name: /go to github repo/i,
    });
    const svg = githubButton.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
  });

  it("should_hide_discord_icon_from_assistive_technology", () => {
    const discordButton = screen.getByRole("button", {
      name: /go to discord server/i,
    });
    const svg = discordButton.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
  });
});
