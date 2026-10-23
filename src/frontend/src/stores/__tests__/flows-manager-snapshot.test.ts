import { act } from "@testing-library/react";
import lodash from "lodash";
import useFlowStore from "../flowStore";
import useFlowsManagerStore from "../flowsManagerStore";

jest.mock("@/constants/constants", () => ({ AUTOSAVE_DEBOUNCE_TIME: 1000 }));
jest.mock("../assistantManagerStore", () => ({
  __esModule: true,
  default: {},
}));
jest.mock("../flowStore", () => ({
  __esModule: true,
  default: { getState: jest.fn() },
}));

const createGraph = (value: unknown = "initial") => ({
  nodes: [
    {
      id: "node-1",
      data: { node: { template: { input: { value } } } },
    },
  ],
  edges: [
    {
      id: "edge-1",
      source: "node-1",
      target: "node-2",
      data: { sourceHandle: { output_types: ["Message"] } },
    },
  ],
});

describe("flow snapshots", () => {
  let graph: ReturnType<typeof createGraph>;
  let cloneDeep: jest.SpyInstance;
  let flowId = 0;
  const history = () => useFlowsManagerStore.getState();

  beforeEach(() => {
    jest.clearAllMocks();
    cloneDeep = jest.spyOn(lodash, "cloneDeep");
    graph = createGraph();
    const flowStore = {
      get nodes() {
        return graph.nodes;
      },
      get edges() {
        return graph.edges;
      },
      setNodes: (nodes: typeof graph.nodes) => {
        graph.nodes = nodes;
      },
      setEdges: (edges: typeof graph.edges) => {
        graph.edges = edges;
      },
    };
    jest
      .mocked(useFlowStore.getState)
      .mockReturnValue(
        flowStore as unknown as ReturnType<typeof useFlowStore.getState>,
      );
    act(() => {
      // History is module-scoped and resetStore does not clear it.
      useFlowsManagerStore.setState({ currentFlowId: `snapshot-${flowId++}` });
    });
  });

  afterEach(() => jest.restoreAllMocks());

  it("should capture an empty first snapshot", () => {
    graph.nodes = [];
    graph.edges = [];

    act(() => history().takeSnapshot());
    graph = createGraph();
    act(() => history().undo());

    expect(cloneDeep).toHaveBeenCalledTimes(2);
    expect(graph).toEqual({ nodes: [], edges: [] });
  });

  it("should skip cloning a duplicate graph with new object references", () => {
    act(() => history().takeSnapshot());
    cloneDeep.mockClear();
    graph = createGraph();

    act(() => history().takeSnapshot());

    expect(cloneDeep).not.toHaveBeenCalled();
  });

  it.each(["node", "edge"])(
    "should capture a nested %s mutation without changing earlier snapshots",
    (target) => {
      const value = { items: [{ text: "initial" }] };
      graph = createGraph(value);
      const initial = lodash.cloneDeep(graph);
      act(() => history().takeSnapshot());
      const nodes = graph.nodes;
      const edges = graph.edges;

      if (target === "node") value.items[0].text = "edited";
      else graph.edges[0].data.sourceHandle.output_types.push("Data");
      const edited = lodash.cloneDeep(graph);
      cloneDeep.mockClear();
      act(() => history().takeSnapshot());

      expect(graph.nodes).toBe(nodes);
      expect(graph.edges).toBe(edges);
      expect(cloneDeep).toHaveBeenCalledTimes(2);
      value.items[0].text = "later edit";
      graph.edges[0].data.sourceHandle.output_types.push("Table");
      act(() => history().undo());
      expect(graph).toEqual(edited);
      act(() => history().undo());
      expect(graph).toEqual(initial);
    },
  );

  it("should preserve JSON equality for omitted values", () => {
    graph = createGraph({ value: 1 });
    act(() => history().takeSnapshot());
    graph = createGraph({ value: 1, missing: undefined, callback: () => 2 });
    cloneDeep.mockClear();

    act(() => history().takeSnapshot());

    expect(cloneDeep).not.toHaveBeenCalled();
  });

  it("should retain non-JSON values in accepted snapshots", () => {
    const callback = () => "value";
    const value = {
      date: new Date("2026-01-01T00:00:00Z"),
      missing: undefined,
      callback,
      toJSON() {
        return { date: this.date.toISOString() };
      },
    };
    graph = createGraph(value);
    act(() => history().takeSnapshot());
    cloneDeep.mockClear();
    act(() => history().takeSnapshot());
    expect(cloneDeep).not.toHaveBeenCalled();
    value.date.setUTCFullYear(2027);

    act(() => history().undo());

    const restored = graph.nodes[0].data.node.template.input.value;
    expect(restored).toEqual({
      ...value,
      date: new Date("2026-01-01T00:00:00Z"),
    });
    expect(restored).not.toBe(value);
  });

  it("should preserve the existing circular-data error during comparison", () => {
    const value: { self?: unknown } = {};
    value.self = value;
    graph = createGraph(value);
    act(() => history().takeSnapshot());

    expect(() => history().takeSnapshot()).toThrow(TypeError);
    graph = createGraph();
    act(() => history().undo());
    const restored = graph.nodes[0].data.node.template.input.value;
    expect(restored).toEqual(value);
    expect(restored).not.toBe(value);
  });

  it("should retain redo history when a duplicate is skipped", () => {
    act(() => history().takeSnapshot());
    graph = createGraph("second");
    act(() => history().takeSnapshot());
    graph = createGraph("third");
    act(() => history().undo());
    graph = createGraph();

    act(() => {
      history().takeSnapshot();
      history().redo();
    });

    expect(graph).toEqual(createGraph("third"));
  });

  it("should clear redo history when a new snapshot is captured", () => {
    act(() => history().takeSnapshot());
    graph = createGraph("second");
    act(() => history().undo());
    graph = createGraph("new branch");

    act(() => {
      history().takeSnapshot();
      history().redo();
    });

    expect(graph).toEqual(createGraph("new branch"));
    act(() => history().undo());
    expect(graph).toEqual(createGraph("new branch"));
  });

  it("should isolate undo and redo history by flow", () => {
    const firstFlowId = history().currentFlowId;
    act(() => history().takeSnapshot());
    graph = createGraph("edited");
    act(() => history().undo());
    act(() => {
      useFlowsManagerStore.setState({ currentFlowId: `${firstFlowId}-other` });
      history().takeSnapshot();
    });
    graph = createGraph("other flow");
    act(() => history().undo());
    expect(graph).toEqual(createGraph());

    act(() => {
      useFlowsManagerStore.setState({ currentFlowId: firstFlowId });
      history().redo();
    });

    expect(graph).toEqual(createGraph("edited"));
  });

  it("should not trim history when skipping duplicate snapshots", () => {
    act(() => {
      for (let value = 0; value < 10; value++) {
        graph = createGraph(value);
        history().takeSnapshot();
      }
      for (let duplicate = 0; duplicate < 100; duplicate++) {
        history().takeSnapshot();
      }
    });
    graph = createGraph("current");
    act(() => {
      for (let step = 0; step < 10; step++) history().undo();
    });
    expect(graph).toEqual(createGraph(0));

    act(() => history().undo());

    expect(graph).toEqual(createGraph(0));
  });
});
