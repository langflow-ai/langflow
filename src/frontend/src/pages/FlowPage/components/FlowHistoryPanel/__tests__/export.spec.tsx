import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ---------------------------------------------------------------------------
// Mocks — hoisted before imports
// ---------------------------------------------------------------------------

const downloadFlowMock = jest.fn();
const removeApiKeysMock = jest.fn((flow: any) => flow);

jest.mock("@/utils/reactflowUtils", () => ({
  cleanEdges: jest.fn((_n: any, e: any) => ({ edges: e })),
  downloadFlow: (...args: any[]) => downloadFlowMock(...args),
  processFlowEdges: jest.fn(),
  processFlowNodes: jest.fn(),
  removeApiKeys: (flow: any) => removeApiKeysMock(flow),
  updateEdges: jest.fn(),
}));

// Minimal @xyflow/react stubs — the test never renders a real canvas.
jest.mock("@xyflow/react", () => ({
  Background: () => null,
  ReactFlow: () => <div data-testid="reactflow" />,
  ReactFlowProvider: ({ children }: any) => <>{children}</>,
  useNodesInitialized: () => true,
}));

jest.mock("react-error-boundary", () => ({
  ErrorBoundary: ({ children }: any) => <>{children}</>,
}));

jest.mock("../../../consts", () => ({
  nodeTypes: {},
  edgeTypes: {},
}));

// API mock — used by handleExportEntry to fetch the full history entry
const apiGetMock = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: any[]) => apiGetMock(...args), post: jest.fn() },
}));
jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/flows",
}));

// Query-hook mocks
const mockHistory = [
  {
    id: "entry-1",
    flow_id: "flow-1",
    user_id: "user-1",
    version_number: 1,
    version_tag: "v1",
    description: "first version",
    created_at: "2026-01-01T00:00:00Z",
  },
];

jest.mock("@/controllers/API/queries/flow-history", () => ({
  useGetFlowHistory: () => ({
    data: mockHistory,
    isLoading: false,
    isError: false,
  }),
  useGetFlowHistoryEntry: () => ({
    data: null,
    isLoading: false,
    isError: false,
  }),
  usePostCreateSnapshot: () => ({ mutate: jest.fn(), isPending: false }),
  useDeleteHistoryEntry: () => ({ mutate: jest.fn(), isPending: false }),
}));

jest.mock("@/hooks/flows/use-apply-flow-to-canvas", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));

// Store mocks
const mockCurrentFlow = {
  id: "flow-1",
  name: "Test Flow",
  description: "A test flow",
  data: { nodes: [{ id: "draft-node" }], edges: [] },
};

jest.mock("@/stores/flowStore", () => {
  const store: any = (selector: any) =>
    selector({
      currentFlow: mockCurrentFlow,
      nodes: [],
      edges: [],
      autoSaveFlow: undefined,
      inspectionPanelVisible: false,
    });
  store.getState = () => ({
    nodes: [],
    edges: [],
    autoSaveFlow: undefined,
    inspectionPanelVisible: false,
  });
  store.setState = jest.fn();
  return { __esModule: true, default: store };
});

const setErrorDataMock = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({
      setSuccessData: jest.fn(),
      setErrorData: setErrorDataMock,
    }),
}));

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

jest.mock("lodash", () => ({
  cloneDeep: jest.fn((obj: any) => JSON.parse(JSON.stringify(obj))),
}));

// ---------------------------------------------------------------------------
// Import the component AFTER all mocks are set up
// ---------------------------------------------------------------------------

import FlowHistoryPanel from "../index";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FlowHistoryPanel export", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("exports a history entry using removeApiKeys + downloadFlow", async () => {
    const user = userEvent.setup();
    const historyData = {
      nodes: [{ id: "hist-node", data: { node: { template: {} } } }],
      edges: [],
    };

    apiGetMock.mockResolvedValueOnce({
      data: {
        ...mockHistory[0],
        data: historyData,
        version_tag: "v1",
      },
    });

    render(<FlowHistoryPanel flowId="flow-1" onClose={jest.fn()} />);

    // Find the Export menu items — there's one for each history entry
    const exportItems = screen.getAllByRole("menuitem", { name: /Export/i });
    expect(exportItems.length).toBeGreaterThan(0);

    await user.click(exportItems[0]);

    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalledWith(
        "/api/v1/flows/flow-1/history/entry-1",
      );
    });

    await waitFor(() => {
      // Should call removeApiKeys with a flow-shaped object containing the version's data
      expect(removeApiKeysMock).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "flow-1",
          data: historyData,
          name: "Test Flow_v1",
          description: "A test flow",
          is_component: false,
        }),
      );
    });

    await waitFor(() => {
      // Should call downloadFlow with the result of removeApiKeys
      expect(downloadFlowMock).toHaveBeenCalledWith(
        expect.objectContaining({ data: historyData }),
        "Test Flow_v1",
        expect.any(String),
      );
    });
  });

  it("exports a history entry with the correct flow name and description", async () => {
    const user = userEvent.setup();
    const historyData = {
      nodes: [{ id: "v1-node" }],
      edges: [],
    };

    apiGetMock.mockResolvedValueOnce({
      data: { ...mockHistory[0], data: historyData, version_tag: "v1" },
    });

    render(<FlowHistoryPanel flowId="flow-1" onClose={jest.fn()} />);

    const exportItems = screen.getAllByRole("menuitem", { name: /Export/i });
    await user.click(exportItems[0]);

    await waitFor(() => {
      // The flow name passed to downloadFlow should include the version tag
      expect(downloadFlowMock).toHaveBeenCalledWith(
        expect.anything(),
        "Test Flow_v1",
        "A test flow",
      );
    });
  });

  it("shows error when export fails", async () => {
    const user = userEvent.setup();

    apiGetMock.mockRejectedValueOnce({
      response: { data: { detail: "Server error" } },
    });

    render(<FlowHistoryPanel flowId="flow-1" onClose={jest.fn()} />);

    const exportItems = screen.getAllByRole("menuitem", { name: /Export/i });
    await user.click(exportItems[0]);

    await waitFor(() => {
      expect(setErrorDataMock).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Failed to export version",
        }),
      );
    });

    // downloadFlow should NOT have been called
    expect(downloadFlowMock).not.toHaveBeenCalled();
  });
});
