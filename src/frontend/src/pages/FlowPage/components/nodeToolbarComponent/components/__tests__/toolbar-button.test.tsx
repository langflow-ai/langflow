import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { axe } from "@/utils/a11y-test";
import { ToolbarButton } from "../toolbar-button";

let lastShadTooltipProps: Record<string, unknown> = {};

jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({
    children,
    ...props
  }: {
    children: ReactNode;
    [key: string]: unknown;
  }) => {
    lastShadTooltipProps = props;
    return <>{children}</>;
  },
}));

jest.mock("../../shortcutDisplay", () => ({
  __esModule: true,
  default: ({ name }: { name?: string }) => <span>{name}</span>,
}));

describe("ToolbarButton", () => {
  beforeEach(() => {
    lastShadTooltipProps = {};
  });

  it("should_have_no_axe_violations with a label", async () => {
    const { container } = render(
      <ToolbarButton icon="FileText" label="Docs" onClick={jest.fn()} />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations icon-only with a shortcut", async () => {
    const { container } = render(
      <ToolbarButton
        icon="Snowflake"
        shortcut={{ name: "Freeze", shortcut: "F" }}
        onClick={jest.fn()}
      />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

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

  it("always suppresses the tooltip's aria-describedby, since the visible label/aria-label already covers the button's name", () => {
    render(<ToolbarButton icon="FileText" label="Docs" onClick={jest.fn()} />);

    expect("ariaDescribedBy" in lastShadTooltipProps).toBe(true);
    expect(lastShadTooltipProps.ariaDescribedBy).toBeUndefined();
  });

  it("also suppresses aria-describedby when a shortcut is shown", () => {
    render(
      <ToolbarButton
        icon="Snowflake"
        shortcut={{ name: "Freeze", shortcut: "F" }}
        onClick={jest.fn()}
      />,
    );

    expect("ariaDescribedBy" in lastShadTooltipProps).toBe(true);
    expect(lastShadTooltipProps.ariaDescribedBy).toBeUndefined();
  });
});
