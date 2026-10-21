import type { APIClassType } from "@/types/api";
import type { AllNodeType, EdgeType } from "@/types/flow";
import { cleanEdges, scapedJSONStringfy } from "@/utils/reactflowUtils";
import { processNodeAdvancedFields } from "../process-node-advanced-fields";

const edgeInto = (target: string, fieldName: string) => {
  const sourceHandle = {
    dataType: "Source",
    id: "Source-1",
    name: "out",
    output_types: ["Message"],
  };
  const targetHandle = {
    fieldName,
    id: target,
    inputTypes: ["Message"],
    type: "str",
  };
  return {
    id: `edge-${target}-${fieldName}`,
    source: "Source-1",
    target,
    sourceHandle: scapedJSONStringfy(sourceHandle),
    targetHandle: scapedJSONStringfy(targetHandle),
    data: { sourceHandle, targetHandle },
  } as unknown as EdgeType;
};

const genericNode = (id: string, node: Partial<APIClassType>) =>
  ({
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: { id, type: id.split("-")[0], node },
  }) as unknown as AllNodeType;

const sourceNode = genericNode("Source-1", {
  display_name: "Source",
  template: {},
  outputs: [
    {
      name: "out",
      display_name: "Out",
      types: ["Message"],
      selected: "Message",
    },
  ],
});

const textField = (show: boolean) => ({
  type: "str",
  show,
  display_name: "Text",
  input_types: ["Message"],
});

// What /custom_component returns for a Knowledge-like node: the registry declares
// search_query and column hidden (they belong to another mode).
const registryResponse = () =>
  ({
    display_name: "Knowledge",
    template: {
      mode: { type: "str", show: true, value: "Ingest" },
      search_query: textField(false),
      column: textField(false),
    },
    outputs: [],
  }) as unknown as APIClassType;

describe("processNodeAdvancedFields", () => {
  it("should keep a connected field shown when the registry declares it hidden", () => {
    const edges = [edgeInto("Knowledge-1", "search_query")];

    const updated = processNodeAdvancedFields(
      registryResponse(),
      edges,
      "Knowledge-1",
    );

    expect(updated.template.search_query.show).toBe(true);
    expect(updated.template.column.show).toBe(false);
    const result = cleanEdges(
      [sourceNode, genericNode("Knowledge-1", updated)],
      edges,
    );
    expect(result.edges).toHaveLength(1);
    expect(result.brokenEdges).toHaveLength(0);
  });

  it("should not show a field because another node's field of the same name is connected", () => {
    const edges = [edgeInto("Knowledge-2", "search_query")];

    const updated = processNodeAdvancedFields(
      registryResponse(),
      edges,
      "Knowledge-1",
    );

    expect(updated.template.search_query.show).toBe(false);
  });
});
