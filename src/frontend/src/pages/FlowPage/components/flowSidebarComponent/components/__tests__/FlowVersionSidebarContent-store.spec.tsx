import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ---------------------------------------------------------------------------
// Mocks — hoisted before imports
// ---------------------------------------------------------------------------

const invalidateQueriesMock = jest.fn();
jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: invalidateQueriesMock }),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  downloadFlow: jest.fn(),
  processFlows: jest.fn(),
  removeApiKeys: jest.fn((flow: any) => flow),
}));

jest.mock("@/controllers/API/api", () => ({
  api: { get: jest.fn(), post: jest.fn() },
}));
jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/flows",
}));

// ---------------------------------------------------------------------------
// Configurable version entry query mock — controls what selectedEntryFull returns
// ---------------------------------------------------------------------------

let entryQueryData: any = null;
let entryQueryLoading = false;
let entryQueryError = false;

jest.mock("@/controllers/API/queries/flow-version", () => ({
  useGetFlowVersions: () => ({
    data: {
      entries: [
        {
          id: "entry-1",
          flow_id: "flow-1",
          user_id: "user-1",
          version_number: 1,
          version_tag: "v1",
          description: "first version",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      max_entries: 50,
    },
    isLoading: false,
    isError: false,
  }),
  useGetFlowVersionEntry: () => ({
    data: entryQueryData,
    isLoading: entryQueryLoading,
    isError: entryQueryError,
  }),
  useDeleteVersionEntry: () => ({ mutate: jest.fn(), isPending: false }),
}));

const applyFlowToCanvasMock = jest.fn();
jest.mock("@/hooks/flows/use-apply-flow-to-canvas", () => ({
  __esModule: true,
  default: () => applyFlowToCanvasMock,
}));

// ---------------------------------------------------------------------------
// Store mocks — with subscribe support
// ---------------------------------------------------------------------------

const mockCurrentFlow = {
  id: "flow-1",
  name: "Test Flow",
  description: "A test flow",
  data: { nodes: [{ id: "draft-node" }], edges: [{ id: "draft-edge" }] },
};

const storeState: Record<string, any> = {
  currentFlow: mockCurrentFlow,
  nodes: [{ id: "draft-node" }],
  edges: [{ id: "draft-edge" }],
  autoSaveFlow: undefined,
  inspectionPanelVisible: false,
};

const storeSubscribers = new Set<(state: any) => void>();

const setStateMock = jest.fn((partial: any) => {
  Object.assign(storeState, partial);
  // Notify subscribers synchronously, like real zustand
  storeSubscribers.forEach((cb) => cb(storeState));
});

jest.mock("@/stores/flowStore", () => {
  const store: any = (selector: any) => selector(storeState);
  store.getState = () => storeState;
  store.setState = (...args: any[]) => setStateMock(...args);
  store.subscribe = jest.fn((cb: any) => {
    storeSubscribers.add(cb);
    return () => storeSubscribers.delete(cb);
  });
  return { __esModule: true, default: store };
});

const setErrorDataMock = jest.fn();
const setSuccessDataMock = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({
      setSuccessData: setSuccessDataMock,
      setErrorData: setErrorDataMock,
    }),
}));

const setPreviewMock = jest.fn();
const clearPreviewMock = jest.fn();
const setPreviewLoadingMock = jest.fn();
jest.mock("@/stores/versionPreviewStore", () => {
  const state = {
    previewNodes: null,
    previewEdges: null,
    previewLabel: null,
    previewId: null,
    isPreviewLoading: false,
    didRestore: false,
    setPreview: setPreviewMock,
    clearPreview: clearPreviewMock,
    setPreviewLoading: setPreviewLoadingMock,
  };
  const store: any = (selector: any) => selector(state);
  store.getState = () => state;
  store.setState = jest.fn();
  return { __esModule: true, default: store };
});

jest.mock("@/utils/utils", () => ({
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: any) => <span data-testid={`icon-${name}`} />,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, ...rest }: any) => (
    <button onClick={onClick} {...rest}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: any) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: any) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onClick }: any) => (
    <div role="menuitem" onClick={onClick}>
      {children}
    </div>
  ),
  DropdownMenuSeparator: () => <hr />,
  DropdownMenuTrigger: ({ children }: any) => <>{children}</>,
}));

