import { renderHook } from "@testing-library/react";
import type { FlowType } from "@/types/flow";
import useDeleteFlow from "../use-delete-flow";

const mockSetFlows = jest.fn();
const mockMutate = jest.fn();

const flowsState: { flows: FlowType[] } = { flows: [] };

jest.mock("@/controllers/API/queries/flows/use-delete-delete-flows", () => ({
  useDeleteDeleteFlows: () => ({ mutate: mockMutate, isPending: false }),
}));

type Selector<T> = (state: T) => unknown;
type FlowsManagerState = { flows: FlowType[]; setFlows: jest.Mock };

jest.mock("@/stores/flowsManagerStore", () => {
  const store = Object.assign(
    (selector: Selector<FlowsManagerState>) =>
      selector({ flows: flowsState.flows, setFlows: mockSetFlows }),
    { getState: () => ({ flows: flowsState.flows, setFlows: mockSetFlows }) },
  );
  return { __esModule: true, default: store };
});

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: { setState: jest.fn() },
}));

jest.mock("@/utils/reactflowUtils", () => ({
  processFlows: (flows: FlowType[]) => ({ data: {}, flows }),
  extractFieldsFromComponenents: () => ({}),
}));

const makeFlow = (id: string): FlowType =>
  ({ id, name: id, data: { nodes: [], edges: [], viewport: {} } }) as FlowType;

describe("useDeleteFlow", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    flowsState.flows = [];
  });

  it("should_remove_only_deleted_flows_when_delete_succeeds", async () => {
    flowsState.flows = [makeFlow("flow-a"), makeFlow("flow-b")];
    mockMutate.mockImplementation((_vars, { onSuccess }) => onSuccess());

    const { result } = renderHook(() => useDeleteFlow());
    await result.current.deleteFlow({ id: "flow-a" });

    expect(mockSetFlows).toHaveBeenCalledWith([
      expect.objectContaining({ id: "flow-b" }),
    ]);
  });

  it("should_keep_flow_created_while_delete_was_in_flight", async () => {
    flowsState.flows = [makeFlow("placeholder")];
    // Simulate a flow landing in the store (e.g. a template flow created by
    // the welcome overlay handoff) before the DELETE response arrives.
    mockMutate.mockImplementation((_vars, { onSuccess }) => {
      flowsState.flows = [makeFlow("placeholder"), makeFlow("template-flow")];
      onSuccess();
    });

    const { result } = renderHook(() => useDeleteFlow());
    await result.current.deleteFlow({ id: "placeholder" });

    expect(mockSetFlows).toHaveBeenCalledWith([
      expect.objectContaining({ id: "template-flow" }),
    ]);
  });

  it("should_reject_when_delete_fails", async () => {
    flowsState.flows = [makeFlow("flow-a")];
    const error = new Error("boom");
    mockMutate.mockImplementation((_vars, { onError }) => onError(error));

    const { result } = renderHook(() => useDeleteFlow());

    await expect(result.current.deleteFlow({ id: "flow-a" })).rejects.toThrow(
      "boom",
    );
    expect(mockSetFlows).not.toHaveBeenCalled();
  });
});
