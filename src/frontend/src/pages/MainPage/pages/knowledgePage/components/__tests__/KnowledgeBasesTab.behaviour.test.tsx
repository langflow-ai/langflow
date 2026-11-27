import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";

// Behaviour of the tab around the grid: ingestion toasts, row and keyboard
// activation, the create flow, and the ownership seam's tools and labels.

type TableProps = {
  rowData: KnowledgeBaseInfo[];
  onRowClicked?: (event: unknown) => void;
  onCellKeyDown?: (event: unknown) => void;
};
let mockTableProps: TableProps = { rowData: [] };
jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => ({
    __esModule: true,
    default: (props: TableProps) => {
      mockTableProps = props;
      return (
        <div data-testid="mock-table">
          {props.rowData.map((row) => (
            <div key={row.dir_name} data-testid={`row-${row.dir_name}`}>
              {row.name}
            </div>
          ))}
        </div>
      );
    },
  }),
);

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/components/ui/loading", () => ({
  __esModule: true,
  default: () => <div data-testid="loading-spinner" />,
}));

const mockGetKnowledgeBases = jest.fn();
jest.mock(
  "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases",
  () => ({ useGetKnowledgeBases: () => mockGetKnowledgeBases() }),
);

const mockApiGet = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockApiGet(...args) },
}));

const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();
const mockSetNoticeData = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, jest.Mock>) => unknown) =>
    selector({
      setErrorData: mockSetErrorData,
      setSuccessData: mockSetSuccessData,
      setNoticeData: mockSetNoticeData,
    }),
}));

let mockExamples: Array<{ name: string; data?: unknown }> = [];
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { examples: unknown[] }) => unknown) =>
    selector({ examples: mockExamples }),
}));
jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: (selector: (state: { myCollectionId: string }) => unknown) =>
    selector({ myCollectionId: "my-collection" }),
}));
jest.mock("react-router-dom", () => ({ useParams: () => ({}) }));
const mockNavigate = jest.fn();
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));
const mockAddFlow = jest.fn();
jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => mockAddFlow,
}));
const mockTrack = jest.fn();
jest.mock("@/customization/utils/analytics", () => ({
  track: (...args: unknown[]) => mockTrack(...args),
}));
jest.mock("@/utils/reactflowUtils", () => ({ updateIds: jest.fn() }));

jest.mock("@/modals/deleteConfirmationModal", () => ({
  __esModule: true,
  default: ({ open, description }: { open: boolean; description: string }) =>
    open ? <div data-testid="delete-modal">{description}</div> : null,
}));
jest.mock("@/modals/knowledgeBaseUploadModal/KnowledgeBaseUploadModal", () => ({
  __esModule: true,
  default: ({
    open,
    setOpen,
    existingKnowledgeBase,
  }: {
    open: boolean;
    setOpen: (open: boolean) => void;
    existingKnowledgeBase?: { name: string };
  }) =>
    open ? (
      <div data-testid="upload-modal">
        {existingKnowledgeBase?.name ?? "new"}
        <button type="button" onClick={() => setOpen(false)}>
          close-upload
        </button>
      </div>
    ) : null,
}));
jest.mock("../KnowledgeBaseEmptyState", () => ({
  __esModule: true,
  default: ({
    handleCreateKnowledge,
  }: {
    handleCreateKnowledge: () => void;
  }) => (
    <div data-testid="empty-state">
      <button type="button" onClick={handleCreateKnowledge}>
        create-from-template
      </button>
    </div>
  ),
}));

type StatusTransition = { kb: KnowledgeBaseInfo; previousStatus?: string };
let mockOnStatusChange: ((t: StatusTransition[]) => void) | undefined;
jest.mock("../../hooks/useKnowledgeBasePolling", () => ({
  useKnowledgeBasePolling: (options: {
    onStatusChange: (t: StatusTransition[]) => void;
  }) => {
    mockOnStatusChange = options.onStatusChange;
    return { pollingRef: { current: false } };
  },
}));
jest.mock("../../hooks/useOptimisticKnowledgeBase", () => ({
  useOptimisticKnowledgeBase: () => ({
    captureSubmit: jest.fn(),
    applyOptimisticUpdate: () => false,
  }),
}));

