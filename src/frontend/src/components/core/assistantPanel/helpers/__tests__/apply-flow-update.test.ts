/**
 * I6 — apply-flow-update must validate untrusted SSE payloads before
 * mutating the live canvas. The event arrives from the assistant SSE
 * stream (LLM-driven, potentially malformed); a blanket cast lets garbage
 * land in `useFlowStore`, corrupting the user's canvas with no signal.
 *
 * These tests cover the malformed-payload paths the reviewer flagged:
 * the dispatcher must drop the event (no store mutation) rather than
 * cast-and-write.
 */

import type { AgenticFlowUpdateEvent } from "@/controllers/API/queries/agentic";
import { applyFlowUpdate } from "../apply-flow-update";

type UpdateNodeInternalsFn = Parameters<typeof applyFlowUpdate>[1];
const asEvent = (v: unknown): AgenticFlowUpdateEvent =>
  v as AgenticFlowUpdateEvent;
const asInternals = (v: unknown): UpdateNodeInternalsFn =>
  v as UpdateNodeInternalsFn;

// Mock the canvas store BEFORE the helper imports it.
const setNodes = jest.fn();
const setEdges = jest.fn();
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      setNodes,
      setEdges,
      reactFlowInstance: { fitView: jest.fn() },
    }),
  },
}));

const noopUpdateNodeInternals = jest.fn();

beforeEach(() => {
  setNodes.mockClear();
  setEdges.mockClear();
  noopUpdateNodeInternals.mockClear();
});

describe("applyFlowUpdate — boundary validation", () => {
  describe("set_flow", () => {
    it("should_skip_canvas_replace_when_flow_data_nodes_is_not_an_array", () => {
      const malformed = {
        event: "flow_update",
        action: "set_flow",
        // nodes must be an array; the assistant sometimes hallucinates a
        // string or an object literal here.
        flow: { data: { nodes: "<corrupted>", edges: [] } },
      };

      applyFlowUpdate(asEvent(malformed), asInternals(noopUpdateNodeInternals));

      expect(setNodes).not.toHaveBeenCalled();
      expect(setEdges).not.toHaveBeenCalled();
    });

    it("should_apply_canvas_replace_when_payload_is_well_formed", () => {
      const valid = {
        event: "flow_update",
        action: "set_flow",
        flow: {
          data: {
            nodes: [{ id: "ChatInput-1" }],
            edges: [],
          },
        },
      };

      applyFlowUpdate(asEvent(valid), asInternals(noopUpdateNodeInternals));

      expect(setNodes).toHaveBeenCalledTimes(1);
      expect(setEdges).toHaveBeenCalledTimes(1);
    });
  });

  describe("add_component", () => {
    it.each([
      ["null node", null],
      ["string node", "Agent-1"],
      ["number node", 42],
      ["node missing id", { data: {} }],
    ])("should_skip_add_when_payload_is_%s", (_label, badNode) => {
      const malformed = {
        event: "flow_update",
        action: "add_component",
        node: badNode,
      };

      applyFlowUpdate(asEvent(malformed), asInternals(noopUpdateNodeInternals));

      expect(setNodes).not.toHaveBeenCalled();
    });

    it("should_apply_add_when_node_is_a_valid_object_with_id", () => {
      const valid = {
        event: "flow_update",
        action: "add_component",
        node: { id: "Agent-1", data: {} },
      };

      applyFlowUpdate(asEvent(valid), asInternals(noopUpdateNodeInternals));

      expect(setNodes).toHaveBeenCalledTimes(1);
    });
  });

  describe("connect", () => {
    it("should_skip_when_edge_lacks_source_or_target", () => {
      const malformed = {
        event: "flow_update",
        action: "connect",
        edge: { id: "edge-1", source: "A" }, // target missing
      };

      applyFlowUpdate(asEvent(malformed), asInternals(noopUpdateNodeInternals));

      expect(setEdges).not.toHaveBeenCalled();
    });
  });
});
