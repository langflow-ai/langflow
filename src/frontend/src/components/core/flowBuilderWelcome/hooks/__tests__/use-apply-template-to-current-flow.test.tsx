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
const setCurrentFlowInManager = jest.fn();
const saveFlow = jest.fn().mockResolvedValue(undefined);
const requestFitView = jest.fn();

let currentFlow: unknown;

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn((selector?: (state: unknown) => unknown) => {
    const state = { setNodes, setEdges, currentFlow, requestFitView };
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
      const state = {
        examples,
        flows,
        setCurrentFlow: setCurrentFlowInManager,
      };
      return selector ? selector(state) : state;
    },
  );
  (mockedFlowsManagerStore as unknown as { getState: () => unknown }).getState =
    () => ({ currentFlow });
}

describe("useApplyTemplateToCurrentFlow", () => {
  beforeEach(() => {
    setNodes.mockClear();
    setEdges.mockClear();
    setCurrentFlowInManager.mockClear();
    saveFlow.mockClear();
    requestFitView.mockClear();
    currentFlow = {
      id: "flow-1",
      name: "New Flow",
      folder_id: "folder-A",
      data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
    };
    setStores(fullExamples);
  });

  it("should_apply_template_data_to_current_flow_when_template_is_applied", () => {
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    let didApply = false;
    act(() => {
      didApply = result.current("simple_agent");
    });

    expect(didApply).toBe(true);
    // setCurrentFlowInManager (which internally calls resetFlow → setNodes/setEdges)
    // is the path taken when currentFlow exists.
    expect(setCurrentFlowInManager).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          nodes: [{ id: "n1" }],
          edges: [{ id: "e1" }],
        }),
      }),
    );
  });

  it("should_pick_the_correct_template_when_a_different_name_key_is_passed", () => {
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    act(() => {
      result.current("vector_store_rag");
    });

    expect(setCurrentFlowInManager).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          nodes: [{ id: "n2" }, { id: "n3" }],
          edges: [{ id: "e2" }],
        }),
      }),
    );
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
    expect(setCurrentFlowInManager).toHaveBeenCalledWith(
      expect.objectContaining({ id: "flow-1", name: "Simple Agent" }),
    );
    // ...and the rename is persisted via saveFlow.
    expect(saveFlow).toHaveBeenCalledWith(
      expect.objectContaining({ id: "flow-1", name: "Simple Agent" }),
      expect.anything(),
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

    expect(setCurrentFlowInManager).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Simple Agent (1)" }),
    );
  });

  it("should_dedupe_against_a_same_named_flow_in_a_different_folder", () => {
    // Flow names are unique per USER in the database (``unique_flow_name`` on
    // (user_id, name)), not per folder. A folder-scoped rename lets the clash
    // through and the PATCH comes back 400 "Name must be unique" (LE-2232).
    setStores(fullExamples, [
      { id: "other", name: "Simple Agent", folder_id: "folder-B" },
    ]);
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    act(() => {
      result.current("simple_agent");
    });

    expect(setCurrentFlowInManager).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Simple Agent (1)" }),
    );
    expect(saveFlow).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Simple Agent (1)" }),
      expect.anything(),
    );
  });

  it("should_issue_the_save_before_the_optimistic_store_swap", () => {
    // useSaveFlow skips the request when the payload already equals the
    // manager store's flow, so swapping first turns the save into a no-op and
    // leaves persistence to the debounced autosave — where nothing can react
    // to a rejected rename.
    let swapsWhenSaveWasCalled = -1;
    saveFlow.mockImplementationOnce(() => {
      swapsWhenSaveWasCalled = setCurrentFlowInManager.mock.calls.length;
      return Promise.resolve(undefined);
    });
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    act(() => {
      result.current("simple_agent");
    });

    expect(swapsWhenSaveWasCalled).toBe(0);
    expect(setCurrentFlowInManager).toHaveBeenCalledTimes(1);
  });

  it("should_not_dedupe_against_ownerless_example_flows", () => {
    // Under AUTO_LOGIN the flows list also carries the ownerless starter
    // examples. They hold no user_id, so they never collide — suffixing
    // because of them would rename a flow whose name is actually free.
    setStores(fullExamples, [
      { id: "ex-1", name: "Simple Agent", folder_id: "starter-folder" },
    ]);
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    act(() => {
      result.current("simple_agent");
    });

    expect(setCurrentFlowInManager).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Simple Agent" }),
    );
  });

  it("should_retry_with_the_next_version_when_the_save_hits_a_name_conflict", async () => {
    // Safety net for what no client-side list can see: another tab/session
    // taking the name between the read and the PATCH. Retry with the next
    // free version instead of dropping the template on the floor.
    saveFlow.mockRejectedValueOnce({
      response: { status: 400, data: { detail: "Name must be unique" } },
    });
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    await act(async () => {
      result.current("simple_agent");
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(saveFlow).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ name: "Simple Agent" }),
      expect.anything(),
    );
    expect(saveFlow).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ name: "Simple Agent (1)" }),
      expect.anything(),
    );
    expect(setCurrentFlowInManager).toHaveBeenLastCalledWith(
      expect.objectContaining({ name: "Simple Agent (1)" }),
    );
  });

  it("should_stop_retrying_and_roll_back_when_every_version_conflicts", async () => {
    saveFlow.mockRejectedValue({
      response: { status: 400, data: { detail: "Name must be unique" } },
    });
    const original = currentFlow;
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    await act(async () => {
      result.current("simple_agent");
      for (let i = 0; i < 20; i++) await Promise.resolve();
    });

    expect(saveFlow.mock.calls.length).toBeLessThanOrEqual(5);
    expect(setCurrentFlowInManager).toHaveBeenLastCalledWith(original);
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

    expect(setCurrentFlowInManager).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ name: "Simple Agent" }),
    );
    expect(setCurrentFlowInManager).toHaveBeenLastCalledWith(original);
  });

  // A template's nodes measure over several frames; fitting before they all
  // have dimensions frames the flow around a subset, which is what the welcome
  // overlay would then uncover.
  it("should_defer_the_fit_until_the_canvas_reports_the_graph_measured", () => {
    const onFitted = jest.fn();
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    act(() => {
      result.current("simple_agent", onFitted);
    });

    expect(requestFitView).toHaveBeenCalledTimes(1);
    expect(onFitted).not.toHaveBeenCalled();

    act(() => {
      requestFitView.mock.calls[0][0]();
    });

    expect(onFitted).toHaveBeenCalledTimes(1);
    // The canvas corrects the framing itself when uncovering narrows it, so
    // uncovering must not queue a second fit that races that resize.
    expect(requestFitView).toHaveBeenCalledTimes(1);
  });

  it("should_not_rename_or_persist_when_there_is_no_current_flow", () => {
    currentFlow = undefined;
    const { result } = renderHook(() => useApplyTemplateToCurrentFlow());

    act(() => {
      result.current("simple_agent");
    });

    expect(setCurrentFlowInManager).not.toHaveBeenCalled();
    expect(saveFlow).not.toHaveBeenCalled();
  });
});