type Callbacks = {
  onViewChunks?: (kb: KnowledgeBaseInfo) => void;
  onDelete?: (kb: KnowledgeBaseInfo) => void;
  onAddSources?: (kb: KnowledgeBaseInfo) => void;
};
let mockCallbacks: Callbacks = {};
jest.mock("../../config/knowledgeBaseColumns", () => ({
  createKnowledgeBaseColumns: (callbacks: Callbacks) => {
    mockCallbacks = callbacks;
    return [{ headerName: "Name", field: "name" }];
  },
  isKnowledgeBaseOwned: jest.requireActual("../../config/knowledgeBaseColumns")
    .isKnowledgeBaseOwned,
}));

const mockListFilter = jest.fn();
jest.mock("@/customization/hooks/use-custom-resource-list-filter", () => ({
  useCustomResourceListFilter: (...args: unknown[]) => mockListFilter(...args),
}));
const actualListFilter = jest.requireActual(
  "@/customization/hooks/use-custom-resource-list-filter",
).useCustomResourceListFilter;

import KnowledgeBasesTab from "../KnowledgeBasesTab";

const makeKb = (
  overrides: Partial<KnowledgeBaseInfo> = {},
): KnowledgeBaseInfo => ({
  id: "kb-1",
  dir_name: "my_kb",
  name: "My KB",
  size: 0,
  words: 0,
  characters: 0,
  chunks: 12,
  avg_chunk_size: 0,
  status: "ready",
  ...overrides,
});

const onRowClick = jest.fn();
const renderTab = (data: KnowledgeBaseInfo[] | undefined) => {
  mockGetKnowledgeBases.mockReturnValue({
    isLoading: false,
    data,
    error: null,
    refetch: mockRefetch,
  });
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <KnowledgeBasesTab
        quickFilterText=""
        setQuickFilterText={jest.fn()}
        selectedFiles={[]}
        setSelectedFiles={jest.fn()}
        quantitySelected={0}
        setQuantitySelected={jest.fn()}
        isShiftPressed={false}
        onRowClick={onRowClick}
      />
    </QueryClientProvider>,
  );
};
const mockRefetch = jest.fn();

const run = (overrides: Record<string, unknown>) => ({
  data: {
    runs: [
      {
        status: "succeeded",
        succeeded: 0,
        skipped: 0,
        failed: 0,
        chunks_created: 0,
        ...overrides,
      },
    ],
  },
});

beforeEach(() => {
  jest.clearAllMocks();
  mockExamples = [];
  mockListFilter.mockImplementation(actualListFilter);
});

