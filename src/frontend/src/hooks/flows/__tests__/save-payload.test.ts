import type { FlowType } from "@/types/flow";
import { buildFlowUpdatePayload } from "../save-payload";

const graph = (label: string) =>
  ({
    nodes: [{ id: "n1", data: { label } }],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
  }) as unknown as FlowType["data"];

const flow = (overrides: Partial<FlowType> = {}): FlowType =>
  ({
    id: "flow-1",
    name: "mine",
    description: "",
    folder_id: "folder-1",
    endpoint_name: null,
    locked: false,
    data: graph("base"),
    ...overrides,
  }) as unknown as FlowType;

const baseline = (overrides: Partial<FlowType> = {}): FlowType =>
  flow({ version_token: "token-a", ...overrides } as Partial<FlowType>);

describe("the payload a save sends", () => {
  it("should carry the graph and the precondition when the graph changed", () => {
    const payload = buildFlowUpdatePayload({
      flow: flow({ data: graph("edited") }),
      persisted: baseline(),
      flows: [],
      live: undefined,
      userEdited: true,
    });

    expect(payload.data).toEqual(graph("edited"));
    expect(payload.versionToken).toBe("token-a");
  });

  it("should omit the graph when only the name changed", () => {
    const payload = buildFlowUpdatePayload({
      flow: flow({ name: "renamed" }),
      persisted: baseline(),
      flows: [],
      live: undefined,
      userEdited: true,
    });

    expect("data" in payload).toBe(false);
    expect(payload.name).toBe("renamed");
  });

  it("should omit the precondition with the graph, so a rename is never refused", () => {
    // A rename does not take the writer's turn, so sending If-Match would have it
    // refused for a graph change it is not making — and the rename then vanished
    // without a word.
    const payload = buildFlowUpdatePayload({
      flow: flow({ name: "renamed" }),
      persisted: baseline(),
      flows: [],
      live: undefined,
      userEdited: true,
    });

    expect(payload.versionToken).toBeNull();
  });

  it("should still send the graph when there is no baseline to compare against", () => {
    const payload = buildFlowUpdatePayload({
      flow: flow({ name: "renamed" }),
      persisted: undefined,
      flows: [],
      live: undefined,
      userEdited: true,
    });

    expect(payload.data).toEqual(graph("base"));
  });

  it("should not treat panning the canvas as a graph change", () => {
    const panned = {
      nodes: [{ id: "n1", data: { label: "base" } }],
      edges: [],
      viewport: { x: 900, y: -400, zoom: 2 },
    } as unknown as FlowType["data"];

    const payload = buildFlowUpdatePayload({
      flow: flow({ name: "renamed", data: panned }),
      persisted: baseline(),
      flows: [],
      live: undefined,
      userEdited: true,
    });

    expect("data" in payload).toBe(false);
    expect(payload.versionToken).toBeNull();
  });

  it("should not treat selecting a node as a graph change", () => {
    // Clicking a node writes `selected` into the graph. Counted as an edit, it
    // took the writer's turn and refused everyone else's save for nothing.
    const selected = {
      nodes: [{ id: "n1", data: { label: "base" }, selected: true }],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    } as unknown as FlowType["data"];

    const payload = buildFlowUpdatePayload({
      flow: flow({ name: "renamed", data: selected }),
      persisted: baseline(),
      flows: [],
      live: undefined,
      userEdited: true,
    });

    expect("data" in payload).toBe(false);
  });

  it("should flag a project move so the scoped caches are cleared", () => {
    const payload = buildFlowUpdatePayload({
      flow: flow({ folder_id: "folder-2" }),
      persisted: baseline(),
      flows: [],
      live: undefined,
      userEdited: true,
    });

    expect(payload.providerScopeChanged).toBe(true);
  });
});

describe("whose change the graph is", () => {
  const live = (label: string) => ({
    nodes: [{ id: "n1", data: { label } }],
    edges: [],
  });

  it("should leave the graph out when the person has not edited it", () => {
    // Opening a flow rewrites nodes on the way in. Treating that as the person's
    // work sent the whole canvas with a rename, which the server then refused as
    // a competing graph write — and the rename was dropped in silence.
    const payload = buildFlowUpdatePayload({
      flow: flow({ name: "renamed", data: graph("hydrated") }),
      persisted: baseline(),
      flows: [],
      live: live("hydrated"),
      userEdited: false,
    });

    expect("data" in payload).toBe(false);
    expect(payload.name).toBe("renamed");
  });

  it("should send the graph once the person has edited it", () => {
    const payload = buildFlowUpdatePayload({
      flow: flow({ data: graph("edited") }),
      persisted: baseline(),
      flows: [],
      live: live("edited"),
      userEdited: true,
    });

    expect(payload.data).toEqual(graph("edited"));
    expect(payload.versionToken).toBe("token-a");
  });

  it("should not call a selected node on the canvas a graph of its own", () => {
    // The payload is normalised before comparing; the live graph has to be too,
    // or a node the person merely clicked reads as a caller-supplied graph and
    // the save carries a precondition it never needed.
    const payload = buildFlowUpdatePayload({
      flow: flow({ name: "renamed", data: graph("base") }),
      persisted: baseline(),
      flows: [],
      live: {
        nodes: [{ id: "n1", data: { label: "base" }, selected: true }],
        edges: [],
      },
      userEdited: false,
    });

    expect("data" in payload).toBe(false);
    expect(payload.versionToken).toBeNull();
  });

  it("should send a graph the caller supplied itself, edits or not", () => {
    // Applying a template writes a graph the canvas does not hold yet.
    const payload = buildFlowUpdatePayload({
      flow: flow({ data: graph("from-template") }),
      persisted: baseline(),
      flows: [],
      live: live("base"),
      userEdited: false,
    });

    expect(payload.data).toEqual(graph("from-template"));
  });
});
