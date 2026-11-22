import { act, renderHook, waitFor } from "@testing-library/react";
import useFileDrop from "@/pages/MainPage/hooks/use-on-file-drop";
import type { FlowType } from "@/types/flow";
import useUploadFlow from "../use-upload-flow";

const mockAddFlow = jest.fn();
const mockPostUploadFlows = jest.fn();
const mockPrepareFlows = jest.fn();
const mockPaste = jest.fn();
const mockSetFlows = jest.fn();
const mockSetTypes = jest.fn();
const mockGetObjects = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      setErrorData: mockSetErrorData,
      setSuccessData: mockSetSuccessData,
    }),
}));

jest.mock("../use-add-flow", () => ({
  __esModule: true,
  default: () => mockAddFlow,
}));
jest.mock("../use-prepare-flows", () => ({
  __esModule: true,
  default: () => mockPrepareFlows,
}));
jest.mock("@/controllers/API/queries/flows/use-post-upload-flows", () => ({
  usePostUploadFlows: () => ({ mutateAsync: mockPostUploadFlows }),
}));
jest.mock("@/helpers/get-objects-from-filelist", () => ({
  getObjectsFromFilelist: (...args: unknown[]) => mockGetObjects(...args),
}));
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ paste: mockPaste }),
}));
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: Object.assign(
    (selector: (state: unknown) => unknown) =>
      selector({ flows: [], setFlows: mockSetFlows }),
    { getState: () => ({ flows: [], setFlows: mockSetFlows }) },
  ),
}));
jest.mock("@/stores/typesStore", () => ({
  useTypesStore: { setState: (...args: unknown[]) => mockSetTypes(...args) },
}));
jest.mock("@/utils/reactflowUtils", () => ({
  processDataFromFlow: jest.fn(async (flow) => flow.data),
  processFlows: (flows: FlowType[]) => ({ data: {}, flows }),
  extractFieldsFromComponenents: () => ({}),
}));

const flow = (name: string): FlowType => ({
  id: name,
  name,
  description: "",
  data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
});
const files = [new File(["{}"], "flow.json", { type: "application/json" })];

describe("atomic flow uploads", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPrepareFlows.mockImplementation(async (flows) => flows);
    mockPostUploadFlows.mockImplementation(async (flows) => flows);
    mockAddFlow.mockResolvedValue("created");
  });

  it.each(["bundle", "selection"])(
    "submits a %s in one batch",
    async (source) => {
      const first = flow("First");
      const second = flow("Second");
      mockGetObjects.mockResolvedValue(
        source === "bundle" ? [{ flows: [first, second] }] : [first, second],
      );
      const { result } = renderHook(() => useUploadFlow());

      await result.current({ files });

      expect(mockPostUploadFlows).toHaveBeenCalledTimes(1);
      expect(mockPostUploadFlows).toHaveBeenCalledWith([first, second]);
      expect(mockAddFlow).not.toHaveBeenCalled();
      expect(mockSetFlows).toHaveBeenCalledWith([first, second]);
    },
  );

  it("leaves client state unchanged when the server rejects any flow", async () => {
    const error = {
      response: {
        status: 422,
        data: { detail: [{ msg: "Only one trigger is allowed" }] },
      },
    };
    mockGetObjects.mockResolvedValue([
      { flows: [flow("Valid"), flow("Invalid")] },
    ]);
    mockPostUploadFlows.mockRejectedValue(error);
    const { result } = renderHook(() => useUploadFlow());

    await expect(result.current({ files })).rejects.toBe(error);

    expect(mockAddFlow).not.toHaveBeenCalled();
    expect(mockSetFlows).not.toHaveBeenCalled();
    expect(mockSetTypes).not.toHaveBeenCalled();
  });

  it("validates every graph before submitting an import", async () => {
    mockGetObjects.mockResolvedValue([flow("Valid"), { name: "Invalid" }]);
    const { result } = renderHook(() => useUploadFlow());

    await expect(result.current({ files })).rejects.toThrow(
      "Invalid flow data",
    );

    expect(mockAddFlow).not.toHaveBeenCalled();
    expect(mockPostUploadFlows).not.toHaveBeenCalled();
  });

  it("shows one clean alert for a rejected dashboard import", async () => {
    const message =
      "A flow can have only one trigger. Remove the extra triggers and try again.";
    mockGetObjects.mockResolvedValue([
      { flows: [flow("Valid"), flow("Invalid")] },
    ]);
    mockPostUploadFlows.mockRejectedValue({
      response: {
        status: 422,
        data: {
          detail: [
            { msg: `Value error, ${message}` },
            { msg: `Value error, ${message}` },
          ],
        },
      },
    });
    const { result } = renderHook(() => useFileDrop("flows"));

    act(() =>
      result.current({
        preventDefault: jest.fn(),
        dataTransfer: { types: ["Files"], files },
      }),
    );

    await waitFor(() => expect(mockSetErrorData).toHaveBeenCalledTimes(1));
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Error occurred while uploading file",
      list: [message],
    });
    expect(mockSetSuccessData).not.toHaveBeenCalled();
    expect(mockAddFlow).not.toHaveBeenCalled();
  });

  it("does not create a destination for an empty selection", async () => {
    mockGetObjects.mockResolvedValue([]);
    const { result } = renderHook(() => useUploadFlow());

    await result.current({ files: [] });

    expect(mockPrepareFlows).not.toHaveBeenCalled();
    expect(mockPostUploadFlows).not.toHaveBeenCalled();
  });

  it("rejects mixed flow and component imports before any write", async () => {
    mockGetObjects.mockResolvedValue([
      flow("Valid"),
      { ...flow("Component"), is_component: true },
    ]);
    const { result } = renderHook(() => useUploadFlow());

    await expect(result.current({ files, isComponent: false })).rejects.toThrow(
      "You cannot upload a component as a flow or vice versa",
    );

    expect(mockPrepareFlows).not.toHaveBeenCalled();
    expect(mockPostUploadFlows).not.toHaveBeenCalled();
  });

  it("keeps canvas drops local and offsets each pasted flow", async () => {
    const first = flow("First");
    const second = flow("Second");
    mockGetObjects.mockResolvedValue([first, second]);
    const { result } = renderHook(() => useUploadFlow());

    await result.current({ files, position: { x: 5, y: 10 } });

    expect(mockPaste).toHaveBeenNthCalledWith(1, first.data, { x: 5, y: 10 });
    expect(mockPaste).toHaveBeenNthCalledWith(2, second.data, { x: 55, y: 60 });
    expect(mockPostUploadFlows).not.toHaveBeenCalled();
    expect(mockPrepareFlows).not.toHaveBeenCalled();
  });
});
