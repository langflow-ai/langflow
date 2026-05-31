import { renderHook } from "@testing-library/react";

import useUploadFlow from "../use-upload-flow";

const mockGetObjectsFromFilelist = jest.fn();
const mockProcessDataFromFlow = jest.fn();
const mockAddFlow = jest.fn();
const mockPaste = jest.fn();

jest.mock("@/helpers/get-objects-from-filelist", () => ({
  getObjectsFromFilelist: (...args: unknown[]) =>
    mockGetObjectsFromFilelist(...args),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  processDataFromFlow: (...args: unknown[]) => mockProcessDataFromFlow(...args),
}));

jest.mock("../use-add-flow", () => ({
  __esModule: true,
  default: () => mockAddFlow,
}));

jest.mock("@/stores/flowStore", () => {
  const useFlowStoreMock = (
    selector: (state: { paste: jest.Mock }) => unknown,
  ) => selector({ paste: mockPaste });
  return {
    __esModule: true,
    default: useFlowStoreMock,
  };
});

describe("useUploadFlow", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("uses paste for canvas JSON drop/import so collaboration mode can emit add operations", async () => {
    const flow = {
      id: "flow-1",
      name: "Imported Flow",
      data: {
        nodes: [{ id: "n1" }],
        edges: [{ id: "e1", source: "n1", target: "n2" }],
      },
    };
    mockGetObjectsFromFilelist.mockResolvedValue([flow]);
    mockProcessDataFromFlow.mockResolvedValue(undefined);
    const { result } = renderHook(() => useUploadFlow());
    const position = { x: 10, y: 20 };

    await result.current({
      files: [new File(["{}"], "flow.json", { type: "application/json" })],
      position,
    });

    expect(mockProcessDataFromFlow).toHaveBeenCalledWith(flow);
    expect(mockPaste).toHaveBeenCalledWith(flow.data, position);
    expect(mockAddFlow).not.toHaveBeenCalled();
  });
});
