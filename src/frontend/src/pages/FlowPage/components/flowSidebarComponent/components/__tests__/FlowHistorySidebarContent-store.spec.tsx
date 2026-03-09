import { act, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

// ---------------------------------------------------------------------------
// Mocks — hoisted before imports
// ---------------------------------------------------------------------------

const invalidateQueriesMock = jest.fn();
jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: invalidateQueriesMock }),
}));

jest.mock("react-router-dom", () => ({
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
}));

jest.mock("@/utils/reactflowUtils", () => ({
  downloadFlow: jest.fn(),
  processFlows: jest.fn(),
  removeApiKeys: jest.fn((flow: unknown) => flow),
}));

jest.mock("@/controllers/API/api", () => ({
  api: { get: jest.fn(), post: jest.fn() },
}));
jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/flows",
}));

// ---------------------------------------------------------------------------
// Configurable history entry query mock — controls what selectedEntryFull returns
// ---------------------------------------------------------------------------

let entryQueryData: unknown = null;
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
      deployment_counts: {
        "entry-1": 2,
      },
    },
    isLoading: false,
    isError: false,
  }),
  useGetFlowVersionEntry: () => ({
    data: entryQueryData,
    isLoading: entryQueryLoading,
    isError: entryQueryError,
  }),
  usePostCreateVersionSnapshot: () => ({
    mutate: jest.fn(),
    isPending: false,
  }),
  useDeleteFlowVersionEntry: () => ({ mutate: jest.fn(), isPending: false }),
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

const storeState: Record<string, unknown> = {
  currentFlow: mockCurrentFlow,
  nodes: [{ id: "draft-node" }],
  edges: [{ id: "draft-edge" }],
  autoSaveFlow: undefined,
  inspectionPanelVisible: false,
};

const storeSubscribers = new Set<(state: Record<string, unknown>) => void>();

const setStateMock = jest.fn((partial: Record<string, unknown>) => {
  Object.assign(storeState, partial);
  // Notify subscribers synchronously, like real zustand
  storeSubscribers.forEach((cb) => cb(storeState));
});

jest.mock("@/stores/flowStore", () => {
  type Selector<TState> = (state: TState) => unknown;
  type MockStore<TState> = ((selector: Selector<TState>) => unknown) & {
    getState: () => TState;
    setState: (...args: unknown[]) => void;
    subscribe: (cb: (state: TState) => void) => () => boolean;
  };
  const store = ((selector: Selector<Record<string, unknown>>) =>
    selector(storeState)) as MockStore<Record<string, unknown>>;
  store.getState = () => storeState;
  store.setState = (...args: unknown[]) =>
    setStateMock(args[0] as Record<string, unknown>);
  store.subscribe = jest.fn((cb: (state: Record<string, unknown>) => void) => {
    storeSubscribers.add(cb);
    return () => storeSubscribers.delete(cb);
  });
  return { __esModule: true, default: store };
});

const setErrorDataMock = jest.fn();
const setSuccessDataMock = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      setSuccessData: setSuccessDataMock,
      setErrorData: setErrorDataMock,
    }),
}));

const setPreviewMock = jest.fn();
const clearPreviewMock = jest.fn();
const setPreviewLoadingMock = jest.fn();
jest.mock("@/stores/historyPreviewStore", () => {
  type Selector<TState> = (state: TState) => unknown;
  type MockStore<TState> = ((selector: Selector<TState>) => unknown) & {
    getState: () => TState;
  };
  type HistoryPreviewState = {
    previewNodes: null;
    previewEdges: null;
    previewLabel: null;
    setPreview: jest.Mock;
    clearPreview: jest.Mock;
    setPreviewLoading: jest.Mock;
  };
  const state: HistoryPreviewState = {
    previewNodes: null,
    previewEdges: null,
    previewLabel: null,
    setPreview: setPreviewMock,
    clearPreview: clearPreviewMock,
    setPreviewLoading: setPreviewLoadingMock,
  };
  const store = ((selector: Selector<HistoryPreviewState>) =>
    selector({
      ...state,
    })) as MockStore<HistoryPreviewState>;
  store.getState = () => ({ ...state });
  return { __esModule: true, default: store };
});

jest.mock("@/utils/utils", () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(" "),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

type BasicProps = {
  children?: ReactNode;
  onClick?: () => void;
  className?: string;
  [key: string]: unknown;
};

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, ...rest }: BasicProps) => (
    <button onClick={onClick} {...rest}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: BasicProps) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: BasicProps) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onClick }: BasicProps) => (
    <div role="menuitem" onClick={onClick}>
      {children}
    </div>
  ),
  DropdownMenuSeparator: () => <hr />,
  DropdownMenuTrigger: ({ children }: BasicProps) => <>{children}</>,
}));