describe("KnowledgeBasesTab ingestion toasts", () => {
  const finish = (kb: KnowledgeBaseInfo) =>
    act(() => {
      mockOnStatusChange?.([{ kb, previousStatus: "ingesting" }]);
    });

  it("should_show_an_error_with_the_reason_when_ingestion_fails", () => {
    renderTab([makeKb()]);
    act(() => {
      mockOnStatusChange?.([
        {
          kb: makeKb({ status: "failed", failure_reason: "Bad PDF" }),
          previousStatus: "ingesting",
        },
      ]);
    });

    expect(mockSetErrorData).toHaveBeenCalledWith(
      expect.objectContaining({ list: ["Bad PDF"] }),
    );
  });

  it("should_not_repeat_the_error_when_the_kb_was_already_failed", () => {
    renderTab([makeKb()]);
    act(() => {
      mockOnStatusChange?.([
        { kb: makeKb({ status: "failed" }), previousStatus: "failed" },
      ]);
    });

    expect(mockSetErrorData).not.toHaveBeenCalled();
  });

  it("should_show_success_when_the_latest_run_succeeded", async () => {
    mockApiGet.mockResolvedValue(
      run({ status: "succeeded", chunks_created: 9 }),
    );
    renderTab([makeKb()]);
    finish(makeKb());

    await waitFor(() => expect(mockSetSuccessData).toHaveBeenCalledTimes(1));
    expect(mockApiGet).toHaveBeenCalledWith(
      expect.stringContaining("/my_kb/runs?page=1&limit=1"),
    );
  });

  it("should_show_a_notice_with_the_breakdown_when_the_run_was_partial", async () => {
    mockApiGet.mockResolvedValue(
      run({
        status: "partial",
        succeeded: 2,
        skipped: 1,
        failed: 1,
        chunks_created: 5,
      }),
    );
    renderTab([makeKb()]);
    finish(makeKb());

    await waitFor(() =>
      expect(mockSetNoticeData).toHaveBeenCalledWith({
        title:
          '"My KB" ingestion finished with issues — 2 succeeded, 1 skipped, 1 failed · 5 chunks ingested',
      }),
    );
    expect(mockSetSuccessData).not.toHaveBeenCalled();
  });

  it("should_say_no_items_processed_when_a_partial_run_has_no_counts", async () => {
    mockApiGet.mockResolvedValue(run({ status: "partial" }));
    renderTab([makeKb()]);
    finish(makeKb());

    await waitFor(() =>
      expect(mockSetNoticeData).toHaveBeenCalledWith({
        title: '"My KB" ingestion finished with issues — no items processed',
      }),
    );
  });

  it("should_show_a_neutral_notice_when_the_run_was_cancelled", async () => {
    mockApiGet.mockResolvedValue(run({ status: "cancelled" }));
    renderTab([makeKb()]);
    finish(makeKb());

    await waitFor(() =>
      expect(mockSetNoticeData).toHaveBeenCalledWith({
        title: '"My KB" ingestion cancelled — cancelled',
      }),
    );
  });

  it("should_fall_back_to_success_when_the_run_lookup_fails", async () => {
    mockApiGet.mockRejectedValue(new Error("offline"));
    renderTab([makeKb()]);
    finish(makeKb());

    await waitFor(() => expect(mockSetSuccessData).toHaveBeenCalledTimes(1));
    expect(mockSetNoticeData).not.toHaveBeenCalled();
  });
});

describe("KnowledgeBasesTab row activation", () => {
  const kb = makeKb();
  const keyDown = (colId: string, key: string, target: HTMLElement) => {
    const event = new KeyboardEvent("keydown", { key, cancelable: true });
    Object.defineProperty(event, "target", { value: target });
    act(() => {
      mockTableProps.onCellKeyDown?.({
        column: { getColId: () => colId },
        data: kb,
        event,
      });
    });
    return event;
  };

  it("should_open_the_kb_when_a_row_is_clicked_outside_its_buttons", () => {
    renderTab([kb]);
    const cell = document.createElement("div");

    mockTableProps.onRowClicked?.({ event: { target: cell }, data: kb });

    expect(onRowClick).toHaveBeenCalledWith(kb);
  });

  it("should_not_open_the_kb_when_the_click_lands_on_a_row_button", () => {
    renderTab([kb]);
    const button = document.createElement("button");

    mockTableProps.onRowClicked?.({ event: { target: button }, data: kb });

    expect(onRowClick).not.toHaveBeenCalled();
  });

  it("should_open_the_kb_when_enter_is_pressed_on_a_data_cell", () => {
    renderTab([kb]);

    const event = keyDown("name", "Enter", document.createElement("div"));

    expect(onRowClick).toHaveBeenCalledWith(kb);
    expect(event.defaultPrevented).toBe(true);
  });

  it("should_ignore_enter_when_focus_is_on_a_control_inside_the_row", () => {
    renderTab([kb]);

    keyDown("name", "Enter", document.createElement("button"));
    keyDown("name", "a", document.createElement("div"));

    expect(onRowClick).not.toHaveBeenCalled();
  });

  it("should_forward_enter_to_the_row_actions_trigger_in_the_actions_cell", () => {
    renderTab([kb]);
    const gridCell = document.createElement("div");
    gridCell.setAttribute("role", "gridcell");
    const trigger = document.createElement("button");
    trigger.dataset.testid = "kb-row-actions-trigger";
    const inner = document.createElement("span");
    gridCell.append(trigger, inner);
    const forwarded = jest.fn();
    trigger.addEventListener("keydown", (event) => forwarded(event.key));

    const event = keyDown("actions", " ", inner);

    expect(forwarded).toHaveBeenCalledWith(" ");
    expect(event.defaultPrevented).toBe(true);
    expect(onRowClick).not.toHaveBeenCalled();
  });

  it("should_leave_other_keys_and_the_trigger_itself_alone_in_the_actions_cell", () => {
    renderTab([kb]);
    const forwarded = jest.fn();
    const trigger = document.createElement("button");
    trigger.addEventListener("keydown", forwarded);

    keyDown("actions", "a", document.createElement("div"));
    keyDown("actions", "Enter", trigger);
    keyDown("actions", "Enter", document.createElement("div"));

    expect(forwarded).not.toHaveBeenCalled();
    expect(onRowClick).not.toHaveBeenCalled();
  });

  it("should_view_chunks_through_the_row_click_handler_when_no_viewer_is_given", () => {
    renderTab([kb]);

    act(() => mockCallbacks.onViewChunks?.(kb));

    expect(onRowClick).toHaveBeenCalledWith(kb);
  });
});

