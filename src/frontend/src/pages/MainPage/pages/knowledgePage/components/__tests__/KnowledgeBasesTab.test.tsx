import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";

// ── Heavy / external dependency mocks ────────────────────────────────────────

interface MockTableRow {
  dir_name: string;
  name: string;
}
jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => ({
    __esModule: true,
    default: ({ rowData }: { rowData: MockTableRow[] }) => (
      <div data-testid="mock-table">
        {rowData?.map((row) => (
          <div key={row.dir_name} data-testid={`row-${row.dir_name}`}>
            {row.name}
          </div>
        ))}
      </div>
    ),
  }),
);

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/components/ui/loading", () => ({
  __esModule: true,
  default: () => <div data-testid="loading-spinner" />,
}));

const mockGetKnowledgeBases = jest.fn();
jest.mock(
  "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases",
  () => ({
    useGetKnowledgeBases: () => mockGetKnowledgeBases(),
  }),
);

const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();
const mockSetNoticeData = jest.fn();
type StoreSelector<TState> = ((state: TState) => unknown) | undefined;
jest.mock("@/stores/alertStore", () => {
  type AlertState = {
    setErrorData: jest.Mock;
    setSuccessData: jest.Mock;
    setNoticeData: jest.Mock;
  };
  const store = jest.fn((selector: StoreSelector<AlertState>) => {
    const state: AlertState = {
      setErrorData: mockSetErrorData,
      setSuccessData: mockSetSuccessData,
      setNoticeData: mockSetNoticeData,
    };
    return typeof selector === "function" ? selector(state) : state;
  });
  return { __esModule: true, default: store };
});

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: jest.fn((selector: StoreSelector<{ examples: never[] }>) => {
    const state = { examples: [] as never[] };
    return typeof selector === "function" ? selector(state) : state;
  }),
}));

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: jest.fn(
    (selector: StoreSelector<{ myCollectionId: string }>) => {
      const state = { myCollectionId: "my-collection" };
      return typeof selector === "function" ? selector(state) : state;
    },
  ),
}));

jest.mock("react-router-dom", () => ({
  useParams: () => ({ folderId: undefined }),
}));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));
jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));
jest.mock("@/customization/utils/analytics", () => ({ track: jest.fn() }));
jest.mock("@/utils/reactflowUtils", () => ({ updateIds: jest.fn() }));

interface MockDeleteModalProps {
  open: boolean;
  onConfirm: () => void;
  children?: React.ReactNode;
}
jest.mock("@/modals/deleteConfirmationModal", () => ({
  __esModule: true,
  default: ({ open, onConfirm, children }: MockDeleteModalProps) =>
    open ? (
      <div data-testid="delete-modal">
        <button data-testid="confirm-delete" onClick={onConfirm}>
          Confirm
        </button>
        {children}
      </div>
    ) : null,
}));

jest.mock("@/modals/knowledgeBaseUploadModal/KnowledgeBaseUploadModal", () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="upload-modal" /> : null,
}));

jest.mock("../KnowledgeBaseEmptyState", () => ({
  __esModule: true,
  default: ({
    handleCreateKnowledge,
  }: {
    handleCreateKnowledge: () => void;
  }) => (
    <div data-testid="empty-state">
      <button data-testid="create-flow-btn" onClick={handleCreateKnowledge}>
        Create Flow
      </button>
    </div>
  ),
}));

jest.mock("../KnowledgeBaseSelectionOverlay", () => ({
  __esModule: true,
  default: () => <div data-testid="selection-overlay" />,
}));

jest.mock("../../hooks/useKnowledgeBasePolling", () => ({
  useKnowledgeBasePolling: () => ({ pollingRef: { current: false } }),
}));

jest.mock("../../hooks/useOptimisticKnowledgeBase", () => ({
  useOptimisticKnowledgeBase: () => ({
    captureSubmit: jest.fn(),
    applyOptimisticUpdate: jest.fn(() => false),
  }),
}));

