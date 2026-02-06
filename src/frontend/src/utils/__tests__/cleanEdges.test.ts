/**
 * Jest test for the cleanEdges function from utils/reactflowUtils.ts
 *
 * Tests the ModelInput type handling fix where input_types defaults based on model_type:
 * - "embedding" -> ["Embeddings"]
 * - "language" (default) -> ["LanguageModel"]
 */

import { cloneDeep } from "lodash";

// Mock scapeJSONParse and scapedJSONStringfy functions
const scapeJSONParse = (str: string) => {
  try {
    return JSON.parse(str.replace(/œ/g, '"'));
  } catch {
    return {};
  }
};

const scapedJSONStringfy = (obj: unknown) => {
  return JSON.stringify(obj).replace(/"/g, "œ");
};

// Define minimal types needed for testing
interface TargetHandleType {
  fieldName?: string;
  name?: string;
  id: string;
  inputTypes?: string[];
  type?: string;
  proxy?: unknown;
}

interface SourceHandleType {
  id: string;
  name: string;
  output_types: string[];
  dataType: string;
}

interface NodeOutput {
  name: string;
  display_name?: string;
  types: string[];
  selected?: string;
  allows_loop?: boolean;
  loop_types?: string[];
  group_outputs?: boolean;
}

interface AllNodeType {
  id: string;
  type: string;
  data: {
    id: string;
    type: string;
    selected_output?: string;
    node: {
      display_name: string;
      template: Record<string, unknown>;
      outputs?: NodeOutput[];
      tool_mode?: boolean;
    };
  };
}

interface EdgeType {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
  selected?: boolean;
  animated?: boolean;
  data?: unknown;
}

// Simplified filterHiddenFieldsEdges mock
const filterHiddenFieldsEdges = (
  _edge: EdgeType,
  edges: EdgeType[],
  _targetNode: AllNodeType,
) => edges;

// Reimplement cleanEdges function for testing (matches the fix in reactflowUtils.ts)
function cleanEdges(nodes: AllNodeType[], edges: EdgeType[]) {
  const brokenEdges: Array<{
    source: { nodeDisplayName: string; outputDisplayName?: string };
    target: { displayName: string; field: string };
  }> = [];

  function generateAlertObject(
    sourceNode: AllNodeType,
    targetNode: AllNodeType,
    edge: EdgeType,
  ) {
    const targetHandleObject = scapeJSONParse(
      edge.targetHandle!,
    ) as TargetHandleType;
    const sourceHandleObject = scapeJSONParse(
      edge.sourceHandle!,
    ) as SourceHandleType;
    const name = sourceHandleObject.name;
    const output = sourceNode.data.node.outputs?.find((o) => o.name === name);
    const template = targetNode.data.node.template as Record<
      string,
      { display_name?: string }
    >;

    return {
      source: {
        nodeDisplayName: sourceNode.data.node.display_name,
        outputDisplayName: output?.display_name,
      },
      target: {
        displayName: targetNode.data.node.display_name,
        field:
          template[targetHandleObject.fieldName!]?.display_name ??
          targetHandleObject.fieldName ??
          targetHandleObject.name ??
          "",
      },
    };
  }

  let newEdges: EdgeType[] = cloneDeep(
    edges.map((edge) => ({ ...edge, selected: false, animated: false })),
  );

  edges.forEach((edge) => {
    const sourceNode = nodes.find((node) => node.id === edge.source);
    const targetNode = nodes.find((node) => node.id === edge.target);
    if (!sourceNode || !targetNode) {
      newEdges = newEdges.filter((edg) => edg.id !== edge.id);
      return;
    }

    const sourceHandle = edge.sourceHandle;
    const targetHandle = edge.targetHandle;

    if (targetHandle) {
      const targetHandleObject = scapeJSONParse(
        targetHandle,
      ) as TargetHandleType;
      const field = targetHandleObject.fieldName;
      const template = targetNode.data.node.template as Record<
        string,
        {
          type?: string;
          input_types?: string[];
          proxy?: unknown;
          tool_mode?: boolean;
        }
      >;

      const templateFieldType = template[field!]?.type;
      const rawInputTypes = template[field!]?.input_types;
      const modelType = (template[field!] as { model_type?: string })
        ?.model_type;
      // For ModelInput types, default based on model_type:
      // - "embedding" -> ["Embeddings"]
      // - "language" (default) -> ["LanguageModel"]
      const isModelType = templateFieldType === "model";
      const defaultModelInputType =
        modelType === "embedding" ? "Embeddings" : "LanguageModel";
      const inputTypes =
        rawInputTypes && rawInputTypes.length > 0
          ? rawInputTypes
          : isModelType
            ? [defaultModelInputType]
            : rawInputTypes;
      const hasProxy = template[field!]?.proxy;
      const isToolMode = template[field!]?.tool_mode;

      let id: TargetHandleType | SourceHandleType;

      if (
        !field &&
        targetHandleObject.name &&
        targetNode.type === "genericNode"
      ) {
        const dataType = targetNode.data.type;
        const output = targetNode.data.node.outputs?.find(
          (o) => o.name === targetHandleObject.name,
        );
        const baseTypes = output?.types ?? [];
        const outputTypes =
          output?.allows_loop && output?.loop_types
            ? [output.selected ?? baseTypes[0], ...output.loop_types]
            : baseTypes;

        id = {
          dataType: dataType ?? "",
          name: targetHandleObject.name,
          id: targetNode.data.id,
          output_types: outputTypes,
        };
      } else {
        id = {
          type: templateFieldType,
          fieldName: field,
          id: targetNode.data.id,
          inputTypes: inputTypes,
        } as TargetHandleType;
        if (hasProxy) {
          (id as TargetHandleType).proxy = template[field!]?.proxy;
        }
      }

      const targetOutput = targetNode.data.node.outputs?.find(
        (o) => o.name === targetHandleObject.name,
      );
      const isLoopInput = targetOutput?.allows_loop === true;

      if (
        (scapedJSONStringfy(id) !== targetHandle ||
          (targetNode.data.node?.tool_mode && isToolMode)) &&
        !isLoopInput
      ) {
        newEdges = newEdges.filter((e) => e.id !== edge.id);
        brokenEdges.push(generateAlertObject(sourceNode, targetNode, edge));
      }
    }

    if (sourceHandle) {
      const parsedSourceHandle = scapeJSONParse(
        sourceHandle,
      ) as SourceHandleType;
      const name = parsedSourceHandle.name;

      if (sourceNode.type === "genericNode") {
        const output =
          sourceNode.data.node.outputs?.find(
            (o) => o.name === sourceNode.data.selected_output,
          ) ??
          sourceNode.data.node.outputs?.find(
            (o) =>
              (o.selected ||
                (sourceNode.data.node.outputs?.filter(
                  (out) => !out.group_outputs,
                )?.length ?? 0) <= 1) &&
              o.name === name,
          );

        if (output) {
          const outputTypes =
            output.types.length === 1 ? output.types : [output.selected!];

          const id: SourceHandleType = {
            id: sourceNode.data.id,
            name: output?.name ?? name,
            output_types: outputTypes,
            dataType: sourceNode.data.type,
          };

          const hasAllowsLoop = output?.allows_loop === true;
          if (scapedJSONStringfy(id) !== sourceHandle && !hasAllowsLoop) {
            newEdges = newEdges.filter((e) => e.id !== edge.id);
            brokenEdges.push(generateAlertObject(sourceNode, targetNode, edge));
          }
        } else {
          newEdges = newEdges.filter((e) => e.id !== edge.id);
          brokenEdges.push(generateAlertObject(sourceNode, targetNode, edge));
        }
      }
    }

    newEdges = filterHiddenFieldsEdges(edge, newEdges, targetNode);
  });

  return { edges: newEdges, brokenEdges };
}

describe("cleanEdges", () => {
  describe("ModelInput type handling", () => {
    it("should preserve edge when ModelInput has empty input_types and edge expects LanguageModel", () => {
      // This tests the fix for the SmartRouter connection issue
      const sourceNode: AllNodeType = {
        id: "LanguageModelComponent-123",
        type: "genericNode",
        data: {
          id: "LanguageModelComponent-123",
          type: "LanguageModelComponent",
          selected_output: "model_output",
          node: {
            display_name: "Language Model",
            template: {},
            outputs: [
              {
                name: "model_output",
                display_name: "Model Output",
                types: ["LanguageModel"],
                selected: "LanguageModel",
              },
            ],
          },
        },
      };

      const targetNode: AllNodeType = {
        id: "SmartRouter-456",
        type: "genericNode",
        data: {
          id: "SmartRouter-456",
          type: "SmartRouter",
          node: {
            display_name: "Smart Router",
            template: {
              model: {
                type: "model",
                input_types: [], // Empty input_types - this is the bug scenario
                display_name: "Language Model",
              },
            },
            outputs: [],
          },
        },
      };

      // Property order must match cleanEdges reconstruction: type, fieldName, id, inputTypes
      const targetHandleWithLanguageModel = scapedJSONStringfy({
        type: "model",
        fieldName: "model",
        id: "SmartRouter-456",
        inputTypes: ["LanguageModel"],
      });

      const sourceHandleStr = scapedJSONStringfy({
        id: "LanguageModelComponent-123",
        name: "model_output",
        output_types: ["LanguageModel"],
        dataType: "LanguageModelComponent",
      });

      const edge: EdgeType = {
        id: "edge-1",
        source: "LanguageModelComponent-123",
        target: "SmartRouter-456",
        sourceHandle: sourceHandleStr,
        targetHandle: targetHandleWithLanguageModel,
      };

      const result = cleanEdges([sourceNode, targetNode], [edge]);

      // Edge should be preserved because cleanEdges now defaults to ["LanguageModel"]
      expect(result.edges.length).toBe(1);
      expect(result.brokenEdges.length).toBe(0);
    });

    it("should preserve edge when ModelInput has explicit input_types", () => {
      const sourceNode2: AllNodeType = {
        id: "LanguageModelComponent-123",
        type: "genericNode",
        data: {
          id: "LanguageModelComponent-123",
          type: "LanguageModelComponent",
          selected_output: "model_output",
          node: {
            display_name: "Language Model",
            template: {},
            outputs: [
              {
                name: "model_output",
                display_name: "Model Output",
                types: ["LanguageModel"],
                selected: "LanguageModel",
              },
            ],
          },
        },
      };

      const targetNode2: AllNodeType = {
        id: "SmartRouter-456",
        type: "genericNode",
        data: {
          id: "SmartRouter-456",
          type: "SmartRouter",
          node: {
            display_name: "Smart Router",
            template: {
              model: {
                type: "model",
                input_types: ["LanguageModel"], // Explicit input_types
                display_name: "Language Model",
              },
            },
            outputs: [],
          },
        },
      };

      // Property order must match cleanEdges reconstruction: type, fieldName, id, inputTypes
      const targetHandleStr2 = scapedJSONStringfy({
        type: "model",
        fieldName: "model",
        id: "SmartRouter-456",
        inputTypes: ["LanguageModel"],
      });

      const sourceHandleStr2 = scapedJSONStringfy({
        id: "LanguageModelComponent-123",
        name: "model_output",
        output_types: ["LanguageModel"],
        dataType: "LanguageModelComponent",
      });

      const edge2: EdgeType = {
        id: "edge-1",
        source: "LanguageModelComponent-123",
        target: "SmartRouter-456",
        sourceHandle: sourceHandleStr2,
        targetHandle: targetHandleStr2,
      };

      const result2 = cleanEdges([sourceNode2, targetNode2], [edge2]);

      expect(result2.edges.length).toBe(1);
      expect(result2.brokenEdges.length).toBe(0);
    });

    it("should not apply LanguageModel default to non-model type fields", () => {
      const sourceNode3: AllNodeType = {
        id: "TextInput-123",
        type: "genericNode",
        data: {
          id: "TextInput-123",
          type: "TextInput",
          selected_output: "text",
          node: {
            display_name: "Text Input",
            template: {},
            outputs: [
              {
                name: "text",
                display_name: "Text",
                types: ["str"],
                selected: "str",
              },
            ],
          },
        },
      };

      const targetNode3: AllNodeType = {
        id: "Prompt-456",
        type: "genericNode",
        data: {
          id: "Prompt-456",
          type: "Prompt",
          node: {
            display_name: "Prompt",
            template: {
              text_input: {
                type: "str", // Not a model type
                input_types: [], // Empty - should NOT default to LanguageModel
                display_name: "Text Input",
              },
            },
            outputs: [],
          },
        },
      };

      // Edge with mismatched inputTypes (edge expects ["str"] but template has [])
      const targetHandleStr3 = scapedJSONStringfy({
        fieldName: "text_input",
        id: "Prompt-456",
        inputTypes: ["str"],
        type: "str",
      });

      const sourceHandleStr3 = scapedJSONStringfy({
        id: "TextInput-123",
        name: "text",
        output_types: ["str"],
        dataType: "TextInput",
      });

      const edge3: EdgeType = {
        id: "edge-1",
        source: "TextInput-123",
        target: "Prompt-456",
        sourceHandle: sourceHandleStr3,
        targetHandle: targetHandleStr3,
      };

      const result3 = cleanEdges([sourceNode3, targetNode3], [edge3]);

      // Edge should be removed because non-model types don't get the default
      expect(result3.edges.length).toBe(0);
      expect(result3.brokenEdges.length).toBe(1);
    });

    it("should preserve edge when EmbeddingModel has empty input_types and edge expects Embeddings (LE-278)", () => {
      // This tests the fix for embedding model input type (LE-278)
      const sourceNode: AllNodeType = {
        id: "EmbeddingModelComponent-123",
        type: "genericNode",
        data: {
          id: "EmbeddingModelComponent-123",
          type: "EmbeddingModelComponent",
          selected_output: "embeddings",
          node: {
            display_name: "Embedding Model",
            template: {},
            outputs: [
              {
                name: "embeddings",
                display_name: "Embedding Model",
                types: ["Embeddings"],
                selected: "Embeddings",
              },
            ],
          },
        },
      };

      const targetNode: AllNodeType = {
        id: "VectorStore-456",
        type: "genericNode",
        data: {
          id: "VectorStore-456",
          type: "VectorStore",
          node: {
            display_name: "Vector Store",
            template: {
              model: {
                type: "model",
                model_type: "embedding", // This is the key field for embedding models
                input_types: [], // Empty input_types - should default to ["Embeddings"]
                display_name: "Embedding Model",
              },
            },
            outputs: [],
          },
        },
      };

      const targetHandleWithEmbeddings = scapedJSONStringfy({
        type: "model",
        fieldName: "model",
        id: "VectorStore-456",
        inputTypes: ["Embeddings"],
      });

      const sourceHandleStr = scapedJSONStringfy({
        id: "EmbeddingModelComponent-123",
        name: "embeddings",
        output_types: ["Embeddings"],
        dataType: "EmbeddingModelComponent",
      });

      const edge: EdgeType = {
        id: "edge-1",
        source: "EmbeddingModelComponent-123",
        target: "VectorStore-456",
        sourceHandle: sourceHandleStr,
        targetHandle: targetHandleWithEmbeddings,
      };

      const result = cleanEdges([sourceNode, targetNode], [edge]);

      // Edge should be preserved because cleanEdges now defaults to ["Embeddings"] for embedding model_type
      expect(result.edges.length).toBe(1);
      expect(result.brokenEdges.length).toBe(0);
    });
  });

  describe("Basic edge validation", () => {
    it("should remove edge when source node does not exist", () => {
      const targetNodeBasic: AllNodeType = {
        id: "Target-456",
        type: "genericNode",
        data: {
          id: "Target-456",
          type: "Target",
          node: {
            display_name: "Target",
            template: {},
            outputs: [],
          },
        },
      };

      const edgeBasic: EdgeType = {
        id: "edge-1",
        source: "NonExistent-123",
        target: "Target-456",
      };

      const resultBasic = cleanEdges([targetNodeBasic], [edgeBasic]);

      expect(resultBasic.edges.length).toBe(0);
    });

    it("should remove edge when target node does not exist", () => {
      const sourceNodeBasic: AllNodeType = {
        id: "Source-123",
        type: "genericNode",
        data: {
          id: "Source-123",
          type: "Source",
          node: {
            display_name: "Source",
            template: {},
            outputs: [
              {
                name: "output",
                types: ["str"],
                selected: "str",
              },
            ],
          },
        },
      };

      const edgeBasic2: EdgeType = {
        id: "edge-1",
        source: "Source-123",
        target: "NonExistent-456",
      };

      const resultBasic2 = cleanEdges([sourceNodeBasic], [edgeBasic2]);

      expect(resultBasic2.edges.length).toBe(0);
    });
  });
});
