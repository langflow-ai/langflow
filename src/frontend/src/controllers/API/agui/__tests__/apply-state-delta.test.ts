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

  describe("build_duration stamping on output-node success", () => {
    // The AG-UI translator drops the backend's per-vertex duration, so the
    // bridge has to derive ``build_duration`` client-side and stamp it onto
    // the last bot message. These pin the gates (output-type only, success
    // only, buildStartTime required) so a regression would surface here
    // instead of in a playwright run.

    const OUTPUT_NODE_ID = "ChatOutput-XYZ";
    const NON_OUTPUT_NODE_ID = "LanguageModelComponent-ABC";

    const seedFlow = (nodes: Array<{ id: string; type: string }>) => {
      useFlowStore.setState({
        nodes: nodes.map((n) => ({
          id: n.id,
          // Only ``data.type`` matters here; the rest of the node shape is
          // surplus for the helper but required by AllNodeType typing.
          data: { type: n.type },
        })) as unknown as ReturnType<typeof useFlowStore.getState>["nodes"],
      });
    };

    const seedBotMessage = (msg: {
      id: string;
      properties?: Record<string, unknown>;
    }) => {
      // Stamping reads ``useMessagesStore`` when React Query returns nothing
      // (the shareable-playground / IOModal path), so seed it there.
      const { useMessagesStore } = require("@/stores/messagesStore");
      useMessagesStore.setState({
        messages: [
          {
            id: msg.id,
            sender: "Machine",
            sender_name: "AI",
            session_id: "s1",
            flow_id: "f1",
            text: "Hi",
            files: [],
            timestamp: "2026-05-28T00:00:00Z",
            properties: msg.properties ?? {},
            content_blocks: [],
            category: "message",
          },
        ],
      });
    };

    beforeEach(() => {
      const { useMessagesStore } = require("@/stores/messagesStore");
      const { queryClient } = require("@/contexts");
      useMessagesStore.setState({ messages: [] });
      useFlowStore.setState({ nodes: [], buildStartTime: null });
      // Clear the React Query messages cache so the scoping test below
      // doesn't leak seeded sessions into the Zustand-fallback tests.
      queryClient.clear();
    });

    it("stamps build_duration on the last bot message when an output node finishes successfully", () => {
      seedFlow([{ id: OUTPUT_NODE_ID, type: "ChatOutput" }]);
      seedBotMessage({ id: "m1" });
      useFlowStore.setState({ buildStartTime: Date.now() - 1500 });

      applyStateDelta(
        [
          {
            op: "add",
            path: `/nodes/${OUTPUT_NODE_ID}`,
            value: { status: "success", output: { results: {} } },
          },
        ],
        "run-1",
        new Set<string>(),
      );

      const { useMessagesStore } = require("@/stores/messagesStore");
      const stamped = useMessagesStore.getState().messages[0];
      expect(stamped.properties.build_duration).toBeGreaterThanOrEqual(1500);
      // Resets so the next segment is measured fresh.
      expect(useFlowStore.getState().buildStartTime).not.toBeNull();
    });

    it("does not stamp when the finishing node is not an output type", () => {
      seedFlow([{ id: NON_OUTPUT_NODE_ID, type: "LanguageModelComponent" }]);
      seedBotMessage({ id: "m1" });
      useFlowStore.setState({ buildStartTime: Date.now() - 500 });

      applyStateDelta(
        [
          {
            op: "add",
            path: `/nodes/${NON_OUTPUT_NODE_ID}`,
            value: { status: "success", output: { results: {} } },
          },
        ],
        "run-1",
        new Set<string>(),
      );

      const { useMessagesStore } = require("@/stores/messagesStore");
      const msg = useMessagesStore.getState().messages[0];
      expect(msg.properties.build_duration).toBeUndefined();
    });

    it("does not stamp when buildStartTime is missing", () => {
      seedFlow([{ id: OUTPUT_NODE_ID, type: "ChatOutput" }]);
      seedBotMessage({ id: "m1" });
      useFlowStore.setState({ buildStartTime: null });

      applyStateDelta(
        [
          {
            op: "add",
            path: `/nodes/${OUTPUT_NODE_ID}`,
            value: { status: "success", output: { results: {} } },
          },
        ],
        "run-1",
        new Set<string>(),
      );

      const { useMessagesStore } = require("@/stores/messagesStore");
      const msg = useMessagesStore.getState().messages[0];
      expect(msg.properties.build_duration).toBeUndefined();
    });

    it("does not overwrite a build_duration already on the message (nested-segment guard)", () => {
      seedFlow([{ id: OUTPUT_NODE_ID, type: "ChatOutput" }]);
      seedBotMessage({ id: "m1", properties: { build_duration: 999 } });
      useFlowStore.setState({ buildStartTime: Date.now() - 5000 });

      applyStateDelta(
        [
          {
            op: "add",
            path: `/nodes/${OUTPUT_NODE_ID}`,
            value: { status: "success", output: { results: {} } },
          },
        ],
        "run-1",
        new Set<string>(),
      );

      const { useMessagesStore } = require("@/stores/messagesStore");
      const msg = useMessagesStore.getState().messages[0];
      expect(msg.properties.build_duration).toBe(999);
    });

    it("scopes the stamp to the running session, not another session's cache", () => {
      // D1 regression: the bot-message lookup must be scoped to the running
      // flow/session. The unscoped form walked every messages cache and could
      // stamp build_duration onto a bot message from a different session the
      // user had open in the same tab.
      const { queryClient } = require("@/contexts");
      const MESSAGES_QUERY_KEY = "useGetMessagesQuery";
      const botMsg = (id: string) => ({
        id,
        sender: "Machine",
        sender_name: "AI",
        text: "hi",
        files: [],
        timestamp: "2026-05-28T00:00:00Z",
        properties: {} as Record<string, unknown>,
        content_blocks: [],
        category: "message",
      });
      const otherKey = [
        MESSAGES_QUERY_KEY,
        { id: "f1", session_id: "other-session" },
      ];
      const runningKey = [
        MESSAGES_QUERY_KEY,
        { id: "f1", session_id: "running-session" },
      ];
      queryClient.setQueryData(otherKey, [botMsg("other-msg")]);
      queryClient.setQueryData(runningKey, [botMsg("running-msg")]);

      seedFlow([{ id: OUTPUT_NODE_ID, type: "ChatOutput" }]);
      useFlowStore.setState({ buildStartTime: Date.now() - 1500 });

      applyStateDelta(
        [
          {
            op: "add",
            path: `/nodes/${OUTPUT_NODE_ID}`,
            value: { status: "success", output: { results: {} } },
          },
        ],
        "run-1",
        new Set<string>(),
        "f1",
        "running-session",
      );

      const running = queryClient.getQueryData(runningKey) as Array<{
        properties: { build_duration?: number };
      }>;
      const other = queryClient.getQueryData(otherKey) as Array<{
        properties: { build_duration?: number };
      }>;
      expect(running[0].properties.build_duration).toBeGreaterThanOrEqual(1500);
      expect(other[0].properties.build_duration).toBeUndefined();
    });
  });
});
