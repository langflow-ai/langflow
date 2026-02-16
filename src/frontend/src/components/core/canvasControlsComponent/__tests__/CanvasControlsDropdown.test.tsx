import { fireEvent, render, screen } from "@testing-library/react";
import CanvasControlsDropdown, {
  KEYBOARD_SHORTCUTS,
} from "../CanvasControlsDropdown";

// Mock React Flow hooks
const mockReactFlowFns = {
  fitView: jest.fn(),
  zoomIn: jest.fn(),
  zoomOut: jest.fn(),
  zoomTo: jest.fn(),
};

let mockStoreValues = {
  isInteractive: true,
  minZoomReached: false,
  maxZoomReached: false,
  zoom: 1,
};

jest.mock("@xyflow/react", () => ({
  useReactFlow: () => mockReactFlowFns,
  useStore: (selector: any) => selector(mockStoreValues),
}));

// Mock dependencies
jest.mock("zustand/shallow", () => ({
  shallow: jest.fn((fn) => fn),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: any) => (
    <button {...props}>{children}</button>
  ),
}));

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children, ...props }: any) => (
    <div data-testid="dropdown-menu" {...props}>
      {children}
    </div>
  ),
  DropdownMenuTrigger: ({ children, asChild, ...props }: any) => (
    <div data-testid="dropdown-trigger" {...props}>
      {children}
    </div>
  ),
  DropdownMenuContent: ({ children, ...props }: any) => (
    <div data-testid="dropdown-content" {...props}>
      {children}
    </div>
  ),
}));

jest.mock("@/components/ui/separator", () => ({
  Separator: () => <div data-testid="separator" />,
}));

jest.mock("../DropdownControlButton", () => ({
  __esModule: true,
  default: ({ testId, onClick, disabled, label, shortcut }: any) => (
    <button
      data-testid={testId + "_dropdown"}
      onClick={onClick}
      disabled={disabled}
      data-label={label}
      data-shortcut={shortcut}
    >
      {label}
    </button>
  ),
}));

jest.mock("../utils/canvasUtils", () => ({
  formatZoomPercentage: jest.fn((zoom: number) => `${Math.round(zoom * 100)}%`),
  reactFlowSelector: jest.fn((state: any) => state),
}));

describe("CanvasControlsDropdown", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Reset mock store values
    mockStoreValues = {
      isInteractive: true,
      minZoomReached: false,
      maxZoomReached: false,
      zoom: 1,
    };

    // Mock addEventListener and removeEventListener
    jest.spyOn(document, "addEventListener");
    jest.spyOn(document, "removeEventListener");
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("renders dropdown trigger with zoom percentage", () => {
    render(<CanvasControlsDropdown />);

    expect(screen.getByTestId("canvas_controls_dropdown")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("renders chevron icon", () => {
    render(<CanvasControlsDropdown />);

    // Should have one of the chevron icons (the actual logic depends on internal state)
    const chevronUp = screen.queryByTestId("icon-ChevronUp");
    const chevronDown = screen.queryByTestId("icon-ChevronDown");

    expect(chevronUp || chevronDown).toBeInTheDocument();
  });

  it("renders all control buttons with correct props", () => {
    render(<CanvasControlsDropdown />);

    expect(screen.getByTestId("zoom_in_dropdown")).toBeInTheDocument();
    expect(screen.getByTestId("zoom_out_dropdown")).toBeInTheDocument();
    expect(screen.getByTestId("reset_zoom_dropdown")).toBeInTheDocument();
    expect(screen.getByTestId("fit_view_dropdown")).toBeInTheDocument();

    // Check shortcuts are passed correctly
    expect(screen.getByTestId("zoom_in_dropdown")).toHaveAttribute(
      "data-shortcut",
      KEYBOARD_SHORTCUTS.ZOOM_IN.key,
    );
    expect(screen.getByTestId("zoom_out_dropdown")).toHaveAttribute(
      "data-shortcut",
      KEYBOARD_SHORTCUTS.ZOOM_OUT.key,
    );
  });

  it("handles zoom in button click", () => {
    render(<CanvasControlsDropdown />);

    fireEvent.click(screen.getByTestId("zoom_in_dropdown"));
    expect(mockReactFlowFns.zoomIn).toHaveBeenCalledTimes(1);
  });

  it("handles zoom out button click", () => {
    render(<CanvasControlsDropdown />);

    fireEvent.click(screen.getByTestId("zoom_out_dropdown"));
    expect(mockReactFlowFns.zoomOut).toHaveBeenCalledTimes(1);
  });

  it("handles fit view button click", () => {
    render(<CanvasControlsDropdown />);

    fireEvent.click(screen.getByTestId("fit_view_dropdown"));
    expect(mockReactFlowFns.fitView).toHaveBeenCalledTimes(1);
  });

  it("handles reset zoom button click", () => {
    render(<CanvasControlsDropdown />);

    fireEvent.click(screen.getByTestId("reset_zoom_dropdown"));
    expect(mockReactFlowFns.zoomTo).toHaveBeenCalledWith(1);
  });

  it("disables zoom in when maxZoomReached is true", () => {
    mockStoreValues.maxZoomReached = true;

    render(<CanvasControlsDropdown />);

    expect(screen.getByTestId("zoom_in_dropdown")).toBeDisabled();
  });

  it("disables zoom out when minZoomReached is true", () => {
    mockStoreValues.minZoomReached = true;

    render(<CanvasControlsDropdown />);

    expect(screen.getByTestId("zoom_out_dropdown")).toBeDisabled();
  });

  describe("Keyboard shortcuts", () => {
    it("sets up keyboard event listeners on mount", () => {
      render(<CanvasControlsDropdown />);

      expect(document.addEventListener).toHaveBeenCalledWith(
        "keydown",
        expect.any(Function),
      );
    });
  });

  describe("Event listener management", () => {
    it("removes keydown event listener on unmount", () => {
      const { unmount } = render(<CanvasControlsDropdown />);

      unmount();

      expect(document.removeEventListener).toHaveBeenCalledWith(
        "keydown",
        expect.any(Function),
      );
    });
  });

  describe("Dynamic zoom display", () => {
    it("displays zoom percentage correctly", () => {
      render(<CanvasControlsDropdown />);

      expect(screen.getByText("100%")).toBeInTheDocument();
    });

    it("handles fractional zoom values correctly", () => {
      mockStoreValues.zoom = 0.75;

      render(<CanvasControlsDropdown />);

      expect(screen.getByText("75%")).toBeInTheDocument();
    });
  });
});
