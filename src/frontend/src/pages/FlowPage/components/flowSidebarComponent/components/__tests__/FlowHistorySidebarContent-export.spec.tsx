import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

const downloadFlowMock = jest.fn();
const removeApiKeysMock = jest.fn((flow: unknown) => flow);

jest.mock("@/utils/reactflowUtils", () => ({
  downloadFlow: (...args: unknown[]) => downloadFlowMock(...args),
  processFlows: jest.fn(),
  removeApiKeys: (flow: unknown) => removeApiKeysMock(flow),
}));

// API mock — used by handleExportEntry to fetch the full history entry
const apiGetMock = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => apiGetMock(...args), post: jest.fn() },
}));
jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/flows",
}));

// Query-hook mocks — returns the FlowHistoryListResponse wrapper shape
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

jest.mock("@/controllers/API/queries/flow-version", () => ({
  useGetFlowVersions: () => ({
    data: { entries: mockHistory, max_entries: 50 },
    isLoading: false,
    isError: false,
  }),
  useGetFlowVersionEntry: () => ({
    data: null,
    isLoading: false,
    isError: false,
  }),
  usePostCreateVersionSnapshot: () => ({
    mutate: jest.fn(),
    isPending: false,
  }),
  useDeleteFlowVersionEntry: () => ({ mutate: jest.fn(), isPending: false }),
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
  type FlowStoreState = {
    currentFlow: typeof mockCurrentFlow;
    nodes: unknown[];
    edges: unknown[];
    autoSaveFlow: undefined;
    inspectionPanelVisible: boolean;
  };
  type Selector<TState> = (state: TState) => unknown;
  type MockStore<TState> = ((selector: Selector<TState>) => unknown) & {
    getState: () => TState;
    setState: jest.Mock;
    subscribe: jest.Mock;
  };
  const flowStoreState: FlowStoreState = {
    currentFlow: mockCurrentFlow,
    nodes: [],
    edges: [],
    autoSaveFlow: undefined,
    inspectionPanelVisible: false,
  };
  const store = ((selector: Selector<FlowStoreState>) =>
    selector({
      ...flowStoreState,
    })) as MockStore<FlowStoreState>;
  store.getState = () => ({ ...flowStoreState });
  store.setState = jest.fn();
  store.subscribe = jest.fn(() => jest.fn());
  return { __esModule: true, default: store };
});

const setErrorDataMock = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      setSuccessData: jest.fn(),
      setErrorData: setErrorDataMock,
    }),
}));

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

jest.mock("@/components/ui/checkbox", () => ({
  Checkbox: () => <input type="checkbox" />,
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

jest.mock("lodash", () => ({
  cloneDeep: jest.fn((obj: unknown) =>
    obj === undefined ? undefined : JSON.parse(JSON.stringify(obj)),
  ),
}));

jest.mock("@/stores/historyPreviewStore", () => {
  type HistoryPreviewState = {
    previewNodes: null;
    previewEdges: null;
    previewLabel: null;
    setPreview: jest.Mock;
    clearPreview: jest.Mock;
    setPreviewLoading: jest.Mock;
  };
  type Selector<TState> = (state: TState) => unknown;
  type MockStore<TState> = ((selector: Selector<TState>) => unknown) & {
    getState: () => TState;
  };
  const state: HistoryPreviewState = {
    previewNodes: null,
    previewEdges: null,
    previewLabel: null,
    setPreview: jest.fn(),
    clearPreview: jest.fn(),
    setPreviewLoading: jest.fn(),
  };
  const store = ((selector: Selector<HistoryPreviewState>) =>
    selector({
      ...state,
    })) as MockStore<HistoryPreviewState>;
  store.getState = () => ({ ...state });
  return { __esModule: true, default: store };
});

// ---------------------------------------------------------------------------
// Import the component AFTER all mocks are set up
// ---------------------------------------------------------------------------

import FlowHistorySidebarContent from "../FlowHistorySidebarContent";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FlowHistorySidebarContent export", () => {
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

    render(<FlowHistorySidebarContent flowId="flow-1" />);

    // Find the Export menu items — there's one for each history entry
    const exportItems = screen.getAllByRole("menuitem", { name: /Export/i });
    expect(exportItems.length).toBeGreaterThan(0);

    await user.click(exportItems[0]);

    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalledWith(
        "/api/v1/flows/flow-1/versions/entry-1",
      );
    });

    await waitFor(() => {
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

    render(<FlowHistorySidebarContent flowId="flow-1" />);

    const exportItems = screen.getAllByRole("menuitem", { name: /Export/i });
    await user.click(exportItems[0]);

    await waitFor(() => {
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

    render(<FlowHistorySidebarContent flowId="flow-1" />);

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
