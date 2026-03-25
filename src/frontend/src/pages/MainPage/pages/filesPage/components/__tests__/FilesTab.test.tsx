import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";

const mockUploadFile = jest.fn();
jest.mock("@/hooks/files/use-upload-file", () => ({
  __esModule: true,
  default: () => mockUploadFile,
}));

jest.mock("@/controllers/API/queries/file-management", () => ({
  useGetFilesV2: () => ({
    data: [
      {
        id: "file-1",
        name: "test",
        path: "test.txt",
        size: 1024,
        updated_at: "2024-01-01T00:00:00",
      },
    ],
  }),
}));

jest.mock("@/controllers/API/queries/file-management/use-delete-files", () => ({
  useDeleteFilesV2: () => ({ mutate: jest.fn(), isPending: false }),
}));

jest.mock(
  "@/controllers/API/queries/file-management/use-put-rename-file",
  () => ({
    usePostRenameFileV2: () => ({ mutate: jest.fn() }),
  }),
);

jest.mock("@/customization/hooks/use-custom-post-upload-file", () => ({
  customPostUploadFileV2: () => ({ mutate: jest.fn() }),
}));

const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({
      setErrorData: mockSetErrorData,
      setSuccessData: mockSetSuccessData,
    }),
}));

jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => ({
    __esModule: true,
    default: ({ rowData }: any) => (
      <div data-testid="mock-table">
        {rowData?.map((row: any) => (
          <div key={row.id}>{row.name}</div>
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

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: any) => <>{children}</>,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, ...props }: any) => (
    <button onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/input", () => ({
  Input: (props: any) => <input {...props} />,
}));

jest.mock("@/components/ui/loading", () => ({
  __esModule: true,
  default: () => <div data-testid="loading" />,
}));

jest.mock("@/components/core/cardsWrapComponent", () => ({
  __esModule: true,
  default: ({ children }: any) => <div>{children}</div>,
}));

jest.mock("@/modals/deleteConfirmationModal", () => ({
  __esModule: true,
  default: ({ children }: any) => <>{children}</>,
}));

jest.mock(
  "@/modals/fileManagerModal/components/filesContextMenuComponent",
  () => ({
    __esModule: true,
    default: ({ children }: any) => <>{children}</>,
  }),
);

jest.mock("../dragWrapComponent", () => ({
  __esModule: true,
  default: ({ children }: any) => <div>{children}</div>,
}));

import FilesTab from "../FilesTab";

const createWrapper = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
};

const defaultProps = {
  quickFilterText: "",
  setQuickFilterText: jest.fn(),
  selectedFiles: [],
  setSelectedFiles: jest.fn(),
  quantitySelected: 0,
  setQuantitySelected: jest.fn(),
  isShiftPressed: false,
};

beforeEach(() => {
  jest.clearAllMocks();
});

describe("FilesTab upload success notification", () => {
  // Ensure no success toast is shown when user cancels file picker (empty array returned).
  it("does NOT show success toast when user cancels file picker (empty array returned)", async () => {
    mockUploadFile.mockResolvedValue([]);

    render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });

    const uploadBtn = screen.getByTestId("upload-file-btn");
    await userEvent.click(uploadBtn);

    await waitFor(() => {
      expect(mockUploadFile).toHaveBeenCalled();
    });

    expect(mockSetSuccessData).not.toHaveBeenCalled();
  });

  // Ensure success toast shows "File uploaded successfully" (singular) when one file is uploaded.
  it("shows 'File uploaded successfully' when one file is uploaded", async () => {
    mockUploadFile.mockResolvedValue(["path/to/file.txt"]);

    render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });

    const uploadBtn = screen.getByTestId("upload-file-btn");
    await userEvent.click(uploadBtn);

    await waitFor(() => {
      expect(mockSetSuccessData).toHaveBeenCalledWith({
        title: "File uploaded successfully",
      });
    });
  });

  // Ensure success toast shows "Files uploaded successfully" (plural) when multiple files are uploaded.
  it("shows 'Files uploaded successfully' when multiple files are uploaded", async () => {
    mockUploadFile.mockResolvedValue([
      "path/to/file1.txt",
      "path/to/file2.txt",
    ]);

    render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });

    const uploadBtn = screen.getByTestId("upload-file-btn");
    await userEvent.click(uploadBtn);

    await waitFor(() => {
      expect(mockSetSuccessData).toHaveBeenCalledWith({
        title: "Files uploaded successfully",
      });
    });
  });

  // Ensure error toast is shown and no success toast appears when upload fails.
  it("shows error toast when upload throws", async () => {
    mockUploadFile.mockRejectedValue(new Error("Network error"));

    render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });

    const uploadBtn = screen.getByTestId("upload-file-btn");
    await userEvent.click(uploadBtn);

    await waitFor(() => {
      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "Error uploading file",
        list: ["Network error"],
      });
    });

    expect(mockSetSuccessData).not.toHaveBeenCalled();
  });

  // Ensure fallback error message is shown when error has no message property.
  it("shows fallback error message when error has no message property", async () => {
    mockUploadFile.mockRejectedValue({});

    render(<FilesTab {...defaultProps} />, { wrapper: createWrapper() });

    const uploadBtn = screen.getByTestId("upload-file-btn");
    await userEvent.click(uploadBtn);

    await waitFor(() => {
      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "Error uploading file",
        list: ["An error occurred while uploading the file"],
      });
    });

    expect(mockSetSuccessData).not.toHaveBeenCalled();
  });
});
