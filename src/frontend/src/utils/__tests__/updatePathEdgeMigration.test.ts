/**
 * Reproduction for LE-1929: updating an outdated saved flow must not drop edges whose
 * output type was renamed (DataFrame -> Table, #11554).
 *
 * Flow B (Memory Chatbot, legacy) has a Memory."dataframe" output that was typed ["DataFrame"]
 * when saved but is ["Table"] in the current library. When the user clicks "Update All", the
 * node definition is swapped to the current one (Table) while the edge still stores the old
 * DataFrame handle. cleanEdges must migrate + keep the edge, not drop it.
 */

import { cleanEdges, scapedJSONStringfy } from "../reactflowUtils";

const stringify = (obj: object): string => scapedJSONStringfy(obj);

describe("LE-1929 update-path edge migration (DataFrame -> Table)", () => {
  it("keeps the Memory->TypeConverter edge after the Memory output migrates to Table", () => {
    // Memory node AFTER "Update All": dataframe output is now typed Table.
    const memoryNode: any = {
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
    };

    // TypeConverter node AFTER update: input_data accepts the migrated types.
    const typeConverterNode: any = {
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
            },
          },
          outputs: [],
        },
      },
    };

    // Edge as SAVED in the legacy flow: source handle still says DataFrame.
    const sourceHandle = stringify({
      dataType: "Memory",
      id: "Memory-8X8Cq",
      name: "dataframe",
      output_types: ["DataFrame"],
    });
    const targetHandle = stringify({
      fieldName: "input_data",
      id: "TypeConverterComponent-koSIz",
      inputTypes: ["Message", "Data", "DataFrame"],
      type: "other",
    });

    const edge: any = {
      id:
        "xy-edge__Memory-8X8Cq" +
        sourceHandle +
        "-TypeConverter" +
        targetHandle,
      source: "Memory-8X8Cq",
      target: "TypeConverterComponent-koSIz",
      sourceHandle,
      targetHandle,
      data: {
        sourceHandle: {
          dataType: "Memory",
          id: "Memory-8X8Cq",
          name: "dataframe",
          output_types: ["DataFrame"],
        },
        targetHandle: {
          fieldName: "input_data",
          id: "TypeConverterComponent-koSIz",
          inputTypes: ["Message", "Data", "DataFrame"],
          type: "other",
        },
      },
    };

    const result = cleanEdges([memoryNode, typeConverterNode], [edge]);

    expect(result.brokenEdges.length).toBe(0);
    expect(result.edges.length).toBe(1);
    // The kept edge must have its source handle rewritten to the migrated Table type.
    expect(result.edges[0].sourceHandle).toContain("Table");
  });
});