jest.mock("@/components/ui/sidebar", () => ({
  SidebarGroupLabel: ({ children, className }: BasicProps) => (
    <div className={className}>{children}</div>
  ),
  SidebarMenu: ({ children, className }: BasicProps) => (
    <div className={className}>{children}</div>
  ),
  SidebarMenuButton: ({ children, onClick, className }: BasicProps) => (
    <div onClick={onClick} className={className} role="button" tabIndex={0}>
      {children}
    </div>
  ),
  SidebarMenuItem: ({ children, className }: BasicProps) => (
    <div className={className}>{children}</div>
  ),
}));

jest.mock("@/components/ui/checkbox", () => ({
  Checkbox: () => <input type="checkbox" />,
}));

jest.mock("lodash", () => ({
  cloneDeep: jest.fn((obj: unknown) =>
    obj === undefined ? undefined : JSON.parse(JSON.stringify(obj)),
  ),
}));

// ---------------------------------------------------------------------------
// Import the component AFTER all mocks are set up
// ---------------------------------------------------------------------------

import FlowHistorySidebarContent from "../FlowHistorySidebarContent";

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

describe("FlowHistorySidebarContent store behavior", () => {
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

    const { unmount } = render(<FlowHistorySidebarContent flowId="flow-1" />);

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

    const { unmount } = render(<FlowHistorySidebarContent flowId="flow-1" />);

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

    const { unmount } = render(<FlowHistorySidebarContent flowId="flow-1" />);

    unmount();

    // Should NOT have set inspectionPanelVisible: true
    const restoreCalls = setStateMock.mock.calls.filter(
      (args: unknown[]) =>
        (args[0] as { inspectionPanelVisible?: boolean })
          ?.inspectionPanelVisible === true,
    );
    expect(restoreCalls).toHaveLength(0);
  });

  it("restores original nodes/edges on unmount", () => {
    const { unmount } = render(<FlowHistorySidebarContent flowId="flow-1" />);

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
    const { unmount } = render(<FlowHistorySidebarContent flowId="flow-1" />);

    unmount();

    expect(clearPreviewMock).toHaveBeenCalled();
  });

  it("syncs preview nodes/edges to flow store when entry data is available", () => {
    const historyNodes = [{ id: "hist-node" }];
    const historyEdges = [{ id: "hist-edge" }];
    entryQueryData = {
      id: "entry-1",
      version_tag: "v1",
      data: { nodes: historyNodes, edges: historyEdges },
    };

    render(<FlowHistorySidebarContent flowId="flow-1" />);

    // Click on a history entry to trigger selection
    const entryRow = screen.getByText("v1").closest('[role="button"]');
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
          expect.objectContaining({ id: "hist-node" }),
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

    render(<FlowHistorySidebarContent flowId="flow-1" />);

    // Click entry to trigger selection
    const entryRow = screen.getByText("v1").closest('[role="button"]');
    if (entryRow) {
      act(() => {
        entryRow.click();
      });
    }

    // Should NOT have set empty arrays in the store
    const emptyCalls = setStateMock.mock.calls.filter((args: unknown[]) => {
      const payload = args[0] as { nodes?: unknown[] };
      return Array.isArray(payload?.nodes) && payload.nodes.length === 0;
    });
    expect(emptyCalls).toHaveLength(0);

    // Should NOT have called setPreview with empty data
    const emptyPreviewCalls = setPreviewMock.mock.calls.filter(
      (args: unknown[]) => Array.isArray(args[0]) && args[0].length === 0,
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

    render(<FlowHistorySidebarContent flowId="flow-1" />);

    const entryRow = screen.getByText("v1").closest('[role="button"]');
    if (entryRow) {
      act(() => {
        entryRow.click();
      });
    }

    expect(
      screen.getByText("This version's data could not be rendered for preview"),
    ).toBeTruthy();
  });

  it("restores draft when Current is clicked after previewing", () => {
    entryQueryData = {
      id: "entry-1",
      version_tag: "v1",
      data: { nodes: [{ id: "hist-node" }], edges: [] },
    };

    render(<FlowHistorySidebarContent flowId="flow-1" />);

    // Click version entry
    const entryRow = screen.getByText("v1").closest('[role="button"]');
    if (entryRow) {
      act(() => {
        entryRow.click();
      });
    }

    setStateMock.mockClear();
    clearPreviewMock.mockClear();

    // Click Current row
    const draftRow = screen.getByText("Current").closest('[role="button"]');
    if (draftRow) {
      act(() => {
        draftRow.click();
      });
    }

    // Should show draft in preview overlay (read-only mode)
    expect(setPreviewMock).toHaveBeenCalledWith(
      [{ id: "draft-node" }],
      [{ id: "draft-edge" }],
      "Current Draft",
      null,
    );
  });

  it("shows deployed checkpoint badge when entry has deployment attachments", () => {
    render(<FlowHistorySidebarContent flowId="flow-1" />);

    expect(screen.getByText("Deployed (2)")).toBeTruthy();
  });
});
