import { mergeFlowIntoCanvas } from "../merge-flow-into-canvas";

/**
 * FP1 — Pure helper that merges a proposal flow into existing canvas state.
 *
 * The current "Continue" semantic on a flow proposal is destructive: it
 * replaces nodes/edges via setNodes / setEdges. This helper produces the
 * additive alternative: it
 *   1. Reassigns IDs on proposal nodes that collide with canvas IDs.
 *   2. Rewrites proposal edges so source/target track the new IDs.
 *   3. Offsets proposal node positions so they don't overlap the
 *      existing canvas (placed to the right with a gap).
 *
 * The function is pure (no React, no @xyflow state) — easy to unit-test.
 */

type Node = { id: string; position: { x: number; y: number }; data?: unknown };
type Edge = {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
};

function n(id: string, x = 0, y = 0): Node {
  return { id, position: { x, y }, data: { type: id.split("-")[0] } };
}

function e(id: string, source: string, target: string): Edge {
  return { id, source, target };
}

describe("mergeFlowIntoCanvas", () => {
  describe("empty existing canvas", () => {
    it("should_return_proposal_nodes_unchanged_when_canvas_is_empty", () => {
      const proposal = {
        nodes: [n("ChatInput-a", 100, 100), n("Agent-b", 300, 100)],
        edges: [e("xy", "ChatInput-a", "Agent-b")],
      };

      const result = mergeFlowIntoCanvas([], [], proposal);

      // Empty canvas → no offset, no ID remap.
      expect(result.nodes).toEqual(proposal.nodes);
      expect(result.edges).toEqual(proposal.edges);
    });
  });

  describe("non-empty canvas — no ID collisions", () => {
    it("should_offset_proposal_nodes_to_the_right_of_existing_canvas", () => {
      const existing = [n("Existing-1", 0, 0), n("Existing-2", 200, 50)];
      const proposal = {
        nodes: [n("New-A", 0, 0), n("New-B", 200, 0)],
        edges: [e("e1", "New-A", "New-B")],
      };

      const result = mergeFlowIntoCanvas(existing, [], proposal);

      // Existing canvas right edge ≈ 200; proposal min_x = 0.
      // Offset = (200 - 0) + GAP ⇒ proposal nodes shift right by 200+GAP.
      const offsetA = result.nodes[2].position.x; // New-A
      const offsetB = result.nodes[3].position.x; // New-B
      expect(offsetA).toBeGreaterThan(200); // strictly right of existing
      // Relative spacing preserved within the proposal.
      expect(offsetB - offsetA).toBe(200);
    });

    it("should_concatenate_existing_then_proposal_nodes", () => {
      const existing = [n("Existing-1", 0, 0)];
      const proposal = {
        nodes: [n("New-A", 0, 0)],
        edges: [],
      };

      const result = mergeFlowIntoCanvas(existing, [], proposal);

      expect(result.nodes).toHaveLength(2);
      expect(result.nodes[0].id).toBe("Existing-1");
      expect(result.nodes[1].id).toBe("New-A");
    });

    it("should_concatenate_edges_when_no_collision", () => {
      const existing = [n("Existing-1", 0, 0)];
      const existingEdges = [e("ee1", "Existing-1", "Existing-1")];
      const proposal = {
        nodes: [n("New-A", 0, 0), n("New-B", 100, 0)],
        edges: [e("pe1", "New-A", "New-B")],
      };

      const result = mergeFlowIntoCanvas(existing, existingEdges, proposal);

      expect(result.edges).toHaveLength(2);
      expect(result.edges[0].id).toBe("ee1");
      // The proposal edge keeps its source/target intact (no collision).
      const newEdge = result.edges[1];
      expect(newEdge.source).toBe("New-A");
      expect(newEdge.target).toBe("New-B");
    });
  });

  describe("ID collisions", () => {
    it("should_reassign_proposal_node_ids_when_they_collide_with_existing", () => {
      const existing = [n("ChatInput-abc", 0, 0)];
      const proposal = {
        nodes: [n("ChatInput-abc", 0, 0), n("Agent-xyz", 200, 0)],
        edges: [e("e1", "ChatInput-abc", "Agent-xyz")],
      };

      const result = mergeFlowIntoCanvas(existing, [], proposal);

      // Existing kept as-is.
      expect(result.nodes[0].id).toBe("ChatInput-abc");
      // The colliding proposal node got a new id.
      const remappedChatInput = result.nodes[1];
      expect(remappedChatInput.id).not.toBe("ChatInput-abc");
      expect(remappedChatInput.id.startsWith("ChatInput-")).toBe(true);
      // The non-colliding one stays.
      expect(result.nodes[2].id).toBe("Agent-xyz");
    });

    it("should_rewrite_proposal_edges_to_use_remapped_ids", () => {
      const existing = [n("ChatInput-abc", 0, 0)];
      const proposal = {
        nodes: [n("ChatInput-abc", 0, 0), n("Agent-xyz", 200, 0)],
        edges: [e("e1", "ChatInput-abc", "Agent-xyz")],
      };

      const result = mergeFlowIntoCanvas(existing, [], proposal);

      const remappedChatInputId = result.nodes[1].id;
      const proposalEdge = result.edges[result.edges.length - 1];
      expect(proposalEdge.source).toBe(remappedChatInputId);
      expect(proposalEdge.target).toBe("Agent-xyz");
    });

    it("should_remap_edge_id_when_it_collides_with_existing_edge_id", () => {
      const existing = [n("E1", 0, 0)];
      const existingEdges = [e("shared-edge", "E1", "E1")];
      const proposal = {
        nodes: [n("New-A", 0, 0), n("New-B", 100, 0)],
        edges: [e("shared-edge", "New-A", "New-B")],
      };

      const result = mergeFlowIntoCanvas(existing, existingEdges, proposal);

      expect(result.edges).toHaveLength(2);
      const newEdgeId = result.edges[1].id;
      expect(newEdgeId).not.toBe("shared-edge");
    });

    it("should_remap_multiple_colliding_nodes_with_unique_ids_each", () => {
      const existing = [n("ChatInput-x", 0, 0), n("Agent-x", 100, 0)];
      const proposal = {
        nodes: [
          n("ChatInput-x", 0, 0),
          n("Agent-x", 100, 0),
          n("ChatOutput-z", 200, 0),
        ],
        edges: [
          e("e1", "ChatInput-x", "Agent-x"),
          e("e2", "Agent-x", "ChatOutput-z"),
        ],
      };

      const result = mergeFlowIntoCanvas(existing, [], proposal);

      const newIds = result.nodes.slice(2).map((nn) => nn.id);
      // No id from the proposal subset collides with the existing canvas.
      const existingIds = new Set(["ChatInput-x", "Agent-x"]);
      newIds.forEach((id) => expect(existingIds.has(id)).toBe(false));
      // And the proposal's internal references hold up.
      const proposalEdges = result.edges.slice(0); // all edges; existing had none
      const remappedChatInput = newIds[0];
      const remappedAgent = newIds[1];
      const chatOutput = newIds[2];
      expect(proposalEdges[0].source).toBe(remappedChatInput);
      expect(proposalEdges[0].target).toBe(remappedAgent);
      expect(proposalEdges[1].source).toBe(remappedAgent);
      expect(proposalEdges[1].target).toBe(chatOutput);
    });
  });

  describe("idempotency / determinism", () => {
    it("should_produce_unique_ids_across_two_consecutive_merges", () => {
      // Two clicks of "Add to canvas" with the SAME proposal must not
      // produce id collisions on the second click.
      const proposal = {
        nodes: [n("ChatInput-a", 0, 0), n("Agent-b", 100, 0)],
        edges: [e("e1", "ChatInput-a", "Agent-b")],
      };

      const first = mergeFlowIntoCanvas([], [], proposal);
      const second = mergeFlowIntoCanvas(first.nodes, first.edges, proposal);

      const allIds = [
        ...first.nodes.map((nn) => nn.id),
        ...second.nodes.slice(first.nodes.length).map((nn) => nn.id),
      ];
      expect(new Set(allIds).size).toBe(allIds.length);
    });
  });
});
