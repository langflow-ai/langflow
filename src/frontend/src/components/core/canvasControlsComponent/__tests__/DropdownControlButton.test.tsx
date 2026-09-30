import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
} from "@/components/ui/dropdown-menu";
import { axe } from "@/utils/a11y-test";
import DropdownControlButton from "../DropdownControlButton";

// Mock dependencies
jest.mock("@/components/common/genericIconComponent", () => {
  const MockIcon = ({
    name,
    className,
  }: {
    name: string;
    className: string;
  }) => <span data-testid={`icon-${name}`} className={className} />;
  return {
    __esModule: true,
    default: MockIcon,
    ForwardedIconComponent: MockIcon,
  };
});

jest.mock("@/utils/utils", () => ({
  cn: (...args: (string | undefined | null | boolean)[]) =>
    args.filter(Boolean).join(" "),
}));

jest.mock("../utils/canvasUtils", () => ({
  getModifierKey: jest.fn(() => "⌘"),
}));

// DropdownMenuItem/DropdownMenuCheckboxItem are real Radix menu primitives —
// they require a real DropdownMenu/DropdownMenuContent ancestor to work, so
// every render here goes through that context (kept open so the content is
// actually mounted).
const renderInMenu = (ui: ReactNode) =>
  render(
    <DropdownMenu open>
      <DropdownMenuContent>{ui}</DropdownMenuContent>
    </DropdownMenu>,
  );

describe("DropdownControlButton", () => {
  const defaultProps = {
    testId: "test-button",
    label: "Test Button",
    onClick: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_have_no_axe_violations as a plain menuitem", async () => {
    const { container } = renderInMenu(
      <DropdownControlButton {...defaultProps} iconName="test-icon" />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations as a menuitemcheckbox (the previously-nested toggle)", async () => {
    const { container } = renderInMenu(
      <DropdownControlButton
        {...defaultProps}
        hasToogle={true}
        toggleValue={true}
      />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("renders as a menuitem with the label", () => {
    renderInMenu(<DropdownControlButton {...defaultProps} />);

    const item = screen.getByTestId("test-button");
    expect(item).toBeInTheDocument();
    expect(item).toHaveAttribute("role", "menuitem");
    expect(screen.getByText("Test Button")).toBeInTheDocument();
  });

  it("calls onClick handler when clicked", () => {
    const mockOnClick = jest.fn();
    renderInMenu(
      <DropdownControlButton {...defaultProps} onClick={mockOnClick} />,
    );

    fireEvent.click(screen.getByTestId("test-button"));
    expect(mockOnClick).toHaveBeenCalledTimes(1);
  });

  it("renders with icon when iconName is provided", () => {
    renderInMenu(
      <DropdownControlButton {...defaultProps} iconName="test-icon" />,
    );

    expect(screen.getByTestId("icon-test-icon")).toBeInTheDocument();
  });

  it("displays shortcut with modifier key", () => {
    renderInMenu(<DropdownControlButton {...defaultProps} shortcut="+" />);

    expect(screen.getByText("⌘")).toBeInTheDocument();
    expect(screen.getByText("+")).toBeInTheDocument();
  });

  it("applies disabled state correctly", () => {
    renderInMenu(<DropdownControlButton {...defaultProps} disabled />);

    const item = screen.getByTestId("test-button");
    expect(item).toHaveAttribute("aria-disabled", "true");
  });

  it("exposes an accessible name via aria-label (and title as a hover hint)", () => {
    const tooltipText = "This is a tooltip";
    renderInMenu(
      <DropdownControlButton {...defaultProps} tooltipText={tooltipText} />,
    );

    const item = screen.getByTestId("test-button");
    expect(item).toHaveAttribute("aria-label", tooltipText);
    expect(item).toHaveAttribute("title", tooltipText);
  });

  it("renders as a menuitemcheckbox reflecting the toggle state when hasToogle is true", () => {
    renderInMenu(
      <DropdownControlButton
        {...defaultProps}
        hasToogle={true}
        toggleValue={true}
      />,
    );

    const item = screen.getByTestId("test-button");
    expect(item).toHaveAttribute("role", "menuitemcheckbox");
    expect(item).toHaveAttribute("aria-checked", "true");
  });

  it("reflects an unchecked toggle state", () => {
    renderInMenu(
      <DropdownControlButton
        {...defaultProps}
        hasToogle={true}
        toggleValue={false}
      />,
    );

    expect(screen.getByTestId("test-button")).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("calls onClick (via onCheckedChange) when the toggle item is activated", () => {
    const mockOnClick = jest.fn();
    renderInMenu(
      <DropdownControlButton
        {...defaultProps}
        onClick={mockOnClick}
        hasToogle={true}
        toggleValue={false}
      />,
    );

    fireEvent.click(screen.getByTestId("test-button"));
    expect(mockOnClick).toHaveBeenCalled();
  });

  it("renders without shortcut when not provided", () => {
    renderInMenu(<DropdownControlButton {...defaultProps} />);

    expect(screen.queryByText("⌘")).not.toBeInTheDocument();
  });

  it("uses default onClick when not provided", () => {
    renderInMenu(<DropdownControlButton testId="test-button" label="Test" />);

    // Should not throw error when clicked
    fireEvent.click(screen.getByTestId("test-button"));
  });

  it("applies correct CSS classes for disabled state", () => {
    renderInMenu(<DropdownControlButton {...defaultProps} disabled />);

    const item = screen.getByTestId("test-button");
    expect(item.className).toContain("cursor-not-allowed opacity-50");
  });

  it("renders empty label by default", () => {
    renderInMenu(<DropdownControlButton testId="test-button" />);

    expect(screen.getByTestId("test-button")).toBeInTheDocument();
  });
});