jest.mock("@/components/ui/checkbox", () => ({
  Checkbox: () => <input type="checkbox" />,
}));

const setActiveSectionMock = jest.fn();
jest.mock("@/components/ui/sidebar", () => ({
  useSidebar: () => ({ setActiveSection: setActiveSectionMock }),
  SidebarGroupLabel: ({ children, className }: any) => (
    <div className={className}>{children}</div>
  ),
  SidebarMenu: ({ children, className }: any) => (
    <div className={className}>{children}</div>
  ),
  SidebarMenuButton: ({ children, onClick, isActive, className }: any) => (
    <div
      role="button"
      onClick={onClick}
      className={`cursor-pointer ${className ?? ""} ${isActive ? "active" : ""}`}
    >
      {children}
    </div>
  ),
  SidebarMenuItem: ({ children }: any) => <div>{children}</div>,
}));

jest.mock("lodash", () => ({
  cloneDeep: jest.fn((obj: any) =>
    obj === undefined ? undefined : JSON.parse(JSON.stringify(obj)),
  ),
}));

// ---------------------------------------------------------------------------
// Import the component AFTER all mocks are set up
// ---------------------------------------------------------------------------

import FlowVersionSidebarContent from "../FlowVersionSidebarContent";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resetStoreState() {
  storeState.currentFlow = mockCurrentFlow;
  storeState.nodes = [{ id: "draft-node" }];
  storeState.edges = [{ id: "draft-edge" }];
  storeState.autoSaveFlow = undefined;
  storeState.inspectionPanelVisible = false;
  storeSubscribers.clear();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FlowVersionSidebarContent store behavior", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    entryQueryData = null;
    entryQueryLoading = false;
    entryQueryError = false;
    resetStoreState();
  });

  it("disables auto-save on mount and restores on unmount", () => {
    const fakeAutoSave = jest.fn();
    storeState.autoSaveFlow = fakeAutoSave;

    const { unmount } = render(<FlowVersionSidebarContent flowId="flow-1" />);

    // Auto-save should be disabled on mount
    expect(setStateMock).toHaveBeenCalledWith(
      expect.objectContaining({ autoSaveFlow: undefined }),
    );

    unmount();

    // Auto-save should be restored on unmount
    expect(setStateMock).toHaveBeenCalledWith(
      expect.objectContaining({ autoSaveFlow: fakeAutoSave }),
    );
  });

  it("hides inspection panel on mount and restores on unmount", () => {
    storeState.inspectionPanelVisible = true;

    const { unmount } = render(<FlowVersionSidebarContent flowId="flow-1" />);

    expect(setStateMock).toHaveBeenCalledWith(
      expect.objectContaining({ inspectionPanelVisible: false }),
    );

    unmount();

    expect(setStateMock).toHaveBeenCalledWith(
      expect.objectContaining({ inspectionPanelVisible: true }),
    );
  });

  it("does not restore inspection panel if it was already hidden", () => {
    storeState.inspectionPanelVisible = false;

    const { unmount } = render(<FlowVersionSidebarContent flowId="flow-1" />);

    unmount();

    // Should NOT have set inspectionPanelVisible: true
    const restoreCalls = setStateMock.mock.calls.filter(
      (args: any[]) => args[0]?.inspectionPanelVisible === true,
    );
    expect(restoreCalls).toHaveLength(0);
  });

  it("restores original nodes/edges on unmount", () => {
    const { unmount } = render(<FlowVersionSidebarContent flowId="flow-1" />);

    // Clear mock calls from mount
    setStateMock.mockClear();

    unmount();

    // Should restore original nodes/edges
    expect(setStateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        nodes: [{ id: "draft-node" }],
        edges: [{ id: "draft-edge" }],
      }),
    );
  });

  it("clears preview store on unmount", () => {
    const { unmount } = render(<FlowVersionSidebarContent flowId="flow-1" />);

    unmount();

    expect(clearPreviewMock).toHaveBeenCalled();
  });

  it("syncs preview nodes/edges to flow store when entry data is available", () => {
    const versionNodes = [{ id: "version-node" }];
    const versionEdges = [{ id: "version-edge" }];
    entryQueryData = {
      id: "entry-1",
      version_tag: "v1",
      data: { nodes: versionNodes, edges: versionEdges },
    };

    render(<FlowVersionSidebarContent flowId="flow-1" />);

    // Click on a version entry to trigger selection
    const user = userEvent.setup();
    const entryRow = screen.getByText("v1").closest("[class*=cursor-pointer]");
    if (entryRow) {
      act(() => {
        entryRow.click();
      });
    }

    // The processedPreview should trigger store sync
    // Since the mock useGetFlowVersionEntry always returns entryQueryData,
    // and we clicked the entry (setting selectedId), processedPreview should
    // be non-null and the store should be updated.
    expect(setStateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        nodes: expect.arrayContaining([
          expect.objectContaining({ id: "version-node" }),
        ]),
      }),
    );
  });

  it("does NOT sync error state to flow store or preview store", () => {
    // Make processFlows throw to trigger error state
    const { processFlows } = require("@/utils/reactflowUtils");
    processFlows.mockImplementationOnce(() => {
      throw new Error("processing failed");
    });

    entryQueryData = {
      id: "entry-1",
      version_tag: "v1",
      data: { nodes: [{ id: "n1" }], edges: [] },
    };

    render(<FlowVersionSidebarContent flowId="flow-1" />);

    // Click entry to trigger selection
    const entryRow = screen.getByText("v1").closest("[class*=cursor-pointer]");
    if (entryRow) {
      act(() => {
        entryRow.click();
      });
    }

    // Should NOT have set empty arrays in the store
    const emptyCalls = setStateMock.mock.calls.filter(
      (args: any[]) =>
        Array.isArray(args[0]?.nodes) && args[0].nodes.length === 0,
    );
    expect(emptyCalls).toHaveLength(0);

    // Should NOT have called setPreview with empty data
    const emptyPreviewCalls = setPreviewMock.mock.calls.filter(
      (args: any[]) => Array.isArray(args[0]) && args[0].length === 0,
    );
    expect(emptyPreviewCalls).toHaveLength(0);
  });

  it("shows processing error message in the sidebar", () => {
    const { processFlows } = require("@/utils/reactflowUtils");
    processFlows.mockImplementationOnce(() => {
      throw new Error("processing failed");
    });

    entryQueryData = {
      id: "entry-1",
      version_tag: "v1",
      data: { nodes: [{ id: "n1" }], edges: [] },
    };

    render(<FlowVersionSidebarContent flowId="flow-1" />);

    const entryRow = screen.getByText("v1").closest("[class*=cursor-pointer]");
    if (entryRow) {
      act(() => {
        entryRow.click();
      });
    }

    expect(
      screen.getByText("This version's data could not be rendered for preview"),
    ).toBeTruthy();
  });

  it("restores original draft when Current is clicked after previewing a version", () => {
    entryQueryData = {
      id: "entry-1",
      version_tag: "v1",
      data: { nodes: [{ id: "version-node" }], edges: [] },
    };

    render(<FlowVersionSidebarContent flowId="flow-1" />);

    // Click version entry — this sets store nodes to version-node via layoutEffect
    const entryRow = screen.getByText("v1").closest("[class*=cursor-pointer]");
    if (entryRow) {
      act(() => {
        entryRow.click();
      });
    }

    setStateMock.mockClear();
    clearPreviewMock.mockClear();

    // Click Current row
    const draftRow = screen
      .getByText("Current")
      .closest("[class*=cursor-pointer]");
    if (draftRow) {
      act(() => {
        draftRow.click();
      });
    }

    // Should restore original draft nodes/edges (captured at mount), not the
    // preview data that was set into the store.
    expect(setStateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        nodes: [{ id: "draft-node" }],
        edges: [{ id: "draft-edge" }],
      }),
    );

    // Should show draft in preview overlay with null id
    expect(setPreviewMock).toHaveBeenCalledWith(
      [{ id: "draft-node" }],
      [{ id: "draft-edge" }],
      "Current Draft",
      null,
    );
  });
});
