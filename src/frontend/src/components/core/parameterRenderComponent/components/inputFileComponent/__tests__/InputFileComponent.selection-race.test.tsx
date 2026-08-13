import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";

import InputFileComponent from "../index";

/**
 * A file uploaded from the file manager could disappear from the node right
 * after "Select files": the reconciliation effect re-derives value/file_path
 * from the files cache, and while the manager is open its `file_path` snapshot
 * is the pre-submit one. That write lands after the submit and reverts it.
 */

const TXT = { name: "kept", path: "user/kept.txt" };
const JSON_FILE = { name: "removed", path: "user/removed.json" };
const UPLOADED = { name: "fresh", path: "user/fresh.txt" };

let filesData: { name: string; path: string }[] = [];
let filesUpdatedAt = 1;

const refetchFiles = jest.fn(() => {
  filesUpdatedAt += 1;
});

jest.mock("@/controllers/API/queries/file-management", () => ({
  __esModule: true,
  useGetFilesV2: () => ({
    data: filesData,
    refetch: refetchFiles,
    isFetching: false,
    dataUpdatedAt: filesUpdatedAt,
  }),
}));

jest.mock("@/controllers/API/queries/files/use-post-upload-file", () => ({
  __esModule: true,
  usePostUploadFile: () => ({ mutateAsync: jest.fn(), isPending: false }),
}));

jest.mock("@/customization/feature-flags", () => ({
  __esModule: true,
  ENABLE_FILE_MANAGEMENT: true,
}));

jest.mock(
  "@/modals/fileManagerModal/components/filesRendererComponent",
  () => ({
    __esModule: true,
    default: ({ files }: { files: { path: string }[] }) => (
      <div data-testid="rendered-files">
        {files.map((file) => file.path).join(",")}
      </div>
    ),
  }),
);

jest.mock("@/modals/fileManagerModal", () => ({
  __esModule: true,
  default: ({
    onOpenChange,
    handleSubmit,
  }: {
    onOpenChange?: (open: boolean) => void;
    handleSubmit: (files: string[]) => void;
  }) => (
    <div>
      <button type="button" onClick={() => onOpenChange?.(true)}>
        open-manager
      </button>
      <button
        type="button"
        onClick={() => {
          handleSubmit([TXT.path, JSON_FILE.path, UPLOADED.path]);
          onOpenChange?.(false);
        }}
      >
        submit-manager
      </button>
    </div>
  ),
}));

const onNewValue = jest.fn();

/** Mirrors the node: handleOnNewValue is what feeds value/file_path back in. */
function Harness() {
  const [state, setState] = useState<{ value: string[]; file_path: string[] }>({
    value: [TXT.name, JSON_FILE.name],
    file_path: [TXT.path, JSON_FILE.path],
  });

  return (
    <InputFileComponent
      id="input-file-selection-race"
      value={state.value as never}
      file_path={state.file_path as never}
      handleOnNewValue={(changes) => {
        onNewValue(changes);
        setState({
          value: (changes.value ?? []) as string[],
          file_path: (changes.file_path ?? []) as string[],
        });
      }}
      disabled={false}
      fileTypes={["txt", "json"]}
      isList
      tempFile={false}
      editNode={false}
    />
  );
}

const selection = () => screen.getByTestId("rendered-files").textContent;

describe("InputFileComponent selection reconciliation", () => {
  beforeEach(() => {
    filesData = [TXT, JSON_FILE];
    jest.clearAllMocks();
  });

  it("should_drop_a_file_the_server_no_longer_has_once_a_re_read_confirms_it", () => {
    const { rerender } = render(<Harness />);
    expect(selection()).toBe(`${TXT.path},${JSON_FILE.path}`);

    filesData = [TXT];
    rerender(<Harness key="reconcile" />);

    // The first absence only forces a fresh read - it is not yet evidence.
    expect(onNewValue).not.toHaveBeenCalled();
    expect(refetchFiles).toHaveBeenCalled();

    // The re-read still omits it: a real delete, so the selection is dropped.
    rerender(<Harness key="reconcile" />);

    expect(onNewValue).toHaveBeenCalledWith(
      expect.objectContaining({ file_path: [TXT.path] }),
    );
    expect(selection()).toBe(TXT.path);
  });

  it("should_not_rewrite_the_selection_while_the_file_manager_is_open", () => {
    const { rerender } = render(<Harness />);
    fireEvent.click(screen.getByText("open-manager"));
    onNewValue.mockClear();

    filesData = [TXT, UPLOADED];
    rerender(<Harness />);

    expect(onNewValue).not.toHaveBeenCalled();
    expect(selection()).toBe(TXT.path);
  });

  it("should_keep_the_uploaded_file_submitted_from_the_manager", () => {
    render(<Harness />);
    fireEvent.click(screen.getByText("open-manager"));

    filesData = [TXT, UPLOADED];
    fireEvent.click(screen.getByText("submit-manager"));

    expect(selection()).toBe(`${TXT.path},${UPLOADED.path}`);
  });
});
