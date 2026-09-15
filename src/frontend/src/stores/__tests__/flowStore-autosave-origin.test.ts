import { act } from "@testing-library/react";
import type { AllNodeType, EdgeType } from "@/types/flow";

jest.mock("@xyflow/react", () => ({
  addEdge: jest.fn(),
  applyEdgeChanges: jest.fn((_changes, edges) => edges),
  applyNodeChanges: jest.fn((_changes, nodes) => nodes),
}));

jest.mock("../../i18n", () => ({
  __esModule: true,
  default: { t: jest.fn((key: string) => key) },
}));

jest.mock("../alertStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({ setErrorData: jest.fn(), setSuccessData: jest.fn() }),
  },
}));

jest.mock("../flowsManagerStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      currentFlow: undefined,
      currentFlowId: "flow-1",
      setCurrentFlow: jest.fn(),
      autoSaving: true,
    }),
  },
}));

jest.mock("../tweaksStore", () => ({
  useTweaksStore: { getState: () => ({ initialSetup: jest.fn() }) },
}));

jest.mock("@/CustomNodes/helpers/check-code-validity", () => ({
  checkCodeValidity: jest.fn(() => null),
}));

import useFlowStore from "../flowStore";

const node = (id: string): AllNodeType =>
  ({
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: {
      id,
      type: "ChatInput",
      node: { display_name: id, description: "", template: {} },
    },
  }) as unknown as AllNodeType;

describe("flowStore autosave origin", () => {
  let autoSaveFlow: jest.Mock;

  beforeEach(() => {
    autoSaveFlow = jest.fn();
    act(() => {
      useFlowStore.setState({
        nodes: [node("a")],
        edges: [] as EdgeType[],
        autoSaveFlow: autoSaveFlow as never,
      });
    });
  });

  describe("a user-originated mutation still autosaves", () => {
    it("setNodes", () => {
      act(() => useFlowStore.getState().setNodes([node("a"), node("b")]));
      expect(autoSaveFlow).toHaveBeenCalledTimes(1);
    });

    it("setEdges", () => {
      act(() => useFlowStore.getState().setEdges([]));
      expect(autoSaveFlow).toHaveBeenCalledTimes(1);
    });

    it("setNodesAndEdges", () => {
      act(() => useFlowStore.getState().setNodesAndEdges([node("a")], []));
      expect(autoSaveFlow).toHaveBeenCalledTimes(1);
    });

    it("setNode", () => {
      act(() => useFlowStore.getState().setNode("a", node("a")));
      expect(autoSaveFlow).toHaveBeenCalledTimes(1);
    });
  });

  describe("a write marked autoSave:false does not autosave", () => {
    it("setNodes", () => {
      act(() =>
        useFlowStore.getState().setNodes([node("a"), node("b")], {
          autoSave: false,
        }),
      );
      expect(autoSaveFlow).not.toHaveBeenCalled();
    });

    it("setEdges", () => {
      act(() => useFlowStore.getState().setEdges([], { autoSave: false }));
      expect(autoSaveFlow).not.toHaveBeenCalled();
    });

    it("setNodesAndEdges", () => {
      act(() =>
        useFlowStore
          .getState()
          .setNodesAndEdges([node("a")], [], { autoSave: false }),
      );
      expect(autoSaveFlow).not.toHaveBeenCalled();
    });

    it("setNode", () => {
      act(() =>
        useFlowStore
          .getState()
          .setNode("a", node("a"), true, undefined, { autoSave: false }),
      );
      expect(autoSaveFlow).not.toHaveBeenCalled();
    });
  });

  // The store still applies the change; only the save is withheld. A gate that
  // dropped the mutation would leave the canvas showing stale data.
  it("applies the mutation it declines to save", () => {
    act(() =>
      useFlowStore
        .getState()
        .setNodes([node("a"), node("b")], { autoSave: false }),
    );
    expect(useFlowStore.getState().nodes.map((n) => n.id)).toEqual(["a", "b"]);
  });

  // Opting out is per call: the next user edit must save normally, otherwise a
  // hydration write would silently disable saving for the rest of the session.
  it("does not leak the opt-out into the next mutation", () => {
    act(() =>
      useFlowStore.getState().setNodes([node("a")], { autoSave: false }),
    );
    act(() => useFlowStore.getState().setNodes([node("a"), node("b")]));
    expect(autoSaveFlow).toHaveBeenCalledTimes(1);
  });
});
