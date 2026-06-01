/**
 * Tests for the hook that swaps the current empty flow's nodes/edges with a
 * starter template's data. Used by the welcome overlay's quick-template
 * buttons (Simple Agent / Vector Store RAG).
 */

import { act, renderHook } from "@testing-library/react";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useApplyTemplateToCurrentFlow } from "../use-apply-template-to-current-flow";

const setNodes = jest.fn();
const setEdges = jest.fn();

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn((selector?: (state: unknown) => unknown) => {
    const state = { setNodes, setEdges };
    return selector ? selector(state) : state;
  }),
}));

const fullExamples = [
  {
    id: "ex-1",
    name: "Simple Agent",
    name_key: "simple_agent",
    description: "",
    tags: [],
    data: {
      nodes: [{ id: "n1" }],
      edges: [{ id: "e1" }],
      viewport: { x: 0, y: 0, zoom: 1 },
    },
  },
  {
    id: "ex-2",
    name: "Vector Store RAG",
    name_key: "vector_store_rag",
    description: "",
    tags: [],
    data: {
      nodes: [{ id: "n2" }, { id: "n3" }],
      edges: [{ id: "e2" }],
      viewport: { x: 0, y: 0, zoom: 1 },
    },
  },
];

const mockedFlowsManagerStore = useFlowsManagerStore as unknown as jest.Mock;

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: jest.fn(),
}));

function setExamples(examples: typeof fullExamples) {
  mockedFlowsManagerStore.mockImplementation(
    (selector?: (state: unknown) => unknown) => {
      const state = { examples };
      return selector ? selector(state) : state;
    },
  );
}

describe("useApplyTemplateToCurrentFlow", () => {
  beforeEach(() => {
    setNodes.mockClear();
    setEdges.mockClear();
    setExamples(fullExamples);
  });

  it("should_call_setNodes_and_setEdges_with_template_data_when_template_is_applied", () => {
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    let didApply = false;
    act(() => {
      didApply = result.current("simple_agent");
    });

    expect(didApply).toBe(true);
    expect(setNodes).toHaveBeenCalledWith([{ id: "n1" }]);
    expect(setEdges).toHaveBeenCalledWith([{ id: "e1" }]);
  });

  it("should_pick_the_correct_template_when_a_different_name_key_is_passed", () => {
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    act(() => {
      result.current("vector_store_rag");
    });

    expect(setNodes).toHaveBeenCalledWith([{ id: "n2" }, { id: "n3" }]);
    expect(setEdges).toHaveBeenCalledWith([{ id: "e2" }]);
  });

  it("should_return_false_and_not_mutate_when_no_example_matches_name_key", () => {
    // ``examples`` may be empty (mid-load) or a key may not exist yet — the
    // hook must fail closed instead of clearing the canvas with nothing.
    setExamples([]);
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    let didApply = true;
    act(() => {
      didApply = result.current("simple_agent");
    });

    expect(didApply).toBe(false);
    expect(setNodes).not.toHaveBeenCalled();
    expect(setEdges).not.toHaveBeenCalled();
  });
});
