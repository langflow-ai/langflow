import { render, screen } from "@testing-library/react";
import { useState } from "react";

import InputFileComponent from "../index";

/**
 * The node's attachment must not be destroyed by a file-list response that
 * simply does not mention the attached file. A list read can lag the upload
 * that created the file (the upload writes the entry into the cache optimistically,
 * and the refetch it triggers can be served by a read that has not caught up),
 * or an older in-flight response can resolve last. Reconciling that absence to
 * "" clears value/file_path, is persisted with the flow, and is terminal: with
 * nothing selected, no later - correct - response can restore the attachment.
 */

const UPLOADED = { name: "fresh", path: "user/fresh.txt" };

let filesData: { name: string; path: string }[] = [];
/** Bumped whenever a settled list read lands, like react-query's own value. */
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
  default: ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

const onNewValue = jest.fn();

/** Mirrors the node: handleOnNewValue is what feeds value/file_path back in. */
function Harness({
  state,
  setState,
}: {
  state: { value: string; file_path: string };
  setState: (next: { value: string; file_path: string }) => void;
}) {
  return (
    <InputFileComponent
      id="input-file-stale-list"
      value={state.value}
      file_path={state.file_path}
      handleOnNewValue={(changes) => {
        onNewValue(changes);
        setState({
          value: (changes.value ?? "") as string,
          file_path: (changes.file_path ?? "") as string,
        });
      }}
      disabled={false}
      fileTypes={["txt"]}
      isList={false}
      tempFile={false}
      editNode={false}
    />
  );
}

/** Holds the node state across rerenders so a wipe is observable. */
let nodeState = { value: UPLOADED.name, file_path: UPLOADED.path };

function StatefulHarness() {
  const [state, setState] = useState(nodeState);
  nodeState = state;
  return (
    <Harness
      state={state}
      setState={(next) => {
        nodeState = next;
        setState(next);
      }}
    />
  );
}

const selection = () => screen.queryByTestId("rendered-files")?.textContent;

describe("InputFileComponent stale file-list responses", () => {
  beforeEach(() => {
    filesData = [UPLOADED];
    filesUpdatedAt = 1;
    nodeState = { value: UPLOADED.name, file_path: UPLOADED.path };
    jest.clearAllMocks();
  });

  it("should_keep_the_attachment_when_a_list_response_omits_the_attached_file", () => {
    const { rerender } = render(<StatefulHarness />);
    expect(selection()).toBe(UPLOADED.path);

    // A read that has not caught up with the upload.
    filesData = [];
    rerender(<StatefulHarness />);

    expect(nodeState.file_path).toBe(UPLOADED.path);
    expect(nodeState.value).toBe(UPLOADED.name);
    expect(refetchFiles).toHaveBeenCalled();
  });

  it("should_restore_the_chip_once_a_complete_list_response_arrives", () => {
    const { rerender } = render(<StatefulHarness />);

    filesData = [];
    rerender(<StatefulHarness />);

    // The forced re-read finds it, as it is issued after the upload landed.
    filesData = [UPLOADED];
    rerender(<StatefulHarness />);

    expect(selection()).toBe(UPLOADED.path);
    expect(nodeState.file_path).toBe(UPLOADED.path);
  });

  it("should_drop_the_file_once_a_re_read_confirms_it_is_gone", () => {
    const { rerender } = render(<StatefulHarness />);

    // First absence only forces the re-read.
    filesData = [];
    rerender(<StatefulHarness />);
    expect(nodeState.file_path).toBe(UPLOADED.path);

    // The re-read still does not have it: a real delete.
    rerender(<StatefulHarness />);

    expect(nodeState.file_path).toBe("");
    expect(nodeState.value).toBe("");
  });

  it("should_keep_the_file_selectable_while_the_list_cannot_render_the_chip", () => {
    const { rerender } = render(<StatefulHarness />);
    expect(
      screen.queryByTestId("input-file-component"),
    ).not.toBeInTheDocument();

    filesData = [];
    rerender(<StatefulHarness />);

    expect(selection()).toBe("");
    expect(screen.getByTestId("input-file-component")).toBeInTheDocument();
  });

  it("should_still_follow_a_rename_the_list_does_report", () => {
    const { rerender } = render(<StatefulHarness />);

    filesData = [{ name: "renamed", path: UPLOADED.path }];
    rerender(<StatefulHarness />);

    expect(nodeState.value).toBe("renamed");
    expect(nodeState.file_path).toBe(UPLOADED.path);
  });
});
