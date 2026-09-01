import { act, renderHook } from "@testing-library/react";
import useApplyFlowToCanvas from "@/hooks/flows/use-apply-flow-to-canvas";
import useFlowStore from "@/stores/flowStore";
import type { FlowType } from "@/types/flow";

const setCurrentFlowMock = jest.fn();
const refreshAllModelInputsMock = jest.fn().mockResolvedValue(undefined);

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setCurrentFlow: setCurrentFlowMock }),
}));

jest.mock("@/hooks/use-refresh-model-inputs", () => ({
  useRefreshModelInputs: () => ({
    refreshAllModelInputs: refreshAllModelInputsMock,
  }),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  processFlows: jest.fn(),
}));

function makeFlow(): FlowType {
  return {
    id: "flow-1",
    name: "Flow",
    description: "",
    data: {
      nodes: [{ id: "node-1", position: { x: 0, y: 0 }, data: {} }],
      edges: [],
    },
  } as unknown as FlowType;
}

describe("useApplyFlowToCanvas", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useFlowStore.setState({
      fitViewRequest: { id: 0 },
      reactFlowInstance: null,
    });
  });

  it("should apply the flow to the canvas", () => {
    const { result } = renderHook(() => useApplyFlowToCanvas());
    const flow = makeFlow();

    act(() => {
      result.current(flow);
    });

    expect(setCurrentFlowMock).toHaveBeenCalledTimes(1);
    expect(refreshAllModelInputsMock).toHaveBeenCalledWith({ silent: true });
  });

  // Fitting here would measure an incomplete graph: the nodes have not been
  // laid out yet, and ReactFlow drops unmeasured nodes from the bounding box.
  it("should request a fit instead of fitting the canvas immediately", () => {
    const fitView = jest.fn();
    useFlowStore.setState({
      reactFlowInstance: { fitView } as never,
    });
    const { result } = renderHook(() => useApplyFlowToCanvas());

    act(() => {
      result.current(makeFlow());
    });

    expect(fitView).not.toHaveBeenCalled();
    expect(useFlowStore.getState().fitViewRequest.id).toBe(1);
  });

  it("should request one fit per applied flow", () => {
    const { result } = renderHook(() => useApplyFlowToCanvas());

    act(() => {
      result.current(makeFlow());
      result.current(makeFlow());
    });

    expect(useFlowStore.getState().fitViewRequest.id).toBe(2);
  });

  // A request left pending on an empty flow would be answered by the first
  // component the user drops, re-framing the canvas mid-edit.
  it("should not request a fit for a flow with no nodes", () => {
    const { result } = renderHook(() => useApplyFlowToCanvas());
    const empty = makeFlow();
    empty.data!.nodes = [];

    act(() => {
      result.current(empty);
    });

    expect(setCurrentFlowMock).toHaveBeenCalledTimes(1);
    expect(useFlowStore.getState().fitViewRequest.id).toBe(0);
  });

  // The flow-events refresh re-applies the graph under a canvas the user is
  // already working in.
  it("should not request a fit when the caller opts out", () => {
    const { result } = renderHook(() => useApplyFlowToCanvas());

    act(() => {
      result.current(makeFlow(), { fitView: false });
    });

    expect(setCurrentFlowMock).toHaveBeenCalledTimes(1);
    expect(useFlowStore.getState().fitViewRequest.id).toBe(0);
  });

  it("should not touch the canvas when processFlows destroys every node", () => {
    const { processFlows } = jest.requireMock("@/utils/reactflowUtils");
    processFlows.mockImplementationOnce((flows: FlowType[]) => {
      flows[0].data!.nodes = [];
    });
    const { result } = renderHook(() => useApplyFlowToCanvas());

    expect(() => result.current(makeFlow())).toThrow(
      /processFlows destroyed all nodes/,
    );
    expect(setCurrentFlowMock).not.toHaveBeenCalled();
    expect(useFlowStore.getState().fitViewRequest.id).toBe(0);
  });
});
