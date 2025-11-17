import { fireEvent, render, screen } from "@testing-library/react";
import { SearchConfigTrigger } from "../searchConfigTrigger";

// Mock the components
jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name, className }: any) => (
    <div data-testid={`icon-${name}`} className={className}>
      {name}
    </div>
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children, content }: any) => (
    <div data-testid="tooltip" title={content}>
      {children}
    </div>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    variant,
    size,
    "data-testid": testId,
  }: any) => (
    <button
      onClick={onClick}
      data-testid={testId}
      data-variant={variant}
      data-size={size}
    >
      {children}
    </button>
  ),
}));

describe("SearchConfigTrigger", () => {
  const defaultProps = {
    showConfig: false,
    setShowConfig: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders correctly", () => {
    render(<SearchConfigTrigger {...defaultProps} />);

    expect(screen.getByTestId("sidebar-options-trigger")).toBeInTheDocument();
    expect(screen.getByTestId("tooltip")).toBeInTheDocument();
    expect(screen.getByTestId("icon-Settings2")).toBeInTheDocument();
  });

  it("displays correct tooltip content", () => {
    render(<SearchConfigTrigger {...defaultProps} />);

    const tooltip = screen.getByTestId("tooltip");
    expect(tooltip).toHaveAttribute("title", "Component settings");
  });

  it("shows ghost variant when showConfig is false", () => {
    render(<SearchConfigTrigger {...defaultProps} showConfig={false} />);

    const button = screen.getByTestId("sidebar-options-trigger");
    expect(button).toHaveAttribute("data-variant", "ghost");
  });

  it("shows ghostActive variant when showConfig is true", () => {
    render(<SearchConfigTrigger {...defaultProps} showConfig={true} />);

    const button = screen.getByTestId("sidebar-options-trigger");
    expect(button).toHaveAttribute("data-variant", "ghostActive");
  });

  it("has correct button size", () => {
    render(<SearchConfigTrigger {...defaultProps} />);

    const button = screen.getByTestId("sidebar-options-trigger");
    expect(button).toHaveAttribute("data-size", "iconMd");
  });

  it("calls setShowConfig with true when clicked and showConfig is false", () => {
    const setShowConfig = jest.fn();
    render(
      <SearchConfigTrigger
        {...defaultProps}
        showConfig={false}
        setShowConfig={setShowConfig}
      />,
    );

    const button = screen.getByTestId("sidebar-options-trigger");
    fireEvent.click(button);

    expect(setShowConfig).toHaveBeenCalledTimes(1);
    expect(setShowConfig).toHaveBeenCalledWith(true);
  });

  it("calls setShowConfig with false when clicked and showConfig is true", () => {
    const setShowConfig = jest.fn();
    render(
      <SearchConfigTrigger
        {...defaultProps}
        showConfig={true}
        setShowConfig={setShowConfig}
      />,
    );

    const button = screen.getByTestId("sidebar-options-trigger");
    fireEvent.click(button);

    expect(setShowConfig).toHaveBeenCalledTimes(1);
    expect(setShowConfig).toHaveBeenCalledWith(false);
  });

  it("renders Settings2 icon with correct styling", () => {
    render(<SearchConfigTrigger {...defaultProps} />);

    const icon = screen.getByTestId("icon-Settings2");
    expect(icon).toHaveClass("h-4", "w-4");
  });

  it("toggles showConfig state on multiple clicks", () => {
    const setShowConfig = jest.fn();
    render(
      <SearchConfigTrigger
        {...defaultProps}
        showConfig={false}
        setShowConfig={setShowConfig}
      />,
    );

    const button = screen.getByTestId("sidebar-options-trigger");

    // First click
    fireEvent.click(button);
    expect(setShowConfig).toHaveBeenCalledWith(true);

    // Second click
    fireEvent.click(button);
    expect(setShowConfig).toHaveBeenCalledWith(true); // Still true because showConfig prop is still false

    expect(setShowConfig).toHaveBeenCalledTimes(2);
  });

  it("has proper accessibility attributes", () => {
    render(<SearchConfigTrigger {...defaultProps} />);

    const button = screen.getByTestId("sidebar-options-trigger");
    expect(button).toBeInTheDocument();

    // Check that button is properly wrapped in tooltip for accessibility
    const tooltip = screen.getByTestId("tooltip");
    expect(tooltip).toContainElement(button);
  });
});
