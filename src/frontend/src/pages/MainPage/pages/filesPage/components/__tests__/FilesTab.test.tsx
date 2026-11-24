import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ColDef, NewValueParams } from "ag-grid-community";
import React from "react";
import type { FileType } from "@/types/file_management";

// ── Heavy / external dependency mocks ────────────────────────────────────────

interface MockTableProps {
  columnDefs?: ColDef<FileType>[];
  rowData?: FileType[];
  quickFilterText?: string;
  editable?: Array<{
    onUpdate: (params: NewValueParams<FileType, string>) => void;
  }>;
  onSelectionChanged?: (event: {
    api: { getSelectedRows: () => FileType[] };
  }) => void;
}

let mockLatestTableProps: MockTableProps = {};
const mockStartEditingCell = jest.fn();
let mockHandleRename: ((id: string, name: string) => void) | undefined;
jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => {
    const ReactActual = jest.requireActual<typeof React>("react");
    return {
      __esModule: true,
      default: ReactActual.forwardRef((props: MockTableProps, ref) => {
        mockLatestTableProps = props;
        ReactActual.useImperativeHandle(ref, () => ({
          api: { startEditingCell: mockStartEditingCell },
        }));
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

jest.mock("../dragWrapComponent", () => ({
  __esModule: true,
  default: ({
    children,
    onFileDrop,
  }: {
    children: React.ReactNode;
    onFileDrop?: (event: React.DragEvent) => void;
  }) => (
    <div
      aria-label="Drop files"
      data-testid="drag-wrapper"
      onDrop={onFileDrop}
      role="region"
    >
      {children}
    </div>
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
    default: ({
      children,
      handleRename,
    }: {
      children: React.ReactNode;
      handleRename: (id: string, name: string) => void;
    }) => {
      mockHandleRename = handleRename;
      return <>{children}</>;
    },
  }),
);

const mockListFilter = jest.fn();
jest.mock("@/customization/hooks/use-custom-resource-list-filter", () => ({
  useCustomResourceListFilter: (...args: unknown[]) => mockListFilter(...args),
}));
const actualListFilter = jest.requireActual(
  "@/customization/hooks/use-custom-resource-list-filter",
).useCustomResourceListFilter;

let mockUseLabelSeam = false;
jest.mock("@/customization/components/custom-resource-access-label", () => ({
  __esModule: true,
  default: (props: {
    resourceType: string;
    resourceId: string;
    isOwned: boolean;
  }) =>
    mockUseLabelSeam ? (
      <span
        data-testid="access-label"
        data-resource-type={props.resourceType}
        data-resource-id={props.resourceId}
        data-owned={String(props.isOwned)}
      />
    ) : null,
}));

// ── Utilities ────────────────────────────────────────────────────────────────

import useAuthStore from "@/stores/authStore";
import type { Users } from "@/types/api";
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
  mockUseLabelSeam = false;
  mockListFilter.mockImplementation(actualListFilter);
  useAuthStore.setState({ userData: { id: "user-1" } as Users });
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
      expect(
        screen.getByRole("heading", { name: "No files" }),
      ).toBeInTheDocument();
      expect(screen.getByTestId("drag-wrapper")).toBeInTheDocument();
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

    it("shows the API error when a rename is rejected", () => {
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });
      const renameCell = mockLatestTableProps.editable?.[0].onUpdate;
      expect(renameCell).toEqual(expect.any(Function));
      act(() => {
        renameCell?.({ data: older, newValue: "bad name" } as NewValueParams<
          FileType,
          string
        >);
      });
      const options = mockRename.mock.calls[0][1];
      act(() => {
        options.onError({
          response: { data: { detail: "Invalid file name" } },
        });
      });
      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "Error renaming file",
        list: ["Invalid file name"],
      });
    });

    it.each([
      ["files/recording.21.mov", "MOV"],
      ["archives.v1/report.pdf", "PDF"],
      ["files/README", undefined],
    ])("formats the final file extension from %s", (path, expected) => {
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });
      const typeColumn = mockLatestTableProps.columnDefs?.find(
        (column) => column.field === "path",
      );
      expect(typeColumn?.valueFormatter).toEqual(expect.any(Function));

      const formatType = typeColumn?.valueFormatter as (params: {
        value: string;
      }) => string | undefined;
      expect(formatType({ value: path })).toBe(expected);
    });

    // The files API sends its times in UTC with a Z. Older answers came without one.
    it.each([
      ["2026-10-15T22:53:48.793401Z", "2026-10-15T22:53:48.793Z"],
      ["2024-01-02T00:00:00", "2024-01-02T00:00:00Z"],
    ])("shows the modified time %s as the instant %s", (sent, instant) => {
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });
      const modifiedColumn = mockLatestTableProps.columnDefs?.find(
        (column) => column.field === "updated_at",
      );
      const formatModified = modifiedColumn?.valueFormatter as (params: {
        value: string;
        data: FileType;
      }) => string;

      expect(formatModified({ value: sent, data: older })).toBe(
        new Date(instant).toLocaleString(),
      );
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

  describe("Ownership filter seam", () => {
    const ownedOnly = <T,>(
      _type: string,
      items: T[],
      isOwned: (item: T) => boolean,
    ) => ({
      items: items.filter(isOwned),
      tools: <button type="button">Owned</button>,
    });
    const mine = makeFile({ id: "mine", name: "mine", user_id: "user-1" });
    const theirs = makeFile({ id: "theirs", name: "theirs", user_id: "u-2" });
    const legacy = makeFile({ id: "legacy", name: "legacy", user_id: "" });

    const renderWith = (data: FileType[]) => {
      mockGetFiles.mockReturnValue({ data });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });
    };
    const renderNameCell = (file: FileType) => {
      const nameColumn = mockLatestTableProps.columnDefs?.find(
        (column) => column.field === "name",
      );
      const Renderer = nameColumn?.cellRenderer as (props: {
        data: FileType;
        value: string;
      }) => React.ReactElement;
      return render(<Renderer data={file} value={file.name} />);
    };

    it("should_render_every_file_with_no_tools_when_the_seam_is_the_default", () => {
      renderWith([mine, theirs, legacy]);

      expect(screen.getAllByTestId(/^row-/)).toHaveLength(3);
      expect(
        screen.queryByRole("button", { name: "Owned" }),
      ).not.toBeInTheDocument();
    });

    it("should_compute_isOwned_from_user_id_for_owner_non_owner_and_missing", () => {
      renderWith([mine, theirs, legacy]);

      const [type, , isOwned] = mockListFilter.mock.calls.at(-1);
      expect(type).toBe("file");
      expect([mine, theirs, legacy].map(isOwned)).toEqual([true, false, true]);
    });

    it("should_render_only_filtered_files_and_the_tools_next_to_upload", () => {
      mockListFilter.mockImplementation(ownedOnly);
      renderWith([mine, theirs, legacy]);

      expect(
        screen.getAllByTestId(/^row-/).map((row) => row.dataset.testid),
      ).toEqual(expect.arrayContaining(["row-mine", "row-legacy"]));
      expect(screen.queryByTestId("row-theirs")).not.toBeInTheDocument();
      const actions = screen.getByTestId("files-toolbar-actions");
      expect(actions).toContainElement(
        screen.getByRole("button", { name: "Owned" }),
      );
      expect(actions).toContainElement(screen.getByTestId("upload-file-btn"));
      // Without shrink-0 the box shrank and Upload Files spilled past the
      // right edge at 1024px once the switch joined it.
      expect(actions).toHaveClass("shrink-0");
    });

    it("should_reserve_room_for_a_one_line_label_in_the_name_column", () => {
      renderWith([mine]);
      const nameColumn = mockLatestTableProps.columnDefs?.find(
        (column) => column.field === "name",
      );

      expect(nameColumn).toMatchObject({ flex: 2, minWidth: 280 });
    });

    it("should_show_the_existing_empty_state_with_the_tools_when_no_file_is_owned", () => {
      mockListFilter.mockImplementation(ownedOnly);
      renderWith([theirs]);

      expect(
        screen.getByRole("heading", { name: "No files" }),
      ).toBeInTheDocument();
      expect(screen.queryByTestId("mock-table")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Owned" })).toBeInTheDocument();
    });

    it("should_give_the_seam_an_empty_list_when_there_are_no_files", () => {
      mockListFilter.mockImplementation(ownedOnly);
      renderWith([]);

      expect(mockListFilter.mock.calls.at(-1)?.[1]).toEqual([]);
      expect(
        screen.getByRole("heading", { name: "No files" }),
      ).toBeInTheDocument();
    });

    it("should_render_one_row_per_owned_file_when_there_are_many", () => {
      mockListFilter.mockImplementation(ownedOnly);
      renderWith(
        Array.from({ length: 40 }, (_, index) =>
          makeFile({
            id: `f-${index}`,
            name: `f-${index}`,
            user_id: index < 25 ? "user-1" : "u-2",
          }),
        ),
      );

      expect(screen.getAllByTestId(/^row-/)).toHaveLength(25);
    });

    it("should_leave_the_name_cell_unchanged_when_the_label_is_the_default", () => {
      renderWith([theirs]);
      const { container } = renderNameCell(theirs);

      // Icon and name only; the upload-failed slot renders an empty fragment.
      expect(container.firstElementChild?.children).toHaveLength(2);
    });

    it("should_render_the_label_after_the_file_name_with_file_props", () => {
      mockUseLabelSeam = true;
      renderWith([mine, theirs]);
      const { container } = renderNameCell(theirs);

      const label = screen.getByTestId("access-label");
      const nameText = screen.getByText("theirs.pdf");
      expect(nameText.nextElementSibling).toBe(label);
      // Stacked under the name, not beside it, so the name leaves it room.
      const stack = screen.getByTestId("file-name-stack");
      expect(stack).toHaveClass("flex-col", "min-w-0");
      // The 18px name line is what leaves the label room for its descenders.
      expect(nameText).toHaveClass("leading-[18px]");
      expect(stack.children).toHaveLength(2);
      expect(container.firstElementChild).toContainElement(label);
      expect(label).toHaveAttribute("data-resource-type", "file");
      expect(label).toHaveAttribute("data-resource-id", "theirs");
      expect(label).toHaveAttribute("data-owned", "false");
    });

    it("should_mark_a_file_without_user_id_as_owned_in_its_label", () => {
      mockUseLabelSeam = true;
      renderWith([legacy]);
      renderNameCell(legacy);

      expect(screen.getByTestId("access-label")).toHaveAttribute(
        "data-owned",
        "true",
      );
    });
  });

  describe("Uploading", () => {
    it("should_confirm_a_multi_file_upload_when_the_upload_button_is_used", async () => {
      mockUploadFile.mockResolvedValueOnce(["a", "b"]);
      mockGetFiles.mockReturnValue({ data: [makeFile()] });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });

      await userEvent.click(screen.getByTestId("upload-file-btn"));

      expect(mockUploadFile).toHaveBeenCalledWith({ files: undefined });
      expect(mockSetSuccessData).toHaveBeenCalledWith({
        title: "Files uploaded successfully",
      });
    });

    it("should_confirm_a_single_upload_with_the_singular_message", async () => {
      mockUploadFile.mockResolvedValueOnce(["a"]);
      mockGetFiles.mockReturnValue({ data: [makeFile()] });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });

      await userEvent.click(screen.getByTestId("upload-file-btn"));

      expect(mockSetSuccessData).toHaveBeenCalledWith({
        title: "File uploaded successfully",
      });
    });

    it("should_say_nothing_when_the_picker_is_closed_without_files", async () => {
      mockUploadFile.mockResolvedValueOnce([]);
      mockGetFiles.mockReturnValue({ data: [makeFile()] });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });

      await userEvent.click(screen.getByTestId("upload-file-btn"));

      expect(mockSetSuccessData).not.toHaveBeenCalled();
      expect(mockSetErrorData).not.toHaveBeenCalled();
    });

    it("should_show_the_upload_error_message_when_the_upload_throws", async () => {
      mockUploadFile.mockRejectedValueOnce(new Error("File too large"));
      mockGetFiles.mockReturnValue({ data: [makeFile()] });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });

      await userEvent.click(screen.getByTestId("upload-file-btn"));

      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "Error uploading file",
        list: ["File too large"],
      });
    });

    it("should_fall_back_to_a_generic_detail_when_the_upload_rejects_a_non_error", async () => {
      mockUploadFile.mockRejectedValueOnce("nope");
      mockGetFiles.mockReturnValue({ data: [] });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });

      await userEvent.click(screen.getByTestId("upload-file-btn"));

      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "Error uploading file",
        list: ["An error occurred while uploading the file"],
      });
    });

    it("should_upload_the_dropped_files_when_files_are_dropped_on_the_table", async () => {
      mockUploadFile.mockResolvedValueOnce(["a"]);
      mockGetFiles.mockReturnValue({ data: [makeFile()] });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });
      const dropped = new File(["x"], "dropped.txt");

      await act(async () => {
        fireEvent.drop(screen.getByTestId("drag-wrapper"), {
          dataTransfer: { files: [dropped] },
        });
      });

      expect(mockUploadFile).toHaveBeenCalledWith({ files: [dropped] });
    });

    it("should_not_upload_when_a_drop_carries_no_files", async () => {
      mockGetFiles.mockReturnValue({ data: [makeFile()] });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });

      await act(async () => {
        fireEvent.drop(screen.getByTestId("drag-wrapper"), {
          dataTransfer: { files: [] },
        });
      });

      expect(mockUploadFile).not.toHaveBeenCalled();
    });

    it("should_retry_a_failed_upload_with_the_original_file_from_its_row", () => {
      const original = new File(["x"], "report.pdf");
      const failed = makeFile({ progress: -1, file: original });
      mockGetFiles.mockReturnValue({ data: [failed] });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });
      const nameColumn = mockLatestTableProps.columnDefs?.find(
        (column) => column.field === "name",
      );
      const Renderer = nameColumn?.cellRenderer as (props: {
        data: FileType;
        value: string;
      }) => React.ReactElement;
      render(<Renderer data={failed} value={failed.name} />);

      fireEvent.click(screen.getByRole("button", { name: "try again?" }));

      expect(mockUploadDirect).toHaveBeenCalledWith({ file: original });
    });

    it("should_blank_the_modified_date_while_a_file_is_still_uploading", () => {
      mockGetFiles.mockReturnValue({ data: [makeFile()] });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });
      const modified = mockLatestTableProps.columnDefs?.find(
        (column) => column.field === "updated_at",
      );
      const format = modified?.valueFormatter as (params: {
        data: Partial<FileType>;
        value: string;
      }) => string;

      expect(
        format({ data: { progress: 0.5 }, value: "2024-01-02T00:00:00" }),
      ).toBe("");
      expect(
        format({ data: {}, value: "2024-01-02T00:00:00" }).length,
      ).toBeGreaterThan(0);
    });
  });

  describe("Keyboard access to row actions", () => {
    const keyDown = (colId: string, key: string, target: HTMLElement) => {
      const event = new KeyboardEvent("keydown", { key, cancelable: true });
      Object.defineProperty(event, "target", { value: target });
      const props = mockLatestTableProps as MockTableProps & {
        onCellKeyDown?: (event: unknown) => void;
      };
      act(() => {
        props.onCellKeyDown?.({ column: { getColId: () => colId }, event });
      });
      return event;
    };

    const actionsCell = () => {
      const cell = document.createElement("div");
      cell.setAttribute("role", "gridcell");
      const trigger = document.createElement("button");
      const inner = document.createElement("span");
      cell.append(trigger, inner);
      const forwarded = jest.fn();
      trigger.addEventListener("keydown", (event) => forwarded(event.key));
      return { inner, trigger, forwarded };
    };

    beforeEach(() => {
      mockGetFiles.mockReturnValue({ data: [makeFile()] });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });
    });

    it.each(["Enter", " "])(
      "should_forward_%p_to_the_actions_menu_trigger_in_the_actions_cell",
      (key) => {
        const { inner, forwarded } = actionsCell();

        const event = keyDown("actions", key, inner);

        expect(forwarded).toHaveBeenCalledWith(key);
        expect(event.defaultPrevented).toBe(true);
      },
    );

    it("should_ignore_other_keys_other_columns_and_the_trigger_itself", () => {
      const { inner, trigger, forwarded } = actionsCell();

      keyDown("actions", "a", inner);
      keyDown("name", "Enter", inner);
      keyDown("actions", "Enter", trigger);
      keyDown("actions", "Enter", document.createElement("div"));

      expect(forwarded).not.toHaveBeenCalled();
    });
  });

  describe("Rename with the ownership filter", () => {
    it("should_start_editing_the_row_index_of_the_file_in_the_filtered_list", () => {
      jest.spyOn(window, "requestAnimationFrame").mockImplementation(() => 0);
      mockListFilter.mockImplementation(<T,>(_t: string, items: T[]) => ({
        items: items.slice(1),
        tools: null,
      }));
      const newest = makeFile({
        id: "newest",
        name: "newest",
        updated_at: "2024-09-01T00:00:00",
      });
      const middle = makeFile({
        id: "middle",
        name: "middle",
        updated_at: "2024-06-01T00:00:00",
      });
      const oldest = makeFile({
        id: "oldest",
        name: "oldest",
        updated_at: "2024-01-01T00:00:00",
      });
      mockGetFiles.mockReturnValue({ data: [oldest, middle, newest] });
      render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });

      // Rendered columns mount the context menu, which captures the handler.
      const actions = mockLatestTableProps.columnDefs?.find(
        (column) => column.colId === "actions",
      );
      const Renderer = actions?.cellRenderer as (props: {
        data: FileType;
      }) => React.ReactElement;
      render(<Renderer data={oldest} />);
      act(() => mockHandleRename?.("oldest", "oldest"));

      // Visible rows are [middle, oldest]; "newest" is filtered out.
      expect(mockStartEditingCell).toHaveBeenCalledWith({
        rowIndex: 1,
        colKey: "name",
      });
      jest.restoreAllMocks();
    });
  });
});
