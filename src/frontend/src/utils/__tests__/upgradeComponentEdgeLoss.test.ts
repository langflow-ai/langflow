/**
 * Updating a migrated component after a 1.11.x -> 1.12 upgrade must not drop the
 * component's connections.
 *
 * The fixture is the shipped Vector Store RAG flow saved by 1.11.6, paired with the
 * real /api/v1/custom_component responses a 1.12 server returns for it, so the test
 * exercises the exact node shapes the upgrade produces rather than hand-written ones.
 *
 * Two independent mechanisms dropped an edge:
 *   - Knowledge came back with its saved mode=Retrieve but ingest-mode `show` flags,
 *     so search_query was hidden and filterHiddenFieldsEdges deleted its edge with no
 *     entry in brokenEdges — the loss reached the user with no feedback at all.
 *   - Updating Prompt rewrites data.type to the component's current name
 *     ("Prompt" -> "Prompt Template"), leaving every outgoing edge holding the old
 *     dataType, which handlesMatch rejected outright.
 */

import { cloneDeep } from "lodash";
import { processNodeAdvancedFields } from "@/CustomNodes/helpers/process-node-advanced-fields";
import type { APIClassType } from "../../types/api";
import type { AllNodeType, EdgeType, GenericNodeType } from "../../types/flow";
import {
  cleanEdges,
  filterHiddenFieldsEdges,
  scapeJSONParse,
} from "../reactflowUtils";
import fixture from "./upgradeComponentEdgeLoss.fixture.json";

type UpdateResponse = { data: APIClassType; type?: string };

const updates = fixture.updated as unknown as Record<string, UpdateResponse>;

function genericNode(nodes: AllNodeType[], id: string): GenericNodeType {
  const node = nodes.find((candidate) => candidate.id === id);
  if (!node || node.type !== "genericNode") {
    throw new Error(`Fixture is missing generic node ${id}`);
  }
  return node;
}

function applyComponentUpdates(): { nodes: AllNodeType[]; edges: EdgeType[] } {
  const nodes = cloneDeep(fixture.nodes) as unknown as AllNodeType[];
  const edges = cloneDeep(fixture.edges) as unknown as EdgeType[];

  for (const [nodeId, response] of Object.entries(updates)) {
    const node = genericNode(nodes, nodeId);
    node.data.node = processNodeAdvancedFields(response.data, edges, nodeId);
    if (response.type) node.data.type = response.type;
  }

  return { nodes, edges };
}

const describeEdge = (edge: EdgeType) =>
  `${edge.source} -> ${edge.target} [${edge.data?.targetHandle?.fieldName}]`;

describe("component update after a 1.11.x -> 1.12 upgrade", () => {
  it("should keep every connection when the updated components are applied", () => {
    const { nodes, edges } = applyComponentUpdates();

    const result = cleanEdges(nodes, edges);

    expect(result.edges.map(describeEdge)).toEqual(edges.map(describeEdge));
    expect(result.brokenEdges).toHaveLength(0);
  });

  it("should keep the edge feeding a retrieve-mode field visible on Knowledge", () => {
    const { nodes, edges } = applyComponentUpdates();
    const template = genericNode(nodes, "Knowledge-XkWM6").data.node!.template;

    expect(template.mode.value).toBe("Retrieve");
    expect(template.search_query.show).toBe(true);

    const kept = cleanEdges(nodes, edges).edges;
    expect(
      kept.some(
        (edge) =>
          edge.target === "Knowledge-XkWM6" &&
          edge.data?.targetHandle?.fieldName === "search_query",
      ),
    ).toBe(true);
  });

  it("should migrate the stored dataType when a source component was renamed", () => {
    const { nodes, edges } = applyComponentUpdates();

    expect(genericNode(nodes, "Prompt-cxV2s").data.type).toBe(
      "Prompt Template",
    );
    const storedHandle = edges.find((edge) => edge.source === "Prompt-cxV2s")!
      .sourceHandle!;
    expect(scapeJSONParse(storedHandle).dataType).toBe("Prompt");

    const migrated = cleanEdges(nodes, edges).edges.find(
      (edge) => edge.source === "Prompt-cxV2s",
    );

    expect(migrated).toBeDefined();
    expect(scapeJSONParse(migrated!.sourceHandle!).dataType).toBe(
      "Prompt Template",
    );
    expect(migrated!.data?.sourceHandle?.dataType).toBe("Prompt Template");
  });

  it("should still drop and report an edge whose source output disappeared", () => {
    const { nodes, edges } = applyComponentUpdates();
    genericNode(nodes, "Prompt-cxV2s").data.node!.outputs = [];

    const result = cleanEdges(nodes, edges);

    expect(result.edges.some((edge) => edge.source === "Prompt-cxV2s")).toBe(
      false,
    );
    expect(result.brokenEdges.length).toBeGreaterThan(0);
  });
});

describe("filterHiddenFieldsEdges", () => {
  const targetNode = {
    id: "Knowledge-1",
    type: "genericNode",
    data: {
      id: "Knowledge-1",
      type: "Knowledge",
      node: {
        display_name: "Knowledge",
        template: {
          search_query: { show: false, display_name: "Search Query" },
        },
      },
    },
  } as unknown as AllNodeType;

  const edge = {
    id: "edge-1",
    source: "ChatInput-1",
    target: "Knowledge-1",
    data: { targetHandle: { fieldName: "search_query" } },
  } as unknown as EdgeType;

  it("should report the removal instead of dropping the edge silently", () => {
    const removed: EdgeType[] = [];

    const result = filterHiddenFieldsEdges(edge, [edge], targetNode, (e) =>
      removed.push(e),
    );

    expect(result).toHaveLength(0);
    expect(removed).toEqual([edge]);
  });

  it("should not report anything when the edge was already gone", () => {
    const removed: EdgeType[] = [];

    const result = filterHiddenFieldsEdges(edge, [], targetNode, (e) =>
      removed.push(e),
    );

    expect(result).toHaveLength(0);
    expect(removed).toHaveLength(0);
  });
});
