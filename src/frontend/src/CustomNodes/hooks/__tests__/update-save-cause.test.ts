import { act, renderHook } from "@testing-library/react";
import useFlowSaveCauseStore from "@/stores/flowSaveCauseStore";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType } from "@/types/api";
import useUpdateAllNodes from "../use-update-all-nodes";
import useUpdateNodeCode from "../use-update-node-code";

const newNodeClass = {
  description: "",
  display_name: "Agent",
  documentation: "",
  template: { code: { value: "" } },
  outputs: [],
} as unknown as APIClassType;

const oldNode = {
  id: "Agent-1",
  data: {
    id: "Agent-1",
    type: "Agent",
    node: { ...newNodeClass, outputs: [] },
  },
};

describe("component updates mark the next save", () => {
  beforeEach(() => {
    useFlowStore.setState({ currentFlow: { id: "flow-1" } as never });
    useFlowSaveCauseStore.setState({ pending: null });
  });

  it("with upgrade_component after one component update", () => {
    const setNode = jest.fn((_id, change) => change(oldNode));
    const { result } = renderHook(() =>
      useUpdateNodeCode("Agent-1", newNodeClass, setNode, jest.fn()),
    );

    act(() => result.current(newNodeClass, "code", "code", "Agent"));

    expect(setNode).toHaveBeenCalled();
    expect(useFlowSaveCauseStore.getState().takePendingCause("flow-1")).toBe(
      "upgrade_component",
    );
  });

  it("with upgrade_component after updating all components", () => {
    const setNodes = jest.fn();
    const { result } = renderHook(() => useUpdateAllNodes(setNodes, jest.fn()));

    act(() =>
      result.current([
        { nodeId: "Agent-1", newNode: newNodeClass, code: "", name: "code" },
      ]),
    );

    expect(setNodes).toHaveBeenCalled();
    expect(useFlowSaveCauseStore.getState().pending).toEqual({
      flowId: "flow-1",
      cause: "upgrade_component",
    });
  });
});
