import type { OutputFieldType } from "@/types/api";
import type { AllNodeType, EdgeType } from "@/types/flow";
import { cleanEdges, scapedJSONStringfy } from "@/utils/reactflowUtils";
import { updateHiddenOutputs } from "../update-hidden-outputs";

const sourceHandle = {
  dataType: "Source",
  id: "Source-1",
  name: "out",
  output_types: ["Message"],
};
const targetHandle = {
  fieldName: "input_value",
  id: "Target-1",
  inputTypes: ["Message", "Tool"],
  type: "str",
};

const edge = {
  id: "edge-1",
  source: "Source-1",
  target: "Target-1",
  sourceHandle: scapedJSONStringfy(sourceHandle),
  targetHandle: scapedJSONStringfy(targetHandle),
  data: { sourceHandle, targetHandle },
} as unknown as EdgeType;

const genericNode = (
  id: string,
  type: string,
  template: Record<string, unknown>,
  outputs: OutputFieldType[],
) =>
  ({
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: { id, type, node: { display_name: type, template, outputs } },
  }) as unknown as AllNodeType;

const targetNode = genericNode(
  "Target-1",
  "Target",
  {
    input_value: {
      type: "str",
      show: true,
      display_name: "Input",
      input_types: ["Message", "Tool"],
    },
  },
  [],
);

// The node as useUpdateNodeCode leaves it: the server's outputs, merged with the saved ones.
const updatedSourceNode = (savedOutput: OutputFieldType, types: string[]) =>
  genericNode(
    "Source-1",
    "Source",
    {},
    updateHiddenOutputs(
      [savedOutput],
      [{ name: "out", display_name: "Out", types, selected: types[0] }],
    ),
  );

describe("updateHiddenOutputs", () => {
  it("should keep the saved selected type and its edge when the output types are reordered", () => {
    const saved: OutputFieldType = {
      name: "out",
      display_name: "Out",
      types: ["Message", "Tool"],
      selected: "Message",
    };
    const sourceNode = updatedSourceNode(saved, ["Tool", "Message"]);

    const result = cleanEdges([sourceNode, targetNode], [edge]);
    expect(result.edges).toHaveLength(1);
    expect(result.brokenEdges).toHaveLength(0);
    expect(sourceNode.data.node!.outputs![0].selected).toBe("Message");
  });

  it("should take the new selected type when the output no longer offers the saved one", () => {
    const saved: OutputFieldType = {
      name: "out",
      display_name: "Out",
      types: ["Message", "Tool"],
      selected: "Message",
    };
    const sourceNode = updatedSourceNode(saved, ["Tool"]);

    expect(sourceNode.data.node!.outputs![0].selected).toBe("Tool");
  });

  it.each([
    ["Data", "JSON"],
    ["DataFrame", "Table"],
  ])(
    "should keep a saved %s selection as %s, its new name, and its edge",
    (savedType, newType) => {
      const typedSourceHandle = { ...sourceHandle, output_types: [savedType] };
      const typedTargetHandle = { ...targetHandle, inputTypes: [newType] };
      const typedEdge = {
        ...edge,
        sourceHandle: scapedJSONStringfy(typedSourceHandle),
        targetHandle: scapedJSONStringfy(typedTargetHandle),
        data: {
          sourceHandle: typedSourceHandle,
          targetHandle: typedTargetHandle,
        },
      } as unknown as EdgeType;
      const typedTargetNode = genericNode(
        "Target-1",
        "Target",
        {
          input_value: {
            type: "str",
            show: true,
            display_name: "Input",
            input_types: [newType],
          },
        },
        [],
      );
      const saved: OutputFieldType = {
        name: "out",
        display_name: "Out",
        types: [savedType, "Message"],
        selected: savedType,
      };
      const sourceNode = updatedSourceNode(saved, ["Message", newType]);

      expect(sourceNode.data.node!.outputs![0].selected).toBe(newType);
      const result = cleanEdges([sourceNode, typedTargetNode], [typedEdge]);
      expect(result.edges).toHaveLength(1);
      expect(result.brokenEdges).toHaveLength(0);
    },
  );

  it.each([
    ["JSON", "Data"],
    ["Table", "DataFrame"],
  ])(
    "should keep an exact %s pick when the output also offers %s",
    (picked, otherName) => {
      const saved: OutputFieldType = {
        name: "out",
        display_name: "Out",
        types: [otherName, picked],
        selected: picked,
      };
      const sourceNode = updatedSourceNode(saved, [otherName, picked]);

      expect(sourceNode.data.node!.outputs![0].selected).toBe(picked);
    },
  );

  it.each([null, undefined, 5])(
    "should keep the only type of an output saved with selected %p, and its edge",
    (selected) => {
      const saved = {
        name: "out",
        display_name: "Out",
        types: ["Message"],
        selected,
      } as unknown as OutputFieldType;
      const sourceNode = updatedSourceNode(saved, ["Tool", "Message"]);

      expect(sourceNode.data.node!.outputs![0].selected).toBe("Message");
      const result = cleanEdges([sourceNode, targetNode], [edge]);
      expect(result.edges).toHaveLength(1);
      expect(result.brokenEdges).toHaveLength(0);
    },
  );

  it("should keep the saved output options, such as the inspection filter", () => {
    const saved: OutputFieldType = {
      name: "out",
      display_name: "Out",
      types: ["Message"],
      selected: "Message",
      options: { filter: "results[0]" },
    };
    const sourceNode = updatedSourceNode(saved, ["Message"]);

    expect(sourceNode.data.node!.outputs![0].options).toEqual({
      filter: "results[0]",
    });
  });
});
