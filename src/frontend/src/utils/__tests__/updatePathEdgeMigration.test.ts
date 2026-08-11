/**
 * Reproduction for LE-1929: updating an outdated saved flow must not drop edges whose
 * output type was renamed (DataFrame -> Table, #11554).
 *
 * Flow B (Memory Chatbot, legacy) has a Memory."dataframe" output that was typed ["DataFrame"]
 * when saved but is ["Table"] in the current library. When the user clicks "Update All", the
 * node definition is swapped to the current one (Table) while the edge still stores the old
 * DataFrame handle. cleanEdges must migrate + keep the edge, not drop it.
 *
 * Also covers the inverse guarantee: once the target migration rewrites the retained edge's id,
 * later removal paths (invalid source handle, hidden target field) must still find the edge —
 * filtering by the original id would silently keep a broken edge in the graph.
 */

import type { AllNodeType, EdgeType } from "../../types/flow";
import { cleanEdges, scapedJSONStringfy } from "../reactflowUtils";

const stringify = (obj: object): string => scapedJSONStringfy(obj);

function buildMemoryNode(): AllNodeType {
  // Memory node AFTER "Update All": dataframe output is now typed Table.
  return {
    id: "Memory-8X8Cq",
    type: "genericNode",
    data: {
      id: "Memory-8X8Cq",
      type: "Memory",
      selected_output: "dataframe",
      node: {
        display_name: "Message History",
        template: {},
        outputs: [
          {
            name: "dataframe",
            display_name: "Table",
            types: ["Table"],
            selected: "Table",
          },
        ],
      },
    },
  } as unknown as AllNodeType;
}

function buildTypeConverterNode({
  show = true,
}: {
  show?: boolean;
} = {}): AllNodeType {
  // TypeConverter node AFTER update: input_data accepts the migrated types.
  return {
    id: "TypeConverterComponent-koSIz",
    type: "genericNode",
    data: {
      id: "TypeConverterComponent-koSIz",
      type: "TypeConverterComponent",
      node: {
        display_name: "Type Convert",
        template: {
          input_data: {
            type: "other",
            input_types: ["Message", "Data", "JSON", "DataFrame", "Table"],
            display_name: "Input",
            show,
          },
        },
        outputs: [],
      },
    },
  } as unknown as AllNodeType;
}

function buildLegacyEdge({
  sourceOutputTypes = ["DataFrame"],
}: {
  sourceOutputTypes?: string[];
} = {}): EdgeType {
  // Edge as SAVED in the legacy flow: handles still reference pre-migration types.
  const sourceHandle = stringify({
    dataType: "Memory",
    id: "Memory-8X8Cq",
    name: "dataframe",
    output_types: sourceOutputTypes,
  });
  const targetHandle = stringify({
    fieldName: "input_data",
    id: "TypeConverterComponent-koSIz",
    inputTypes: ["Message", "Data", "DataFrame"],
    type: "other",
  });

  return {
    id:
      "xy-edge__Memory-8X8Cq" + sourceHandle + "-TypeConverter" + targetHandle,
    source: "Memory-8X8Cq",
    target: "TypeConverterComponent-koSIz",
    sourceHandle,
    targetHandle,
    data: {
      sourceHandle: {
        dataType: "Memory",
        id: "Memory-8X8Cq",
        name: "dataframe",
        output_types: sourceOutputTypes,
      },
      targetHandle: {
        fieldName: "input_data",
        id: "TypeConverterComponent-koSIz",
        inputTypes: ["Message", "Data", "DataFrame"],
        type: "other",
      },
    },
  } as unknown as EdgeType;
}

describe("LE-1929 update-path edge migration (DataFrame -> Table)", () => {
  it("keeps the Memory->TypeConverter edge after the Memory output migrates to Table", () => {
    const result = cleanEdges(
      [buildMemoryNode(), buildTypeConverterNode()],
      [buildLegacyEdge()],
    );

    expect(result.brokenEdges.length).toBe(0);
    expect(result.edges.length).toBe(1);
    // The kept edge must have its source handle rewritten to the migrated Table type.
    expect(result.edges[0].sourceHandle).toContain("Table");
  });

  it("removes an edge whose source is invalid even after the target migration rewrote its id", () => {
    // Source handle stores a type that no longer matches the output and has no
    // migration path — the edge is broken and must NOT survive cleanup just
    // because the target block rewrote the retained edge's id first.
    const result = cleanEdges(
      [buildMemoryNode(), buildTypeConverterNode()],
      [buildLegacyEdge({ sourceOutputTypes: ["Vector"] })],
    );

    expect(result.brokenEdges.length).toBe(1);
    expect(result.edges.length).toBe(0);
  });

  it("removes an edge into a hidden field even after the target migration rewrote its id", () => {
    const result = cleanEdges(
      [buildMemoryNode(), buildTypeConverterNode({ show: false })],
      [buildLegacyEdge()],
    );

    expect(result.edges.length).toBe(0);
  });
});
