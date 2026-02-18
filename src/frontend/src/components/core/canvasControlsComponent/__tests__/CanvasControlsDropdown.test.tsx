import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

// Mock flow stores
const mockFlowStoreValues: Record<string, any> = {
  inspectionPanelVisible: false,
  nodes: [],
  edges: [],
  setNodes: jest.fn(),
};

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: any) => selector(mockFlowStoreValues),
}));

const mockTakeSnapshot = jest.fn();

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: any) => selector({ takeSnapshot: mockTakeSnapshot }),
}));

// Mock layoutUtils
const mockGetLayoutedNodes = jest.fn();

jest.mock("@/utils/layoutUtils", () => ({
  getLayoutedNodes: (...args: any[]) => mockGetLayoutedNodes(...args),
}));

describe("CanvasControlsDropdown", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();

    // Reset mock store values
    mockStoreValues = {
      isInteractive: true,
      minZoomReached: false,
      maxZoomReached: false,
      zoom: 1,
    };

    mockFlowStoreValues.inspectionPanelVisible = false;
    mockFlowStoreValues.nodes = [];
    mockFlowStoreValues.edges = [];
    mockFlowStoreValues.setNodes = jest.fn();

    // Mock addEventListener and removeEventListener
    jest.spyOn(document, "addEventListener");
    jest.spyOn(document, "removeEventListener");
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it("renders dropdown trigger with zoom percentage", () => {
    render(<CanvasControlsDropdown selectedNode={null} />);

    expect(screen.getByTestId("canvas_controls_dropdown")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("renders chevron icon", () => {
    render(<CanvasControlsDropdown selectedNode={null} />);

    // Should have one of the chevron icons (the actual logic depends on internal state)
    const chevronUp = screen.queryByTestId("icon-ChevronUp");
    const chevronDown = screen.queryByTestId("icon-ChevronDown");

    expect(chevronUp || chevronDown).toBeInTheDocument();
  });

  it("renders all control buttons with correct props", () => {
    render(<CanvasControlsDropdown selectedNode={null} />);

    expect(screen.getByTestId("zoom_in_dropdown")).toBeInTheDocument();
    expect(screen.getByTestId("zoom_out_dropdown")).toBeInTheDocument();
    expect(screen.getByTestId("reset_zoom_dropdown")).toBeInTheDocument();
    expect(screen.getByTestId("fit_view_dropdown")).toBeInTheDocument();
    expect(screen.getByTestId("tidy_up_dropdown")).toBeInTheDocument();

    // Check shortcuts are passed correctly
    expect(screen.getByTestId("zoom_in_dropdown")).toHaveAttribute(
      "data-shortcut",
      KEYBOARD_SHORTCUTS.ZOOM_IN.key,
    );
    expect(screen.getByTestId("zoom_out_dropdown")).toHaveAttribute(
      "data-shortcut",
      KEYBOARD_SHORTCUTS.ZOOM_OUT.key,
    );
    expect(screen.getByTestId("tidy_up_dropdown")).toHaveAttribute(
      "data-shortcut",
      `⇧${KEYBOARD_SHORTCUTS.TIDY_UP.key}`,
    );
  });

  it("handles zoom in button click", () => {
    render(<CanvasControlsDropdown selectedNode={null} />);

    fireEvent.click(screen.getByTestId("zoom_in_dropdown"));
    expect(mockReactFlowFns.zoomIn).toHaveBeenCalledTimes(1);
  });

  it("handles zoom out button click", () => {
    render(<CanvasControlsDropdown selectedNode={null} />);

    fireEvent.click(screen.getByTestId("zoom_out_dropdown"));
    expect(mockReactFlowFns.zoomOut).toHaveBeenCalledTimes(1);
  });

  it("handles fit view button click", () => {
    render(<CanvasControlsDropdown selectedNode={null} />);

    fireEvent.click(screen.getByTestId("fit_view_dropdown"));
    expect(mockReactFlowFns.fitView).toHaveBeenCalledTimes(1);
  });

  it("handles reset zoom button click", () => {
    render(<CanvasControlsDropdown selectedNode={null} />);

    fireEvent.click(screen.getByTestId("reset_zoom_dropdown"));
    expect(mockReactFlowFns.zoomTo).toHaveBeenCalledWith(1);
  });

  it("disables zoom in when maxZoomReached is true", () => {
    mockStoreValues.maxZoomReached = true;

    render(<CanvasControlsDropdown selectedNode={null} />);

    expect(screen.getByTestId("zoom_in_dropdown")).toBeDisabled();
  });

  it("disables zoom out when minZoomReached is true", () => {
    mockStoreValues.minZoomReached = true;

    render(<CanvasControlsDropdown selectedNode={null} />);

    expect(screen.getByTestId("zoom_out_dropdown")).toBeDisabled();
  });

  describe("Keyboard shortcuts", () => {
    it("sets up keyboard event listeners on mount", () => {
      render(<CanvasControlsDropdown selectedNode={null} />);

      expect(document.addEventListener).toHaveBeenCalledWith(
        "keydown",
        expect.any(Function),
      );
    });
  });

  describe("Event listener management", () => {
    it("removes keydown event listener on unmount", () => {
      const { unmount } = render(
        <CanvasControlsDropdown selectedNode={null} />,
      );

      unmount();

      expect(document.removeEventListener).toHaveBeenCalledWith(
        "keydown",
        expect.any(Function),
      );
    });
  });

  describe("Dynamic zoom display", () => {
    it("displays zoom percentage correctly", () => {
      render(<CanvasControlsDropdown selectedNode={null} />);

      expect(screen.getByText("100%")).toBeInTheDocument();
    });

    it("handles fractional zoom values correctly", () => {
      mockStoreValues.zoom = 0.75;

      render(<CanvasControlsDropdown selectedNode={null} />);

      expect(screen.getByText("75%")).toBeInTheDocument();
    });
  });

  describe("Tidy Up", () => {
    const mockNodes = [
      { id: "node-1", position: { x: 0, y: 0 }, data: {} },
      { id: "node-2", position: { x: 100, y: 100 }, data: {} },
    ];
    const mockEdges = [{ id: "edge-1", source: "node-1", target: "node-2" }];

    it("renders tidy up button", () => {
      render(<CanvasControlsDropdown selectedNode={null} />);

      expect(screen.getByTestId("tidy_up_dropdown")).toBeInTheDocument();
      expect(screen.getByTestId("tidy_up_dropdown")).toHaveAttribute(
        "data-label",
        "Tidy Up",
      );
    });

    it("disables tidy up button when there are no nodes", () => {
      mockFlowStoreValues.nodes = [];

      render(<CanvasControlsDropdown selectedNode={null} />);

      expect(screen.getByTestId("tidy_up_dropdown")).toBeDisabled();
    });

    it("enables tidy up button when there are nodes", () => {
      mockFlowStoreValues.nodes = mockNodes;

      render(<CanvasControlsDropdown selectedNode={null} />);

      expect(screen.getByTestId("tidy_up_dropdown")).not.toBeDisabled();
    });

    it("calls takeSnapshot and getLayoutedNodes on tidy up click", async () => {
      mockFlowStoreValues.nodes = mockNodes;
      mockFlowStoreValues.edges = mockEdges;
      const layoutedNodes = [
        { id: "node-1", position: { x: 0, y: 50 }, data: {} },
        { id: "node-2", position: { x: 200, y: 50 }, data: {} },
      ];
      mockGetLayoutedNodes.mockResolvedValue(layoutedNodes);

      render(<CanvasControlsDropdown selectedNode={null} />);

      fireEvent.click(screen.getByTestId("tidy_up_dropdown"));

      await waitFor(() => {
        expect(mockTakeSnapshot).toHaveBeenCalledTimes(1);
        expect(mockGetLayoutedNodes).toHaveBeenCalledWith(mockNodes, mockEdges);
        expect(mockFlowStoreValues.setNodes).toHaveBeenCalledWith(
          layoutedNodes,
        );
      });
    });

    it("calls fitView after layout completes", async () => {
      mockFlowStoreValues.nodes = mockNodes;
      mockFlowStoreValues.edges = mockEdges;
      mockGetLayoutedNodes.mockResolvedValue(mockNodes);

      render(<CanvasControlsDropdown selectedNode={null} />);

      fireEvent.click(screen.getByTestId("tidy_up_dropdown"));

      await waitFor(() => {
        expect(mockFlowStoreValues.setNodes).toHaveBeenCalled();
      });

      jest.advanceTimersByTime(50);

      expect(mockReactFlowFns.fitView).toHaveBeenCalled();
    });

    it("does nothing when tidy up is clicked with no nodes", async () => {
      mockFlowStoreValues.nodes = [];

      render(<CanvasControlsDropdown selectedNode={null} />);

      fireEvent.click(screen.getByTestId("tidy_up_dropdown"));

      expect(mockTakeSnapshot).not.toHaveBeenCalled();
      expect(mockGetLayoutedNodes).not.toHaveBeenCalled();
    });

    it("triggers tidy up via Ctrl+Shift+L keyboard shortcut", async () => {
      mockFlowStoreValues.nodes = mockNodes;
      mockFlowStoreValues.edges = mockEdges;
      mockGetLayoutedNodes.mockResolvedValue(mockNodes);

      render(<CanvasControlsDropdown selectedNode={null} />);

      fireEvent.keyDown(document, {
        code: "KeyL",
        key: "L",
        ctrlKey: true,
        shiftKey: true,
      });

      await waitFor(() => {
        expect(mockTakeSnapshot).toHaveBeenCalledTimes(1);
        expect(mockGetLayoutedNodes).toHaveBeenCalledWith(mockNodes, mockEdges);
      });
    });

    it("does not trigger tidy up via Ctrl+L without shift", () => {
      mockFlowStoreValues.nodes = mockNodes;

      render(<CanvasControlsDropdown selectedNode={null} />);

      fireEvent.keyDown(document, {
        code: "KeyL",
        key: "l",
        ctrlKey: true,
        shiftKey: false,
      });

      expect(mockTakeSnapshot).not.toHaveBeenCalled();
      expect(mockGetLayoutedNodes).not.toHaveBeenCalled();
    });
  });
});