jest.mock("../../config/knowledgeBaseColumns", () => ({
  createKnowledgeBaseColumns: () => [{ headerName: "Name", field: "name" }],
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

// ── Utilities ────────────────────────────────────────────────────────────────

import KnowledgeBasesTab from "../KnowledgeBasesTab";

const makeKb = (
  overrides: Partial<KnowledgeBaseInfo> = {},
): KnowledgeBaseInfo => ({
  id: "kb-1",
  dir_name: "my_kb",
  name: "My KB",
  embedding_provider: "OpenAI",
  embedding_model: "text-embedding-3-small",
  size: 0,
  words: 0,
  characters: 0,
  chunks: 0,
  avg_chunk_size: 0,
  status: "ready",
  ...overrides,
});

const createWrapper = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
};

const defaultProps = {
  quickFilterText: "",
  setQuickFilterText: jest.fn(),
  selectedFiles: [] as KnowledgeBaseInfo[],
  setSelectedFiles: jest.fn(),
  quantitySelected: 0,
  setQuantitySelected: jest.fn(),
  isShiftPressed: false,
  onRowClick: jest.fn(),
};

beforeEach(() => {
  jest.clearAllMocks();
  mockListFilter.mockImplementation(actualListFilter);
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("KnowledgeBasesTab", () => {
  describe("Loading state", () => {
    it("shows loading spinner while knowledge bases are fetching", () => {
      mockGetKnowledgeBases.mockReturnValue({
        isLoading: true,
        data: undefined,
        error: null,
        refetch: jest.fn(),
      });
      render(<KnowledgeBasesTab {...defaultProps} />, {
        wrapper: createWrapper(),
      });
      expect(screen.getByTestId("loading-spinner")).toBeInTheDocument();
      expect(
        screen.getByText("Loading Knowledge Bases..."),
      ).toBeInTheDocument();
    });
  });

  describe("Empty state", () => {
    it("renders empty state component when knowledge base list is empty", () => {
      mockGetKnowledgeBases.mockReturnValue({
        isLoading: false,
        data: [],
        error: null,
        refetch: jest.fn(),
      });
      render(<KnowledgeBasesTab {...defaultProps} />, {
        wrapper: createWrapper(),
      });
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });
  });

  describe("With data", () => {
    const kbs = [
      makeKb({ dir_name: "kb_one", name: "KB One", status: "ready" }),
      makeKb({ dir_name: "kb_two", name: "KB Two", status: "empty" }),
    ];

    beforeEach(() => {
      mockGetKnowledgeBases.mockReturnValue({
        isLoading: false,
        data: kbs,
        error: null,
        refetch: jest.fn(),
      });
    });

    it("renders the search input", () => {
      render(<KnowledgeBasesTab {...defaultProps} />, {
        wrapper: createWrapper(),
      });
      expect(screen.getByTestId("search-kb-input")).toBeInTheDocument();
    });

    it("calls setQuickFilterText when typing in the search input", () => {
      const setQuickFilterText = jest.fn();
      render(
        <KnowledgeBasesTab
          {...defaultProps}
          setQuickFilterText={setQuickFilterText}
        />,
        { wrapper: createWrapper() },
      );
      fireEvent.change(screen.getByTestId("search-kb-input"), {
        target: { value: "KB One" },
      });
      expect(setQuickFilterText).toHaveBeenCalledWith("KB One");
    });

    it("shows the Add Knowledge button when nothing is selected", () => {
      render(<KnowledgeBasesTab {...defaultProps} quantitySelected={0} />, {
        wrapper: createWrapper(),
      });
      expect(
        screen.getByRole("button", { name: /Add Knowledge/i }),
      ).toBeInTheDocument();
    });

    it("shows the Delete(N) button instead of Add Knowledge when items are selected", () => {
      render(<KnowledgeBasesTab {...defaultProps} quantitySelected={2} />, {
        wrapper: createWrapper(),
      });
      expect(
        screen.getByRole("button", { name: /Delete \(2\)/i }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /Add Knowledge/i }),
      ).not.toBeInTheDocument();
    });

    it("passes sorted KB rows to the table", () => {
      render(<KnowledgeBasesTab {...defaultProps} />, {
        wrapper: createWrapper(),
      });
      // KB One (alphabetically first) should appear before KB Two
      const rows = screen.getAllByTestId(/^row-/);
      expect(rows[0]).toHaveTextContent("KB One");
      expect(rows[1]).toHaveTextContent("KB Two");
    });
  });

  describe("Upload modal", () => {
    beforeEach(() => {
      mockGetKnowledgeBases.mockReturnValue({
        isLoading: false,
        data: [makeKb()],
        error: null,
        refetch: jest.fn(),
      });
    });

    it("opens the upload modal when Add Knowledge is clicked", async () => {
      const user = userEvent.setup();
      render(<KnowledgeBasesTab {...defaultProps} />, {
        wrapper: createWrapper(),
      });

      await user.click(screen.getByRole("button", { name: /Add Knowledge/i }));
      expect(screen.getByTestId("upload-modal")).toBeInTheDocument();
    });
  });

  describe("Bulk delete modal", () => {
    beforeEach(() => {
      mockGetKnowledgeBases.mockReturnValue({
        isLoading: false,
        data: [makeKb()],
        error: null,
        refetch: jest.fn(),
      });
    });

    it("opens the bulk delete modal when Delete(N) button is clicked", async () => {
      const user = userEvent.setup();
      render(
        <KnowledgeBasesTab
          {...defaultProps}
          quantitySelected={1}
          selectedFiles={[makeKb()]}
        />,
        { wrapper: createWrapper() },
      );

      await user.click(screen.getByRole("button", { name: /Delete \(1\)/i }));
      await waitFor(() =>
        expect(screen.getByTestId("delete-modal")).toBeInTheDocument(),
      );
    });
  });

  describe("Error handling", () => {
    it("calls setErrorData when the query fails", () => {
      const error = new Error("Fetch failed");
      mockGetKnowledgeBases.mockReturnValue({
        isLoading: false,
        data: undefined,
        error,
        refetch: jest.fn(),
      });
      render(<KnowledgeBasesTab {...defaultProps} />, {
        wrapper: createWrapper(),
      });
      expect(mockSetErrorData).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Failed to load knowledge bases" }),
      );
    });
  });

  describe("Ownership filter seam", () => {
    const ownedOnly = <T,>(
      _type: string,
      items: T[],
      isOwned: (item: T) => boolean,
    ) => ({
      items: items.filter(isOwned),
      tools: <button type="button">Owned</button>,
    });
    const mine = makeKb({ dir_name: "z_mine", name: "Zeta", is_owner: true });
    const shared = makeKb({
      dir_name: "a_shared",
      name: "Alpha",
      is_owner: false,
    });
    const legacy = makeKb({ dir_name: "m_legacy", name: "Mu" });
    const nullOwner = makeKb({
      dir_name: "n_null",
      name: "Nu",
      is_owner: null,
    });

    const renderWith = (data: KnowledgeBaseInfo[]) => {
      mockGetKnowledgeBases.mockReturnValue({
        isLoading: false,
        data,
        error: null,
        refetch: jest.fn(),
      });
      render(<KnowledgeBasesTab {...defaultProps} />, {
        wrapper: createWrapper(),
      });
    };
    const rowIds = () =>
      screen.getAllByTestId(/^row-/).map((row) => row.dataset.testid);

    it("should_render_every_kb_sorted_with_no_tools_when_the_seam_is_the_default", () => {
      renderWith([mine, shared, legacy]);

      expect(rowIds()).toEqual(["row-a_shared", "row-m_legacy", "row-z_mine"]);
      expect(
        screen.queryByRole("button", { name: "Owned" }),
      ).not.toBeInTheDocument();
    });

    it("should_give_the_seam_the_raw_list_and_an_is_owner_rule", () => {
      const data = [mine, shared, legacy, nullOwner];
      renderWith(data);

      const [type, items, isOwned] = mockListFilter.mock.calls.at(-1);
      expect(type).toBe("knowledge_base");
      expect(items).toBe(data);
      expect(items.map(isOwned)).toEqual([true, false, true, true]);
    });

    it("should_sort_only_the_filtered_rows_and_show_the_tools_in_the_toolbar", () => {
      mockListFilter.mockImplementation(ownedOnly);
      renderWith([mine, shared, legacy]);

      expect(rowIds()).toEqual(["row-m_legacy", "row-z_mine"]);
      const toolsBox = screen.getByTestId("kb-list-tools");
      expect(toolsBox).toContainElement(
        screen.getByRole("button", { name: "Owned" }),
      );
      // 8px from search (matches Files) and never squeezed at 1024px.
      expect(toolsBox).toHaveClass("ml-2", "shrink-0");
      expect(toolsBox.nextElementSibling).toBe(
        screen.getByRole("button", { name: /Add Knowledge/i }),
      );
    });

    it("should_not_add_a_tools_box_when_the_seam_has_no_tools", () => {
      renderWith([mine, shared]);

      expect(screen.queryByTestId("kb-list-tools")).not.toBeInTheDocument();
    });

    it("should_show_the_existing_empty_state_with_the_tools_when_every_kb_is_shared", () => {
      mockListFilter.mockImplementation(ownedOnly);
      renderWith([
        shared,
        makeKb({ dir_name: "b", name: "B", is_owner: false }),
      ]);

      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
      expect(screen.queryByTestId("mock-table")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Owned" })).toBeInTheDocument();
    });

    it("should_give_the_seam_an_empty_list_and_show_the_empty_state_when_there_are_no_kbs", () => {
      mockListFilter.mockImplementation(ownedOnly);
      renderWith([]);

      expect(mockListFilter.mock.calls.at(-1)?.[1]).toEqual([]);
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    it("should_render_one_row_per_owned_kb_when_there_are_many", () => {
      mockListFilter.mockImplementation(ownedOnly);
      const many = Array.from({ length: 30 }, (_, index) =>
        makeKb({
          dir_name: `kb_${String(index).padStart(2, "0")}`,
          name: `KB ${String(index).padStart(2, "0")}`,
          is_owner: index % 3 !== 0,
        }),
      );
      renderWith(many);

      expect(screen.getAllByTestId(/^row-/)).toHaveLength(20);
    });
  });
});
