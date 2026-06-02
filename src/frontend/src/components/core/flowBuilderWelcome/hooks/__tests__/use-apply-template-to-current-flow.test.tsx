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
const setCurrentFlow = jest.fn();
const saveFlow = jest.fn().mockResolvedValue(undefined);

let currentFlow: unknown;

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn((selector?: (state: unknown) => unknown) => {
    const state = { setNodes, setEdges, setCurrentFlow, currentFlow };
    return selector ? selector(state) : state;
  }),
}));

jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => saveFlow,
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

function setStores(
  examples: typeof fullExamples,
  flows: Array<{ id: string; name: string; folder_id?: string }> = [],
) {
  mockedFlowsManagerStore.mockImplementation(
    (selector?: (state: unknown) => unknown) => {
      const state = { examples, flows };
      return selector ? selector(state) : state;
    },
  );
}

describe("useApplyTemplateToCurrentFlow", () => {
  beforeEach(() => {
    setNodes.mockClear();
    setEdges.mockClear();
    setCurrentFlow.mockClear();
    saveFlow.mockClear();
    currentFlow = {
      id: "flow-1",
      name: "New Flow",
      folder_id: "folder-A",
      data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
    };
    setStores(fullExamples);
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
    setStores([]);
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    let didApply = true;
    act(() => {
      didApply = result.current("simple_agent");
    });

    expect(didApply).toBe(false);
    expect(setNodes).not.toHaveBeenCalled();
    expect(setEdges).not.toHaveBeenCalled();
  });

  it("should_rename_the_current_flow_to_the_template_name_and_persist_when_template_is_applied", () => {
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    act(() => {
      result.current("simple_agent");
    });

    // The generic "New Flow" placeholder adopts the template name...
    expect(setCurrentFlow).toHaveBeenCalledWith(
      expect.objectContaining({ id: "flow-1", name: "Simple Agent" }),
    );
    // ...and the rename is persisted via saveFlow.
    expect(saveFlow).toHaveBeenCalledWith(
      expect.objectContaining({ id: "flow-1", name: "Simple Agent" }),
    );
  });

  it("should_dedupe_the_template_name_when_a_flow_with_that_name_already_exists_in_the_same_folder", () => {
    // The "Starter Project" folder is seeded with real starter-project flows
    // (one literally named "Simple Agent"). Matching the rest of the app, the
    // rename version-dedupes against sibling flows → "Simple Agent (1)".
    setStores(fullExamples, [
      { id: "seeded", name: "Simple Agent", folder_id: "folder-A" },
    ]);
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    act(() => {
      result.current("simple_agent");
    });

    expect(setCurrentFlow).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Simple Agent (1)" }),
    );
  });

  it("should_not_dedupe_against_a_same_named_flow_in_a_different_folder", () => {
    // Dedupe must be folder-scoped, mirroring ``useAddFlow``. A "Simple Agent"
    // sitting in another folder must not bump this folder's flow to "(1)".
    setStores(fullExamples, [
      { id: "other", name: "Simple Agent", folder_id: "folder-B" },
    ]);
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    act(() => {
      result.current("simple_agent");
    });

    expect(setCurrentFlow).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Simple Agent" }),
    );
  });

  it("should_revert_the_optimistic_rename_when_the_persist_fails", async () => {
    // The rename is applied optimistically to flowStore, then persisted. If the
    // save fails, the optimistic flowStore state must roll back so it does not
    // diverge from the flows list / backend (which still hold "New Flow").
    const original = currentFlow;
    saveFlow.mockRejectedValueOnce(new Error("persist failed"));
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    await act(async () => {
      result.current("simple_agent");
      await Promise.resolve();
    });

    expect(setCurrentFlow).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ name: "Simple Agent" }),
    );
    expect(setCurrentFlow).toHaveBeenLastCalledWith(original);
  });

  it("should_not_rename_or_persist_when_there_is_no_current_flow", () => {
    currentFlow = undefined;
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    act(() => {
      result.current("simple_agent");
    });

    expect(setCurrentFlow).not.toHaveBeenCalled();
    expect(saveFlow).not.toHaveBeenCalled();
  });
});
