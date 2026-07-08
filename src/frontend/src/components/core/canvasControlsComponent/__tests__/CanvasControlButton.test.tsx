import { render, screen } from "@testing-library/react";
import type { ComponentProps, ReactNode } from "react";
import CanvasControlButton from "../CanvasControlButton";

// ControlButton renders the real DOM <button> and spreads its props, so we can
// assert exactly which attributes (title / aria-label) reach the element.
jest.mock("@xyflow/react", () => ({
  ControlButton: ({ children, ...props }: ComponentProps<"button">) => (
    <button type="button" {...props}>
      {children}
    </button>
  ),
}));

// ShadTooltip is the single, styled tooltip — expose its content so we can
// confirm the button's label is surfaced through it (and only it).
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({
    content,
    children,
  }: {
    content?: string;
    children?: ReactNode;
  }) => (
    <div data-testid="shad-tooltip" data-content={content}>
      {children}
    </div>
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name?: string }) => (
    <div data-testid={`icon-${name}`} />
  ),
}));

// Regression coverage for the duplicate sidebar tooltip bug: the control nav
// buttons rendered BOTH a native `title` attribute and a ShadTooltip, so
// hovering surfaced two tooltips at once (one of them exposing a raw i18n key).
describe("CanvasControlButton — single tooltip (no native title)", () => {
  const setup = () =>
    render(
      <CanvasControlButton
        iconName="blocks"
        tooltipText="Bundles"
        onClick={jest.fn()}
        testId="bundles"
      />,
    );

  it("does not render a native title attribute (would be a second tooltip)", () => {
    setup();
    const button = screen.getByRole("button");
    expect(button).not.toHaveAttribute("title");
  });

  it("exposes the label via aria-label and the ShadTooltip, not a raw key", () => {
    setup();
    expect(screen.getByRole("button")).toHaveAttribute("aria-label", "Bundles");
    expect(screen.getByTestId("shad-tooltip")).toHaveAttribute(
      "data-content",
      "Bundles",
    );
  });
});
