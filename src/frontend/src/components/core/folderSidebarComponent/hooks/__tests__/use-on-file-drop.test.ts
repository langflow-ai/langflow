import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import useFileDrop from "../use-on-file-drop";

const mockSaveFlow = jest.fn().mockResolvedValue(undefined);
const mockSetFolderDragging = jest.fn();
const mockSetFolderIdDragging = jest.fn();
const mockApiPost = jest.fn();
const mockSetErrorData = jest.fn();

/** The slice of store state these tests stand up; the hook reads a few keys of it. */
type MockState = Record<string, unknown>;

let flowsManagerState: MockState;
let folderState: MockState;

jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => mockSaveFlow,
}));

// Only the request is stubbed: the upload mutation itself is real, so overlapping
// drops behave as they do in the app.
jest.mock("@/controllers/API/api", () => ({
  api: { post: (...args: unknown[]) => mockApiPost(...args) },
}));

jest.mock("react-i18next", () => ({
  __esModule: true,
  useTranslation: () => ({ t: (key: string) => key }),
  initReactI18next: {
    type: "3rdParty",
    init: () => {},
  },
}));

jest.mock("../../../../../stores/alertStore", () => ({
  __esModule: true,
  default: <T>(selector: (state: MockState) => T) =>
    selector({
      setErrorData: mockSetErrorData,
    }),
}));

jest.mock("../../../../../stores/flowsManagerStore", () => {
  const useFlowsManagerStore = <T>(selector?: (state: MockState) => T) =>
    selector ? selector(flowsManagerState) : flowsManagerState;
  useFlowsManagerStore.getState = () => flowsManagerState;
  return {
    __esModule: true,
    default: useFlowsManagerStore,
  };
});

jest.mock("../../../../../stores/foldersStore", () => {
  const useFolderStore = <T>(selector?: (state: MockState) => T) =>
    selector ? selector(folderState) : folderState;
  useFolderStore.getState = () => folderState;
  return {
    useFolderStore,
  };
});

const renderFileDrop = () => {
  const client = new QueryClient();
  return renderHook(() => useFileDrop("project-B"), {
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children),
  });
};

/** A flow file dropped on a project. */
const fileDrop = (name: string) =>
  ({
    dataTransfer: {
      getData: jest.fn(() => ""),
      types: ["Files"],
      files: [new File(["{}"], name, { type: "application/json" })],
    },
    preventDefault: jest.fn(),
  }) as unknown as React.DragEvent<HTMLDivElement>;

/** The 422 an upload gets when an MCP server config the flow carries fails validation. */
const validationRejection = {
  response: {
    status: 422,
    data: {
      detail: [
        {
          type: "value_error",
          loc: [],
          msg: "Value error, Environment variable 'NODE_OPTIONS' is not allowed for security reasons",
        },
      ],
    },
  },
};

describe("useFileDrop.onDrop (drag-and-drop flow between projects)", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    const flowInProjectA = {
      id: "flow-1",
      name: "Flow One",
      data: null,
      folder_id: "project-A",
      is_component: false,
    };

    flowsManagerState = {
      flows: [flowInProjectA],
    };

    folderState = {
      setFolderDragging: mockSetFolderDragging,
      setFolderIdDragging: mockSetFolderIdDragging,
      myCollectionId: "my-collection",
    };
  });

  it("should_call_saveFlow_with_new_folder_id_when_flow_is_dropped_into_empty_project", () => {
    const { result } = renderFileDrop();

    const event = {
      dataTransfer: {
        getData: jest.fn((type: string) =>
          type === "flow"
            ? JSON.stringify({
                id: "flow-1",
                name: "Flow One",
                folder_id: "project-A",
              })
            : "",
        ),
        types: ["flow"],
      },
      preventDefault: jest.fn(),
    } as unknown as React.DragEvent<HTMLDivElement>;

    result.current.onDrop(event, "project-B");

    expect(mockSaveFlow).toHaveBeenCalledTimes(1);
    const savedFlow = mockSaveFlow.mock.calls[0][0];
    expect(savedFlow).toEqual(
      expect.objectContaining({
        id: "flow-1",
        folder_id: "project-B",
      }),
    );
    expect(mockSetFolderDragging).toHaveBeenCalledWith(false);
    expect(mockSetFolderIdDragging).toHaveBeenCalledWith("");
  });

  it("should_report_validation_messages_when_a_dropped_flow_file_fails_to_upload", async () => {
    mockApiPost.mockRejectedValueOnce(validationRejection);
    const { result } = renderFileDrop();

    act(() => result.current.onDrop(fileDrop("flow.json"), "project-B"));

    await waitFor(() =>
      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "errors.upload",
        list: [
          "Value error, Environment variable 'NODE_OPTIONS' is not allowed for security reasons",
        ],
      }),
    );
    expect(mockApiPost).toHaveBeenCalledWith(
      expect.stringContaining("folder_id=project-B"),
      expect.any(FormData),
    );
  });

  it("should_report_a_failed_upload_after_a_second_drop_started", async () => {
    let rejectFirst: (reason: unknown) => void = () => {};
    mockApiPost
      .mockImplementationOnce(
        () =>
          new Promise((_resolve, reject) => {
            rejectFirst = reject;
          }),
      )
      .mockImplementationOnce(() => new Promise(() => {}));
    const { result } = renderFileDrop();

    act(() => {
      result.current.onDrop(fileDrop("first.json"), "project-B");
      result.current.onDrop(fileDrop("second.json"), "project-B");
    });
    await waitFor(() => expect(mockApiPost).toHaveBeenCalledTimes(2));
    act(() => rejectFirst(validationRejection));

    await waitFor(() =>
      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "errors.upload",
        list: [
          "Value error, Environment variable 'NODE_OPTIONS' is not allowed for security reasons",
        ],
      }),
    );
  });
});
