/**
 * Tests for `applyStateDelta` — the JSON-Patch parser the bridge runs on
 * every `STATE_DELTA` event. The regex (`^\/nodes\/([^/]+)$`), the
 * add/replace gating, and the BUILDING fallback for unknown statuses are
 * the bits a backend wire-shape change would silently break, so we pin
 * them directly against the real flowStore singleton.
 */

import { BuildStatus } from "@/constants/enums";
import { applyStateDelta } from "@/controllers/API/agui/run-flow-bridge";
import useFlowStore from "@/stores/flowStore";

beforeEach(() => {
  // Zustand singleton — only blow away the slices this helper touches so the
  // rest of the store's action surface (updateBuildStatus, addDataToFlowPool)
  // keeps working as written.
  useFlowStore.setState({ flowBuildStatus: {}, flowPool: {} });
});

describe("applyStateDelta", () => {
  it("adds the vertex build entry on op:add with success + output", () => {
    const touched = new Set<string>();

    applyStateDelta(
      [
        {
          op: "add",
          path: "/nodes/node-a",
          value: {
            status: "success",
            output: { results: { text: "hi" } },
          },
        },
      ],
      "run-1",
      touched,
    );

    const state = useFlowStore.getState();
    expect(state.flowBuildStatus["node-a"]?.status).toBe(BuildStatus.BUILT);
    expect(state.flowPool["node-a"]).toHaveLength(1);
    expect(state.flowPool["node-a"][0]).toMatchObject({
      id: "node-a",
      run_id: "run-1",
      valid: true,
      data: { results: { text: "hi" } },
    });
    expect(touched.has("node-a")).toBe(true);
  });

  it("treats op:replace the same as op:add", () => {
    const touched = new Set<string>();

    applyStateDelta(
      [
        {
          op: "replace",
          path: "/nodes/node-a",
          value: {
            status: "success",
            output: { results: { text: "hi" } },
          },
        },
      ],
      "run-1",
      touched,
    );

    const state = useFlowStore.getState();
    expect(state.flowBuildStatus["node-a"]?.status).toBe(BuildStatus.BUILT);
    expect(state.flowPool["node-a"]).toHaveLength(1);
    expect(touched.has("node-a")).toBe(true);
  });

  it("ignores op:remove", () => {
    const touched = new Set<string>();

    applyStateDelta(
      [
        {
          op: "remove",
          path: "/nodes/node-a",
          value: { status: "success", output: {} },
        },
      ],
      "run-1",
      touched,
    );

    const state = useFlowStore.getState();
    expect(state.flowBuildStatus["node-a"]).toBeUndefined();
    expect(state.flowPool["node-a"]).toBeUndefined();
    expect(touched.size).toBe(0);
  });

  it("ignores nested paths beyond /nodes/<id>", () => {
    const touched = new Set<string>();

    applyStateDelta(
      [
        {
          op: "add",
          path: "/nodes/node-a/extra/path",
          value: { status: "success", output: {} },
        },
      ],
      "run-1",
      touched,
    );

    const state = useFlowStore.getState();
    expect(state.flowBuildStatus["node-a"]).toBeUndefined();
    expect(state.flowPool["node-a"]).toBeUndefined();
    expect(touched.size).toBe(0);
  });

  it("ignores ops with null value", () => {
    const touched = new Set<string>();

    applyStateDelta(
      [{ op: "add", path: "/nodes/node-a", value: null }],
      "run-1",
      touched,
    );

    const state = useFlowStore.getState();
    expect(state.flowBuildStatus["node-a"]).toBeUndefined();
    expect(state.flowPool["node-a"]).toBeUndefined();
    expect(touched.size).toBe(0);
  });

  it("ignores ops with non-object value", () => {
    const touched = new Set<string>();

    applyStateDelta(
      [{ op: "add", path: "/nodes/node-a", value: "string" }],
      "run-1",
      touched,
    );

    const state = useFlowStore.getState();
    expect(state.flowBuildStatus["node-a"]).toBeUndefined();
    expect(state.flowPool["node-a"]).toBeUndefined();
    expect(touched.size).toBe(0);
  });

  it("updates build status to BUILDING for running with null output and skips the flow pool", () => {
    const touched = new Set<string>();

    applyStateDelta(
      [
        {
          op: "add",
          path: "/nodes/node-a",
          value: { status: "running", output: null },
        },
      ],
      "run-1",
      touched,
    );

    const state = useFlowStore.getState();
    expect(state.flowBuildStatus["node-a"]?.status).toBe(BuildStatus.BUILDING);
    expect(state.flowPool["node-a"]).toBeUndefined();
    expect(touched.has("node-a")).toBe(true);
  });

  it("falls back to BuildStatus.BUILDING when the status is unknown", () => {
    const touched = new Set<string>();

    applyStateDelta(
      [
        {
          op: "add",
          path: "/nodes/node-a",
          value: { status: "unknown_status", output: null },
        },
      ],
      "run-1",
      touched,
    );

    const state = useFlowStore.getState();
    expect(state.flowBuildStatus["node-a"]?.status).toBe(BuildStatus.BUILDING);
    expect(touched.has("node-a")).toBe(true);
  });

  it("stamps the runId on each flow-pool entry", () => {
    const touched = new Set<string>();

    applyStateDelta(
      [
        {
          op: "add",
          path: "/nodes/node-a",
          value: { status: "success", output: { results: {} } },
        },
        {
          op: "add",
          path: "/nodes/node-b",
          value: { status: "error", output: { results: {} } },
        },
      ],
      "run-xyz",
      touched,
    );

    const state = useFlowStore.getState();
    expect(state.flowPool["node-a"][0].run_id).toBe("run-xyz");
    expect(state.flowPool["node-b"][0].run_id).toBe("run-xyz");
    // `valid` mirrors `status === "success"`.
    expect(state.flowPool["node-a"][0].valid).toBe(true);
    expect(state.flowPool["node-b"][0].valid).toBe(false);
  });

  describe("edge animation tracks node status", () => {
    /**
     * The v1 build path drove edge animation through onBuildStart/onBuildEnd.
     * Without an explicit toggle here the AG-UI path used to leave edges
     * static until ``finish()`` cleared them. Pin the contract: running flips
     * edges on, success/error flips them off (per-node, no global resets).
     */
    it("flips edges on when a node enters running status", () => {
      const touched = new Set<string>();
      const calls: Array<{ ids: string[]; running: boolean }> = [];
      const original = useFlowStore.getState().updateEdgesRunningByNodes;
      useFlowStore.setState({
        updateEdgesRunningByNodes: (ids: string[], running: boolean) => {
          calls.push({ ids, running });
        },
      });

      applyStateDelta(
        [
          {
            op: "add",
            path: "/nodes/node-a",
            value: { status: "running", output: null },
          },
        ],
        "run-1",
        touched,
      );

      useFlowStore.setState({ updateEdgesRunningByNodes: original });

      expect(calls).toEqual([{ ids: ["node-a"], running: true }]);
    });

    it("flips edges off when a node completes (success or error)", () => {
      const touched = new Set<string>();
      const calls: Array<{ ids: string[]; running: boolean }> = [];
      const original = useFlowStore.getState().updateEdgesRunningByNodes;
      useFlowStore.setState({
        updateEdgesRunningByNodes: (ids: string[], running: boolean) => {
          calls.push({ ids, running });
        },
      });

      applyStateDelta(
        [
          {
            op: "add",
            path: "/nodes/node-a",
            value: { status: "success", output: { results: {} } },
          },
          {
            op: "add",
            path: "/nodes/node-b",
            value: { status: "error", output: null },
          },
        ],
        "run-1",
        touched,
      );

      useFlowStore.setState({ updateEdgesRunningByNodes: original });

      expect(calls).toEqual([
        { ids: ["node-a"], running: false },
        { ids: ["node-b"], running: false },
      ]);
    });
  });
});
