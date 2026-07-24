import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import type { FileType } from "@/types/file_management";

// ── Heavy / external dependency mocks ────────────────────────────────────────

interface MockTableProps {
  rowData?: FileType[];
  quickFilterText?: string;
  onSelectionChanged?: (event: {
    api: { getSelectedRows: () => FileType[] };
  }) => void;
}

let mockLatestTableProps: MockTableProps = {};
jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => {
    const ReactActual = jest.requireActual<typeof React>("react");
    return {
      __esModule: true,
      default: ReactActual.forwardRef((props: MockTableProps, _ref) => {
        mockLatestTableProps = props;
        return (
          <div data-testid="mock-table">
            {props.rowData?.map((row) => (
              <div key={row.id} data-testid={`row-${row.id}`}>
                {row.name}
              </div>
            ))}
          </div>
        );
      }),
    };
  },
);

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/components/ui/loading", () => ({
  __esModule: true,
  default: () => <div data-testid="loading-spinner" />,
}));

jest.mock("@/components/core/cardsWrapComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="empty-state-wrapper">{children}</div>
  ),
}));

jest.mock("../dragWrapComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="drag-wrapper">{children}</div>
  ),
}));

const mockGetFiles = jest.fn();
jest.mock("@/controllers/API/queries/file-management", () => ({
  useGetFilesV2: () => mockGetFiles(),
}));

const mockDeleteFiles = jest.fn();
jest.mock("@/controllers/API/queries/file-management/use-delete-files", () => ({
  useDeleteFilesV2: () => ({ mutate: mockDeleteFiles, isPending: false }),
}));

const mockRename = jest.fn();
jest.mock(
  "@/controllers/API/queries/file-management/use-put-rename-file",
  () => ({
    usePostRenameFileV2: () => ({ mutate: mockRename }),
  }),
);

const mockUploadDirect = jest.fn();
jest.mock("@/customization/hooks/use-custom-post-upload-file", () => ({
  customPostUploadFileV2: () => ({ mutate: mockUploadDirect }),
}));

const mockUploadFile = jest.fn().mockResolvedValue([]);
jest.mock("@/hooks/files/use-upload-file", () => ({
  __esModule: true,
  default: () => mockUploadFile,
}));

const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();
type StoreSelector<TState> = ((state: TState) => unknown) | undefined;
jest.mock("@/stores/alertStore", () => {
  type AlertState = {
    setErrorData: jest.Mock;
    setSuccessData: jest.Mock;
  };
  const store = jest.fn((selector: StoreSelector<AlertState>) => {
    const state: AlertState = {
      setErrorData: mockSetErrorData,
      setSuccessData: mockSetSuccessData,
    };
    return typeof selector === "function" ? selector(state) : state;
  });
  return { __esModule: true, default: store };
});

interface MockDeleteModalProps {
  children?: React.ReactNode;
  onConfirm: () => void;
}
jest.mock("@/modals/deleteConfirmationModal", () => ({
  __esModule: true,
  default: ({ children, onConfirm }: MockDeleteModalProps) => (
    <div data-testid="delete-modal">
      {children}
      <button data-testid="confirm-delete" onClick={onConfirm}>
        Confirm
      </button>
    </div>
  ),
}));

jest.mock(
  "@/modals/fileManagerModal/components/filesContextMenuComponent",
  () => ({
    __esModule: true,
    default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  }),
);

// ── Utilities ────────────────────────────────────────────────────────────────

import FilesTab from "../FilesTab";

