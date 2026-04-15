import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DragFilesComponent from "../index";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ), // minimal
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const uploadFilesMock = jest.fn();
const uploadFolderMock = jest.fn();

jest.mock("@/hooks/files/use-upload-file", () => ({
  __esModule: true,
  default: (opts: { webkitdirectory?: boolean }) =>
    opts?.webkitdirectory ? uploadFolderMock : uploadFilesMock,
}));

const createFileUploadMock = jest.fn();

jest.mock("@/helpers/create-file-upload", () => ({
  __esModule: true,
  createFileUpload: (...args: any[]) => createFileUploadMock(...args),
}));

jest.mock("@/stores/utilityStore", () => ({
  __esModule: true,
  useUtilityStore: (selector: (s: { maxFileSizeUpload: number }) => unknown) =>
    selector({ maxFileSizeUpload: 1024 * 1024 }),
}));

const setErrorDataMock = jest.fn();
const setSuccessDataMock = jest.fn();

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: any) => unknown) =>
    selector({
      setErrorData: setErrorDataMock,
      setSuccessData: setSuccessDataMock,
    }),
}));

jest.mock("../helpers", () => {
  const actual = jest.requireActual("../helpers");
  return {
    ...actual,
    getDroppedFilesFromDragEvent: jest.fn(),
  };
});

import { getDroppedFilesFromDragEvent } from "../helpers";

function fileWithRelativePath(name: string, relativePath: string) {
  const f = new File(["x"], name, { type: "text/plain" });
  Object.defineProperty(f, "webkitRelativePath", {
    value: relativePath,
    enumerable: true,
  });
  return f;
}

describe("DragFilesComponent", () => {
  const onUpload = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    uploadFilesMock.mockResolvedValue(["file-id-1"]);
    uploadFolderMock.mockResolvedValue(["file-id-folder-1"]);
    createFileUploadMock.mockResolvedValue([]);
    (getDroppedFilesFromDragEvent as jest.Mock).mockResolvedValue({
      files: [],
      hasDirectories: false,
    });
  });

  it("renders default prompt and toggles drag UI", () => {
    render(
      <DragFilesComponent
        onUpload={onUpload}
        types={["txt"]}
        isList={false}
        allowFolderSelection={false}
      />,
    );

    expect(screen.getByText("Click or drag files here")).toBeInTheDocument();

    const dropZone = screen.getByTestId("drag-files-component");
    fireEvent.dragEnter(dropZone, {
      dataTransfer: { types: ["Files"], files: [] },
    });

    expect(screen.getByText("Drop files here")).toBeInTheDocument();

    fireEvent.dragLeave(dropZone, {
      dataTransfer: { types: ["Files"], files: [] },
    });

    expect(screen.getByText("Click or drag files here")).toBeInTheDocument();
  });

  it("clicking drop zone triggers file upload and success toast", async () => {
    render(
      <DragFilesComponent
        onUpload={onUpload}
        types={["txt"]}
        isList={false}
        allowFolderSelection={false}
      />,
    );

    const dropZone = screen.getByTestId("drag-files-component");
    await userEvent.click(dropZone);

    await waitFor(() => {
      expect(uploadFilesMock).toHaveBeenCalledWith({});
    });

    expect(onUpload).toHaveBeenCalledWith(["file-id-1"]);
    expect(setSuccessDataMock).toHaveBeenCalledWith({
      title: "File uploaded successfully",
    });
  });

  it("dropping a file uses uploadFiles when folder selection is disabled", async () => {
    const dropped = new File(["x"], "a.txt", { type: "text/plain" });

    (getDroppedFilesFromDragEvent as jest.Mock).mockResolvedValue({
      files: [dropped],
      hasDirectories: false,
    });

    render(
      <DragFilesComponent
        onUpload={onUpload}
        types={["txt"]}
        isList={false}
        allowFolderSelection={false}
      />,
    );

    const dropZone = screen.getByTestId("drag-files-component");

    fireEvent.drop(dropZone, {
      dataTransfer: { files: [dropped], types: ["Files"] },
    });

    await waitFor(() => {
      expect(uploadFilesMock).toHaveBeenCalledWith({ files: [dropped] });
    });

    expect(uploadFolderMock).not.toHaveBeenCalled();
    expect(onUpload).toHaveBeenCalledWith(["file-id-1"]);
  });

  it("dropping a folder-like file uses uploadFolder when folder selection is enabled", async () => {
    const dropped = fileWithRelativePath("a.txt", "my-folder/a.txt");

    (getDroppedFilesFromDragEvent as jest.Mock).mockResolvedValue({
      files: [dropped],
      hasDirectories: false,
    });

    render(
      <DragFilesComponent
        onUpload={onUpload}
        types={["txt"]}
        isList={false}
        allowFolderSelection={true}
        existingFiles={[]}
      />,
    );

    const dropZone = screen.getByTestId("drag-files-component");

    fireEvent.drop(dropZone, {
      dataTransfer: { files: [dropped], types: ["Files"] },
    });

    await waitFor(() => {
      expect(uploadFolderMock).toHaveBeenCalled();
    });

    expect(uploadFilesMock).not.toHaveBeenCalledWith(
      expect.objectContaining({ files: [dropped] }),
    );
    expect(onUpload).toHaveBeenCalledWith(["file-id-folder-1"]);
    expect(setSuccessDataMock).toHaveBeenCalledWith({
      title: "File uploaded successfully",
    });
  });

  it("select folder button uses createFileUpload and uploadFolder", async () => {
    const selected = fileWithRelativePath("a.txt", "my-folder/a.txt");
    createFileUploadMock.mockResolvedValue([selected]);

    render(
      <DragFilesComponent
        onUpload={onUpload}
        types={["txt"]}
        isList={false}
        allowFolderSelection={true}
        existingFiles={[]}
      />,
    );

    const btn = screen.getByRole("button", { name: "Select a folder instead" });
    await userEvent.click(btn);

    await waitFor(() => {
      expect(createFileUploadMock).toHaveBeenCalledWith({
        accept: ".txt",
        multiple: true,
        webkitdirectory: true,
      });
    });

    await waitFor(() => {
      expect(uploadFolderMock).toHaveBeenCalled();
    });

    expect(onUpload).toHaveBeenCalledWith(["file-id-folder-1"]);
  });

  it("shows error toast when upload throws", async () => {
    const dropped = new File(["x"], "a.txt", { type: "text/plain" });

    (getDroppedFilesFromDragEvent as jest.Mock).mockResolvedValue({
      files: [dropped],
      hasDirectories: false,
    });

    uploadFilesMock.mockRejectedValueOnce(new Error("nope"));

    render(
      <DragFilesComponent
        onUpload={onUpload}
        types={["txt"]}
        isList={false}
        allowFolderSelection={false}
      />,
    );

    const dropZone = screen.getByTestId("drag-files-component");
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [dropped], types: ["Files"] },
    });

    await waitFor(() => {
      expect(setErrorDataMock).toHaveBeenCalledWith({
        title: "Error uploading file",
        list: ["nope"],
      });
    });

    expect(onUpload).not.toHaveBeenCalled();
  });
});