describe("KnowledgeBasesTab actions", () => {
  it("should_open_the_upload_modal_for_that_kb_when_add_sources_is_chosen", () => {
    renderTab([makeKb()]);

    act(() => mockCallbacks.onAddSources?.(makeKb()));

    expect(screen.getByTestId("upload-modal")).toHaveTextContent("my_kb");
  });

  it("should_refetch_when_the_upload_modal_closes_without_submitted_files", () => {
    renderTab([makeKb()]);
    act(() => mockCallbacks.onAddSources?.(makeKb()));

    fireEvent.click(screen.getByRole("button", { name: "close-upload" }));

    expect(mockRefetch).toHaveBeenCalled();
    expect(screen.queryByTestId("upload-modal")).not.toBeInTheDocument();
  });

  it("should_ask_for_confirmation_naming_the_kb_when_delete_is_chosen", () => {
    renderTab([makeKb()]);

    act(() => mockCallbacks.onDelete?.(makeKb()));

    expect(screen.getByTestId("delete-modal")).toHaveTextContent(
      'knowledge base "My KB"',
    );
  });

  it("should_create_a_flow_from_the_ingestion_template_from_the_empty_state", async () => {
    mockExamples = [{ name: "Knowledge Ingestion", data: { nodes: [] } }];
    mockAddFlow.mockResolvedValue("new-flow");
    renderTab([]);

    fireEvent.click(
      screen.getByRole("button", { name: "create-from-template" }),
    );

    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith(
        "/flow/new-flow/folder/my-collection",
      ),
    );
    expect(mockTrack).toHaveBeenCalledWith("New Flow Created", {
      template: "Knowledge Ingestion Template",
    });
  });

  it("should_do_nothing_from_the_empty_state_when_the_template_is_missing", () => {
    renderTab([]);

    fireEvent.click(
      screen.getByRole("button", { name: "create-from-template" }),
    );

    expect(mockAddFlow).not.toHaveBeenCalled();
  });
});

describe("KnowledgeBasesTab ownership seam", () => {
  const ownedOnly = <T,>(
    _type: string,
    items: T[],
    isOwned: (item: T) => boolean,
  ) => ({
    items: items.filter(isOwned),
    tools: <button type="button">Owned</button>,
  });

  it("should_render_the_seam_tools_and_its_filtered_rows_when_kbs_are_mixed", () => {
    mockListFilter.mockImplementation(ownedOnly);
    renderTab([
      makeKb({ dir_name: "mine", name: "Mine", is_owner: true }),
      makeKb({ dir_name: "shared", name: "Shared", is_owner: false }),
    ]);

    expect(screen.getByRole("button", { name: "Owned" })).toBeInTheDocument();
    expect(mockTableProps.rowData.map((row) => row.dir_name)).toEqual(["mine"]);
  });

  it("should_keep_the_seam_tools_on_the_empty_state_when_every_kb_is_shared", () => {
    mockListFilter.mockImplementation(ownedOnly);
    renderTab([makeKb({ is_owner: false })]);

    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Owned" })).toBeInTheDocument();
  });

  it("should_show_the_loading_state_and_no_tools_while_kbs_load", () => {
    mockListFilter.mockImplementation(ownedOnly);
    renderTab(undefined);

    expect(screen.getByTestId("loading-spinner")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Owned" }),
    ).not.toBeInTheDocument();
  });
});
