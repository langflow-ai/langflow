import { act, fireEvent, render, screen } from "@testing-library/react";

jest.mock("@/CustomNodes/helpers/check-code-validity", () => ({
  checkCodeValidity: jest.fn(),
}));

jest.mock("@/constants/alerts_constants", () => ({
  MISSED_ERROR_ALERT: "MISSED_ERROR_ALERT",
}));

jest.mock("@/constants/constants", () => ({
  BROKEN_EDGES_WARNING: "BROKEN_EDGES_WARNING",
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_DATASTAX_LANGFLOW: false,
  ENABLE_INSPECTION_PANEL: false,
}));

jest.mock("@/customization/utils/analytics", () => ({
  track: jest.fn(),
  trackDataLoaded: jest.fn(),
  trackFlowBuild: jest.fn(),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: { getState: () => ({ setErrorData: jest.fn() }) },
}));

jest.mock("@/stores/darkStore", () => ({
  useDarkStore: { getState: () => ({ refreshStars: jest.fn() }) },
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({ setCurrentFlow: jest.fn(), takeSnapshot: jest.fn() }),
  },
}));

jest.mock("@/stores/globalVariablesStore/globalVariables", () => ({
  useGlobalVariablesStore: { getState: () => ({ globalVariables: {} }) },
}));

jest.mock("@/stores/tweaksStore", () => ({
  useTweaksStore: {
    getState: () => ({ initialSetup: jest.fn(), tweaks: {} }),
  },
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: { getState: () => ({ templates: {}, types: {} }) },
}));

jest.mock("@/utils/utils", () => ({
  brokenEdgeMessage: jest.fn(),
  cn: (...classes: (string | boolean | undefined)[]) =>
    classes.filter(Boolean).join(" "),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  buildPositionDictionary: jest.fn(() => ({})),
  checkChatInput: jest.fn(),
  cleanEdges: jest.fn(() => ({ edges: [], brokenEdges: [] })),
  getConnectedSubgraph: jest.fn(),
  getHandleId: jest.fn(),
  getNodeId: jest.fn(),
  scapedJSONStringfy: jest.fn(),
  scapeJSONParse: jest.fn(),
  unselectAllNodesEdges: jest.fn(),
  updateGroupRecursion: jest.fn(),
  validateEdge: jest.fn(),
  validateNodes: jest.fn(),
}));

jest.mock("@/utils/storeUtils", () => ({
  getInputsAndOutputs: jest.fn(() => ({ inputs: [], outputs: [] })),
}));

jest.mock("@/utils/buildUtils", () => ({
  buildFlowVerticesWithFallback: jest.fn(),
}));

jest.mock("lodash", () => ({
  cloneDeep: jest.fn((obj) => JSON.parse(JSON.stringify(obj))),
  zip: jest.fn(),
}));



jest.mock("@/components/core/logCanvasControlsComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("../../flowSidebarComponent", () => ({
  useSearchContext: () => ({ focusSearch: jest.fn(), isSearchFocused: false }),
}));

jest.mock(
  "../../flowSidebarComponent/components/sidebarSegmentedNav",
  () => ({ NAV_ITEMS: [] }),
);

jest.mock("@xyflow/react", () => ({
  addEdge: jest.fn(),
  applyEdgeChanges: jest.fn((_, edges) => edges),
  applyNodeChanges: jest.fn((_, nodes) => nodes),
  Panel: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  useStoreApi: () => ({ setState: jest.fn() }),
}));

jest.mock("zustand/react/shallow", () => ({
  useShallow: (fn: (s: unknown) => unknown) => fn,
}));

jest.mock(
  "@/components/core/canvasControlsComponent/CanvasControls",
  () => ({
    __esModule: true,
    default: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="canvas-controls">{children}</div>
    ),
  }),
);

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    disabled,
    title,
    unstyled: _unstyled,
    unselectable: _unselectable,
    ...rest
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    children?: React.ReactNode;
    unstyled?: boolean;
    unselectable?: string;
  }) => (
    <button onClick={onClick} disabled={disabled} title={title} {...rest}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/separator", () => ({
  Separator: ({ orientation }: { orientation: string }) => (
    <div data-testid={`separator-${orientation}`} />
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));



import useFlowStore from "@/stores/flowStore";
import { MemoizedCanvasControls } from "../MemoizedComponents";

const defaultProps = {
  setIsAddingNote: jest.fn(),
  shadowBoxWidth: 200,
  shadowBoxHeight: 100,
  selectedNode: null,
};

describe("Lasso mode integration: store ↔ MemoizedCanvasControls", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    act(() => {
      useFlowStore.setState({ isLassoMode: false, currentFlow: undefined });
    });
  });

  describe("store state drives button appearance", () => {
    it("shows inactive button when isLassoMode is false in the store", () => {
      render(<MemoizedCanvasControls {...defaultProps} />);

      const button = screen.getByTestId("lasso-mode-toggle");
      expect(button.className).not.toContain("bg-accent");
      expect(button).toHaveAttribute("title", "Lasso Select");
    });

    it("shows active button when isLassoMode is true in the store", () => {
      act(() => {
        useFlowStore.setState({ isLassoMode: true });
      });

      render(<MemoizedCanvasControls {...defaultProps} />);

      const button = screen.getByTestId("lasso-mode-toggle");
      expect(button.className).toContain("bg-accent");
      expect(button).toHaveAttribute("title", "Exit Lasso Select (Esc)");
    });
  });

  describe("button click updates the store", () => {
    it("activates lasso mode in the store on first click", () => {
      render(<MemoizedCanvasControls {...defaultProps} />);

      act(() => {
        fireEvent.click(screen.getByTestId("lasso-mode-toggle"));
      });

      expect(useFlowStore.getState().isLassoMode).toBe(true);
    });

    it("deactivates lasso mode in the store on second click", () => {
      act(() => {
        useFlowStore.setState({ isLassoMode: true });
      });

      render(<MemoizedCanvasControls {...defaultProps} />);

      act(() => {
        fireEvent.click(screen.getByTestId("lasso-mode-toggle"));
      });

      expect(useFlowStore.getState().isLassoMode).toBe(false);
    });
  });

  describe("store reset clears lasso mode", () => {
    it("button reflects inactive state after resetFlowState", () => {
      act(() => {
        useFlowStore.setState({ isLassoMode: true });
      });

      render(<MemoizedCanvasControls {...defaultProps} />);
      expect(
        screen.getByTestId("lasso-mode-toggle").className,
      ).toContain("bg-accent");

      act(() => {
        useFlowStore.getState().resetFlowState();
      });

      expect(useFlowStore.getState().isLassoMode).toBe(false);
    });
  });
});