const makeFile = (overrides: Partial<FileType> = {}): FileType => ({
  id: "file-1",
  user_id: "user-1",
  provider: "local",
  name: "report",
  path: "files/report.pdf",
  created_at: "2024-01-01T00:00:00",
  updated_at: "2024-01-02T00:00:00",
  size: 2048,
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
  selectedFiles: [] as FileType[],
  setSelectedFiles: jest.fn(),
  quantitySelected: 0,
  setQuantitySelected: jest.fn(),
  isShiftPressed: false,
};

beforeEach(() => {
  jest.clearAllMocks();
  mockLatestTableProps = {};
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("FilesTab", () => {
  describe("Loading state", () => {
    it("shows the loading spinner while files are fetching", () => {
      mockGetFiles.mockReturnValue({ data: undefined });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });
      expect(screen.getByTestId("loading-spinner")).toBeInTheDocument();
      expect(screen.queryByTestId("mock-table")).not.toBeInTheDocument();
    });
  });

  describe("Empty state", () => {
    it("renders the empty state with an upload button and no table", () => {
      mockGetFiles.mockReturnValue({ data: [] });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });
      expect(screen.getByTestId("empty-state-wrapper")).toBeInTheDocument();
      expect(screen.getByTestId("upload-file-btn")).toBeInTheDocument();
      expect(screen.queryByTestId("mock-table")).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("search-store-input"),
      ).not.toBeInTheDocument();
    });
  });

  describe("With data", () => {
    const older = makeFile({
      id: "file-old",
      name: "older",
      updated_at: "2024-01-02T00:00:00",
    });
    const newer = makeFile({
      id: "file-new",
      name: "newer",
      updated_at: "2024-06-01T00:00:00",
    });

    beforeEach(() => {
      mockGetFiles.mockReturnValue({ data: [older, newer] });
    });

    it("renders one row per file, sorted by most recent first", () => {
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });
      const rows = screen.getAllByTestId(/^row-/);
      expect(rows).toHaveLength(2);
      expect(rows[0]).toHaveTextContent("newer");
      expect(rows[1]).toHaveTextContent("older");
    });

    it("calls setQuickFilterText when typing in the search input", () => {
      const setQuickFilterText = jest.fn();
      render(
        <FilesTab {...defaultProps} setQuickFilterText={setQuickFilterText} />,
        { wrapper: createWrapper() },
      );
      fireEvent.change(screen.getByTestId("search-store-input"), {
        target: { value: "report" },
      });
      expect(setQuickFilterText).toHaveBeenCalledWith("report");
    });

    it("forwards quickFilterText to the table quick filter", () => {
      render(<FilesTab {...defaultProps} quickFilterText="pdf" />, {
        wrapper: createWrapper(),
      });
      expect(mockLatestTableProps.quickFilterText).toBe("pdf");
    });

    it("shows the upload button when nothing is selected", () => {
      render(<FilesTab {...defaultProps} quantitySelected={0} />, {
        wrapper: createWrapper(),
      });
      expect(screen.getByTestId("upload-file-btn")).toBeInTheDocument();
      expect(screen.queryByTestId("bulk-delete-btn")).not.toBeInTheDocument();
    });

    it("shows the bulk delete button instead of upload when rows are selected", () => {
      render(
        <FilesTab
          {...defaultProps}
          quantitySelected={2}
          selectedFiles={[older, newer]}
        />,
        { wrapper: createWrapper() },
      );
      expect(screen.getByTestId("bulk-delete-btn")).toBeInTheDocument();
      expect(screen.queryByTestId("upload-file-btn")).not.toBeInTheDocument();
    });

    it("propagates ag-grid selection to the page state", () => {
      const setSelectedFiles = jest.fn();
      const setQuantitySelected = jest.fn();
      render(
        <FilesTab
          {...defaultProps}
          setSelectedFiles={setSelectedFiles}
          setQuantitySelected={setQuantitySelected}
        />,
        { wrapper: createWrapper() },
      );
      setSelectedFiles.mockClear();
      setQuantitySelected.mockClear();
      act(() => {
        mockLatestTableProps.onSelectionChanged?.({
          api: { getSelectedRows: () => [newer] },
        });
      });
      expect(setSelectedFiles).toHaveBeenCalledWith([newer]);
      expect(setQuantitySelected).toHaveBeenCalledWith(1);
    });

    it("clears the selected quantity shortly after selection is emptied", () => {
      jest.useFakeTimers();
      try {
        const setQuantitySelected = jest.fn();
        render(
          <FilesTab
            {...defaultProps}
            setQuantitySelected={setQuantitySelected}
          />,
          { wrapper: createWrapper() },
        );
        setQuantitySelected.mockClear();
        act(() => {
          mockLatestTableProps.onSelectionChanged?.({
            api: { getSelectedRows: () => [] },
          });
        });
        expect(setQuantitySelected).not.toHaveBeenCalled();
        act(() => {
          jest.advanceTimersByTime(300);
        });
        expect(setQuantitySelected).toHaveBeenCalledWith(0);
      } finally {
        jest.useRealTimers();
      }
    });

    it("resets the selection when file data arrives", () => {
      const setSelectedFiles = jest.fn();
      const setQuantitySelected = jest.fn();
      render(
        <FilesTab
          {...defaultProps}
          setSelectedFiles={setSelectedFiles}
          setQuantitySelected={setQuantitySelected}
        />,
        { wrapper: createWrapper() },
      );
      expect(setQuantitySelected).toHaveBeenCalledWith(0);
      expect(setSelectedFiles).toHaveBeenCalledWith([]);
    });
  });

  describe("Bulk delete through the confirmation modal", () => {
    const fileA = makeFile({ id: "file-a", name: "alpha" });
    const fileB = makeFile({ id: "file-b", name: "beta" });

    beforeEach(() => {
      mockGetFiles.mockReturnValue({ data: [fileA, fileB] });
    });

    const renderWithSelection = (
      extra: Partial<React.ComponentProps<typeof FilesTab>> = {},
    ) =>
      render(
        <FilesTab
          {...defaultProps}
          quantitySelected={2}
          selectedFiles={[fileA, fileB]}
          {...extra}
        />,
        { wrapper: createWrapper() },
      );

    it("deletes the selected file ids when the modal confirms", async () => {
      const user = userEvent.setup();
      renderWithSelection();
      await user.click(screen.getByTestId("confirm-delete"));
      expect(mockDeleteFiles).toHaveBeenCalledWith(
        { ids: ["file-a", "file-b"] },
        expect.objectContaining({
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        }),
      );
    });

    it("shows success and resets the selection when deletion succeeds", async () => {
      const user = userEvent.setup();
      const setSelectedFiles = jest.fn();
      const setQuantitySelected = jest.fn();
      renderWithSelection({ setSelectedFiles, setQuantitySelected });
      await user.click(screen.getByTestId("confirm-delete"));
      setSelectedFiles.mockClear();
      setQuantitySelected.mockClear();
      const [, options] = mockDeleteFiles.mock.calls[0];
      act(() => {
        options.onSuccess({ message: "Files deleted" });
      });
      expect(mockSetSuccessData).toHaveBeenCalledWith({
        title: "Files deleted",
      });
      expect(setQuantitySelected).toHaveBeenCalledWith(0);
      expect(setSelectedFiles).toHaveBeenCalledWith([]);
    });

    it("surfaces an error alert when deletion fails", async () => {
      const user = userEvent.setup();
      renderWithSelection();
      await user.click(screen.getByTestId("confirm-delete"));
      const [, options] = mockDeleteFiles.mock.calls[0];
      act(() => {
        options.onError(new Error("boom"));
      });
      expect(mockSetErrorData).toHaveBeenCalledWith(
        expect.objectContaining({ list: ["boom"] }),
      );
    });
  });
});
