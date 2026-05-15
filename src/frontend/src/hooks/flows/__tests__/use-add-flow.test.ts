import { renderHook } from "@testing-library/react";
import type { FlowType } from "@/types/flow";
import useAddFlow from "../use-add-flow";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockSetErrorData = jest.fn();
const mockSetNoticeData = jest.fn();
const mockSetFlows = jest.fn();
const mockSetMyCollectionId = jest.fn();
const mockDeleteFlow = jest.fn();
const mockPostAddFlow = jest.fn();
const mockPostAddFolder = jest.fn();

jest.mock("react-router-dom", () => ({
  useParams: () => ({ folderId: "folder-1" }),
}));

jest.mock("@/controllers/API/queries/flows/use-post-add-flow", () => ({
  usePostAddFlow: () => ({ mutate: mockPostAddFlow }),
}));

jest.mock("@/controllers/API/queries/folders", () => ({
  usePostFolders: () => ({ mutateAsync: mockPostAddFolder }),
}));

type Selector<T> = (state: T) => unknown;

type AlertState = { setErrorData: jest.Mock; setNoticeData: jest.Mock };
type FlowsManagerState = { flows: never[]; setFlows: jest.Mock };
type FolderState = {
  myCollectionId: string;
  folders: { id: string }[];
  setMyCollectionId: jest.Mock;
};
type AuthState = { userData: { optins: { dialog_dismissed: boolean } } };
type UtilityState = { hideGettingStartedProgress: boolean };
type GlobalVariablesState = {
  unavailableFields: never[];
  globalVariablesEntries: never[];
};

jest.mock("@/stores/alertStore", () => {
  const store = Object.assign(
    (selector: Selector<AlertState>) =>
      selector({
        setErrorData: mockSetErrorData,
        setNoticeData: mockSetNoticeData,
      }),
    {
      getState: () => ({
        setErrorData: mockSetErrorData,
        setNoticeData: mockSetNoticeData,
      }),
    },
  );
  return { __esModule: true, default: store };
});

jest.mock("@/stores/flowsManagerStore", () => {
  const store = Object.assign(
    (selector: Selector<FlowsManagerState>) =>
      selector({ flows: [], setFlows: mockSetFlows }),
    { getState: () => ({ flows: [], setFlows: mockSetFlows }) },
  );
  return { __esModule: true, default: store };
});

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: (selector: Selector<FolderState>) =>
    selector({
      myCollectionId: "folder-1",
      folders: [{ id: "folder-1" }],
      setMyCollectionId: mockSetMyCollectionId,
    }),
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: Selector<AuthState>) =>
    selector({ userData: { optins: { dialog_dismissed: true } } }),
}));

jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (selector: Selector<UtilityState>) =>
    selector({ hideGettingStartedProgress: true }),
}));

jest.mock("@/stores/globalVariablesStore/globalVariables", () => ({
  useGlobalVariablesStore: (selector: Selector<GlobalVariablesState>) =>
    selector({ unavailableFields: [], globalVariablesEntries: [] }),
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: { setState: jest.fn() },
}));

jest.mock("@/hooks/flows/use-delete-flow", () => ({
  __esModule: true,
  default: () => ({ deleteFlow: mockDeleteFlow }),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  processDataFromFlow: jest.fn((flow) =>
    Promise.resolve(
      flow?.data ?? { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
    ),
  ),
  createNewFlow: jest.fn((_data, folderId, flow) => ({
    ...(flow ?? {}),
    id: "new-flow-id",
    name: flow?.name ?? "New Flow",
    folder_id: folderId,
    data: flow?.data ?? {
      nodes: [],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    },
  })),
  addVersionToDuplicates: jest.fn((flow) => flow.name),
  updateGroupRecursion: jest.fn(),
  processFlows: jest.fn((flows) => ({ data: {}, flows })),
  extractFieldsFromComponenents: jest.fn(() => ({})),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const FLOW_STUB: FlowType = {
  id: "flow-1",
  name: "My Flow",
  description: "",
  data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
  folder_id: "folder-1",
};

/** Make postAddFlow call onSuccess with the given flow. */
function resolveAddFlow(flow = FLOW_STUB) {
  mockPostAddFlow.mockImplementation((_payload, opts) => opts.onSuccess(flow));
}

/** Make postAddFlow call onError with the given error object. */
function rejectAddFlow(error: unknown) {
  mockPostAddFlow.mockImplementation((_payload, opts) => opts.onError(error));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useAddFlow — onError display", () => {
  beforeEach(() => jest.clearAllMocks());

  it("shows the plain string detail from a backend 422 as a readable message", async () => {
    rejectAddFlow({
      response: { data: { detail: "Endpoint name cannot contain dots" } },
    });

    const { result } = renderHook(() => useAddFlow());
    await expect(result.current({ flow: FLOW_STUB })).rejects.toBeDefined();

    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Flow creation error",
      list: ["Endpoint name cannot contain dots"],
    });
  });

  it("extracts msg from a Pydantic ValidationError detail array instead of showing [object Object]", async () => {
    rejectAddFlow({
      response: {
        data: {
          detail: [
            {
              loc: ["body", "endpoint_name"],
              msg: "Endpoint name cannot contain dots",
              type: "value_error",
            },
          ],
        },
      },
    });

    const { result } = renderHook(() => useAddFlow());
    await expect(result.current({ flow: FLOW_STUB })).rejects.toBeDefined();

    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Flow creation error",
      list: ["Endpoint name cannot contain dots"],
    });
  });

  it("shows all messages when the detail array has multiple validation errors", async () => {
    rejectAddFlow({
      response: {
        data: {
          detail: [
            {
              loc: ["body", "endpoint_name"],
              msg: "Endpoint cannot contain dots",
              type: "value_error",
            },
            {
              loc: ["body", "name"],
              msg: "Name is required",
              type: "value_error",
            },
          ],
        },
      },
    });

    const { result } = renderHook(() => useAddFlow());
    await expect(result.current({ flow: FLOW_STUB })).rejects.toBeDefined();

    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Flow creation error",
      list: ["Endpoint cannot contain dots", "Name is required"],
    });
  });

  it("falls back to error.message when there is no response detail", async () => {
    rejectAddFlow(new Error("Network Error"));

    const { result } = renderHook(() => useAddFlow());
    await expect(result.current({ flow: FLOW_STUB })).rejects.toBeDefined();

    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Flow creation error",
      list: ["Network Error"],
    });
  });

  it("shows a generic fallback for a completely unknown error shape", async () => {
    rejectAddFlow({ weird: "shape" });

    const { result } = renderHook(() => useAddFlow());
    await expect(result.current({ flow: FLOW_STUB })).rejects.toBeDefined();

    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Flow creation error",
      list: ["An unknown error occurred"],
    });
  });
});

describe("useAddFlow — success path", () => {
  beforeEach(() => jest.clearAllMocks());

  it("resolves with the created flow id on success", async () => {
    resolveAddFlow({ ...FLOW_STUB, id: "created-id" });

    const { result } = renderHook(() => useAddFlow());
    await expect(result.current({ flow: FLOW_STUB })).resolves.toBe(
      "created-id",
    );

    expect(mockSetErrorData).not.toHaveBeenCalled();
  });

  it("calls setFlows with the new flow prepended", async () => {
    resolveAddFlow(FLOW_STUB);

    const { result } = renderHook(() => useAddFlow());
    await result.current({ flow: FLOW_STUB });

    expect(mockSetFlows).toHaveBeenCalledTimes(1);
  });
});
