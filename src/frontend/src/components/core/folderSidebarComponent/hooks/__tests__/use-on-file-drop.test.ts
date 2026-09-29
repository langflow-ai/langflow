import { renderHook } from "@testing-library/react";
import useFileDrop from "../use-on-file-drop";

const mockSaveFlow = jest.fn().mockResolvedValue(undefined);
const mockSetFolderDragging = jest.fn();
const mockSetFolderIdDragging = jest.fn();
const mockUploadFlowToFolder = jest.fn();
const mockSetErrorData = jest.fn();

/** The slice of store state these tests stand up; the hook reads a few keys of it. */
type MockState = Record<string, unknown>;

let flowsManagerState: MockState;
let folderState: MockState;

jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => mockSaveFlow,
}));

jest.mock(
  "@/controllers/API/queries/folders/use-post-upload-to-folder",
  () => ({
    usePostUploadFlowToFolder: () => ({ mutate: mockUploadFlowToFolder }),
  }),
);

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
    const { result } = renderHook(() => useFileDrop("project-B"));

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
});
