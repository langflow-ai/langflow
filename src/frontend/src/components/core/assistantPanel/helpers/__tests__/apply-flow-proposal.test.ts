/**
 * Placement-policy enforcement on the proposal-apply path.
 *
 * A proposal is LLM-generated and can violate canvas placement policy
 * (e.g. two ChatInputs — a singleton). The apply path must (a) enforce
 * the policy in BOTH modes ("add" already filtered; "replace" bypassed
 * the filter entirely) and (b) surface the dropped nodes to the user
 * instead of silently diverging from what the proposal card advertised.
 *
 * Deterministic repro from the review finding: a proposal holding two
 * ChatInputs yields [{type:"ChatInput",reason:"singleton"}] with no
 * model involved.
 */

import type { PendingFlowProposal } from "../../assistant-panel.types";
import { applyFlowProposalToCanvas } from "../apply-flow-proposal";

type UpdateNodeInternalsFn = Parameters<typeof applyFlowProposalToCanvas>[2];
const asInternals = (v: unknown): UpdateNodeInternalsFn =>
  v as UpdateNodeInternalsFn;

const setNodesAndEdges = jest.fn();
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      nodes: [],
      edges: [],
      setNodesAndEdges,
      reactFlowInstance: { fitView: jest.fn() },
    }),
  },
}));

const setNoticeData = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: { getState: () => ({ setNoticeData }) },
}));

jest.mock("@/i18n", () => ({
  __esModule: true,
  default: { t: (key: string) => key },
}));

const node = (id: string, type: string) => ({
  id,
  position: { x: 0, y: 0 },
  data: { type },
});
const edge = (id: string, source: string, target: string) => ({
  id,
  source,
  target,
});

/** The exact shape from the finding: 5 nodes, 4 edges, second ChatInput violates singleton. */
const twoChatInputProposal = (): PendingFlowProposal => ({
  flow: {
    data: {
      nodes: [
        node("ChatInput-a", "ChatInput"),
        node("ChatInput-b", "ChatInput"),
        node("ConditionalRouter-c", "ConditionalRouter"),
        node("ChatOutput-d", "ChatOutput"),
        node("ChatOutput-e", "ChatOutput"),
      ],
      edges: [
        edge("e1", "ChatInput-a", "ConditionalRouter-c"),
        edge("e2", "ChatInput-b", "ConditionalRouter-c"),
        edge("e3", "ConditionalRouter-c", "ChatOutput-d"),
        edge("e4", "ConditionalRouter-c", "ChatOutput-e"),
      ],
    },
  },
  nodeCount: 5,
  edgeCount: 4,
});

const cleanProposal = (): PendingFlowProposal => ({
  flow: {
    data: {
      nodes: [
        node("ChatInput-a", "ChatInput"),
        node("ChatOutput-b", "ChatOutput"),
      ],
      edges: [edge("e1", "ChatInput-a", "ChatOutput-b")],
    },
  },
  nodeCount: 2,
  edgeCount: 1,
});

const appliedIds = () => {
  const [nodes, edges] = setNodesAndEdges.mock.calls[0] as [
    Array<{ id: string }>,
    Array<{ id: string }>,
  ];
  return {
    nodeIds: nodes.map((n) => n.id),
    edgeIds: edges.map((e) => e.id),
  };
};

beforeEach(() => {
  setNodesAndEdges.mockClear();
  setNoticeData.mockClear();
});

describe("applyFlowProposalToCanvas — placement policy", () => {
  describe("add mode", () => {
    it("should_surface_a_singleton_notice_when_a_proposed_node_is_dropped", () => {
      applyFlowProposalToCanvas(
        twoChatInputProposal(),
        "add",
        asInternals(jest.fn()),
      );

      expect(setNoticeData).toHaveBeenCalledTimes(1);
      expect(setNoticeData).toHaveBeenCalledWith({
        title: "assistant.duplicateComponentsNotAdded",
      });
    });

    it("should_drop_the_violating_node_and_its_edges", () => {
      applyFlowProposalToCanvas(
        twoChatInputProposal(),
        "add",
        asInternals(jest.fn()),
      );

      const { nodeIds, edgeIds } = appliedIds();
      expect(nodeIds).toEqual([
        "ChatInput-a",
        "ConditionalRouter-c",
        "ChatOutput-d",
        "ChatOutput-e",
      ]);
      expect(edgeIds).toEqual(["e1", "e3", "e4"]);
    });

    it("should_not_notify_when_the_proposal_has_no_violations", () => {
      applyFlowProposalToCanvas(cleanProposal(), "add", asInternals(jest.fn()));

      expect(setNoticeData).not.toHaveBeenCalled();
      expect(appliedIds().nodeIds).toEqual(["ChatInput-a", "ChatOutput-b"]);
    });
  });

  describe("replace mode", () => {
    it("should_enforce_the_placement_policy_instead_of_bypassing_it", () => {
      applyFlowProposalToCanvas(
        twoChatInputProposal(),
        "replace",
        asInternals(jest.fn()),
      );

      const { nodeIds, edgeIds } = appliedIds();
      expect(nodeIds).toEqual([
        "ChatInput-a",
        "ConditionalRouter-c",
        "ChatOutput-d",
        "ChatOutput-e",
      ]);
      expect(edgeIds).toEqual(["e1", "e3", "e4"]);
      expect(setNoticeData).toHaveBeenCalledWith({
        title: "assistant.duplicateComponentsNotAdded",
      });
    });

    it("should_not_mutate_the_stored_proposal_when_filtering", () => {
      const proposal = twoChatInputProposal();

      applyFlowProposalToCanvas(proposal, "replace", asInternals(jest.fn()));

      // The proposal stays re-appliable from the pending card; filtering
      // must work on a copy, not gut the stored flow.
      const data = proposal.flow.data as { nodes: unknown[]; edges: unknown[] };
      expect(data.nodes).toHaveLength(5);
      expect(data.edges).toHaveLength(4);
    });

    it("should_not_notify_when_the_proposal_has_no_violations", () => {
      applyFlowProposalToCanvas(
        cleanProposal(),
        "replace",
        asInternals(jest.fn()),
      );

      expect(setNoticeData).not.toHaveBeenCalled();
      expect(appliedIds().nodeIds).toEqual(["ChatInput-a", "ChatOutput-b"]);
    });
  });
});
