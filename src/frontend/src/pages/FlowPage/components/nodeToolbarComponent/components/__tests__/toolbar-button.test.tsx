import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { ToolbarButton } from "../toolbar-button";

jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

jest.mock("../../shortcutDisplay", () => ({
  __esModule: true,
  default: ({ name }: { name?: string }) => <span>{name}</span>,
}));

describe("ToolbarButton", () => {
  it("uses the visible label as its accessible name", () => {
    render(<ToolbarButton icon="FileText" label="Docs" onClick={jest.fn()} />);

    expect(screen.getByRole("button", { name: "Docs" })).toBeInTheDocument();
  });

  it("falls back to the shortcut name for icon-only actions", () => {
    render(
      <ToolbarButton
        icon="Snowflake"
        shortcut={{ name: "Freeze", shortcut: "F" }}
        onClick={jest.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Freeze" })).toBeInTheDocument();
  });
});
