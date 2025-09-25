import { fireEvent, render, screen } from "@testing-library/react";
import DropdownControlButton from "../DropdownControlButton";

// Mock dependencies
jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({
    name,
    className,
  }: {
    name: string;
    className: string;
  }) => <span data-testid={`icon-${name}`} className={className} />,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: any) => (
    <button {...props}>{children}</button>
  ),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
}));

jest.mock(
  "../../parameterRenderComponent/components/toggleShadComponent",
  () => ({
    __esModule: true,
    default: ({ value, handleOnNewValue, id }: any) => (
      <div
        data-testid={`toggle-${id}`}
        data-value={value}
        onClick={handleOnNewValue}
        role="switch"
        tabIndex={0}
        aria-checked={value}
        aria-label={`Toggle ${id}`}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleOnNewValue();
          }
        }}
      />
    ),
  }),
);

jest.mock("../utils/canvasUtils", () => ({
  getModifierKey: jest.fn(() => "⌘"),
}));

describe("DropdownControlButton", () => {
  const defaultProps = {
    testId: "test-button",
    label: "Test Button",
    onClick: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders basic button with label", () => {
    render(<DropdownControlButton {...defaultProps} />);

    expect(screen.getByTestId("test-button")).toBeInTheDocument();
    expect(screen.getByText("Test Button")).toBeInTheDocument();
  });

  it("calls onClick handler when clicked", () => {
    const mockOnClick = jest.fn();
    render(<DropdownControlButton {...defaultProps} onClick={mockOnClick} />);

    fireEvent.click(screen.getByTestId("test-button"));
    expect(mockOnClick).toHaveBeenCalledTimes(1);
  });

  it("renders with icon when iconName is provided", () => {
    render(<DropdownControlButton {...defaultProps} iconName="test-icon" />);

    expect(screen.getByTestId("icon-test-icon")).toBeInTheDocument();
  });

  it("displays shortcut with modifier key", () => {
    render(<DropdownControlButton {...defaultProps} shortcut="+" />);

    expect(screen.getByText("⌘")).toBeInTheDocument();
    expect(screen.getByText("+")).toBeInTheDocument();
  });

  it("applies disabled state correctly", () => {
    render(<DropdownControlButton {...defaultProps} disabled />);

    const button = screen.getByTestId("test-button");
    expect(button).toBeDisabled();
  });

  it("sets tooltip text as title attribute", () => {
    const tooltipText = "This is a tooltip";
    render(
      <DropdownControlButton {...defaultProps} tooltipText={tooltipText} />,
    );

    const button = screen.getByTestId("test-button");
    expect(button).toHaveAttribute("title", tooltipText);
  });

  it("renders toggle component when hasToogle is true", () => {
    render(
      <DropdownControlButton
        {...defaultProps}
        hasToogle={true}
        toggleValue={true}
      />,
    );

    expect(screen.getByTestId("toggle-helper_lines")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-helper_lines")).toHaveAttribute(
      "data-value",
      "true",
    );
  });

  it("passes toggle value correctly to toggle component", () => {
    render(
      <DropdownControlButton
        {...defaultProps}
        hasToogle={true}
        toggleValue={false}
      />,
    );

    expect(screen.getByTestId("toggle-helper_lines")).toHaveAttribute(
      "data-value",
      "false",
    );
  });

  it("handles toggle click through onClick prop", () => {
    const mockOnClick = jest.fn();
    render(
      <DropdownControlButton
        {...defaultProps}
        onClick={mockOnClick}
        hasToogle={true}
        toggleValue={false}
      />,
    );

    fireEvent.click(screen.getByTestId("toggle-helper_lines"));
    expect(mockOnClick).toHaveBeenCalled();
  });

  it("renders without shortcut when not provided", () => {
    render(<DropdownControlButton {...defaultProps} />);

    expect(screen.queryByText("⌘")).not.toBeInTheDocument();
  });

  it("uses default onClick when not provided", () => {
    render(<DropdownControlButton testId="test-button" label="Test" />);

    // Should not throw error when clicked
    fireEvent.click(screen.getByTestId("test-button"));
  });

  it("applies correct CSS classes for disabled state", () => {
    render(<DropdownControlButton {...defaultProps} disabled />);

    const button = screen.getByTestId("test-button");
    expect(button.className).toContain("cursor-not-allowed opacity-50");
  });

  it("renders empty label by default", () => {
    render(<DropdownControlButton testId="test-button" />);

    const button = screen.getByTestId("test-button");
    expect(button).toBeInTheDocument();
  });
});
