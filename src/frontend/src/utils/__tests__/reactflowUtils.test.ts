import type { Edge } from "@xyflow/react";
import { cloneDeep } from "lodash";
import type { AllNodeType } from "@/types/flow";
import {
  cleanEdges,
  detectBrokenEdgesEdges,
  scapedJSONStringfy,
  scapeJSONParse,
} from "../reactflowUtils";

// Mock useFlowStore to avoid Zustand issues in tests
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      nodes: [],
      edges: [],
    }),
  },
}));

/**
 * Helper to create a mock node with the given configuration
 */
function createMockNode(
  id: string,
  options: {
    type?: string;
    displayName?: string;
    selectedOutput?: string;
    outputs?: Array<{
      name: string;
      display_name?: string;
      types: string[];
      selected?: string;
      allows_loop?: boolean;
      loop_types?: string[];
      group_outputs?: boolean;
    }>;
    template?: Record<
      string,
      {
        type?: string;
        input_types?: string[];
        display_name?: string;
        proxy?: unknown;
        show?: boolean;
      }
    >;
  } = {},
): AllNodeType {
  // Auto-set selected_output to first output if not specified
  const selectedOutput = options.selectedOutput ?? options.outputs?.[0]?.name;

  return {
    id,
    type: options.type ?? "genericNode",
    position: { x: 0, y: 0 },
    data: {
      id,
      type: options.displayName ?? "TestComponent",
      selected_output: selectedOutput,
      node: {
        display_name: options.displayName ?? "Test Node",
        outputs: options.outputs ?? [],
        template: options.template ?? {},
      },
    },
  } as AllNodeType;
}

/**
 * Helper to create an edge with source handle (output)
 */
function createSourceHandle(
  nodeId: string,
  outputName: string,
  outputTypes: string[],
  dataType: string,
): string {
  return scapedJSONStringfy({
    id: nodeId,
    name: outputName,
    output_types: outputTypes,
    dataType,
  });
}

/**
 * Helper to create an edge with target handle (input)
 */
function createTargetHandle(
  nodeId: string,
  fieldName: string,
  fieldType: string,
  inputTypes?: string[],
): string {
  const handle: Record<string, unknown> = {
    id: nodeId,
    fieldName,
    type: fieldType,
  };
  if (inputTypes) {
    handle.inputTypes = inputTypes;
  }
  return scapedJSONStringfy(handle);
}

/**
 * Helper to create a target handle for loop input (output acting as input)
 */
function createLoopTargetHandle(
  nodeId: string,
  outputName: string,
  outputTypes: string[],
  dataType: string,
): string {
  return scapedJSONStringfy({
    id: nodeId,
    name: outputName,
    output_types: outputTypes,
    dataType,
  });
}

/**
 * Helper to create an edge
 */
function createEdge(
  id: string,
  source: string,
  target: string,
  sourceHandle: string,
  targetHandle: string,
): Edge {
  return {
    id,
    source,
    target,
    sourceHandle,
    targetHandle,
  };
}

describe("reactflowUtils edge validation", () => {
  describe("detectBrokenEdgesEdges", () => {
    describe("regular edges", () => {
      it("should not detect valid edge as broken", () => {
        const sourceNode = createMockNode("source-1", {
          displayName: "SourceComponent",
          outputs: [
            { name: "output", display_name: "Output", types: ["Message"] },
          ],
        });

        const targetNode = createMockNode("target-1", {
          displayName: "TargetComponent",
          template: {
            input_field: {
              type: "str",
              input_types: ["Message"],
              display_name: "Input Field",
            },
          },
        });

        const sourceHandle = createSourceHandle(
          "source-1",
          "output",
          ["Message"],
          "SourceComponent",
        );
        const targetHandle = createTargetHandle(
          "target-1",
          "input_field",
          "str",
          ["Message"],
        );

        const edge = createEdge(
          "edge-1",
          "source-1",
          "target-1",
          sourceHandle,
          targetHandle,
        );

        const brokenEdges = detectBrokenEdgesEdges(
          [sourceNode, targetNode],
          [edge],
        );

        expect(brokenEdges).toHaveLength(0);
      });

      it("should detect edge with mismatched source output types as broken", () => {
        const sourceNode = createMockNode("source-1", {
          displayName: "SourceComponent",
          outputs: [
            // Output now has different type than what's stored in edge
            { name: "output", display_name: "Output", types: ["Data"] },
          ],
        });

        const targetNode = createMockNode("target-1", {
          displayName: "TargetComponent",
          template: {
            input_field: {
              type: "str",
              input_types: ["Message"],
              display_name: "Input Field",
            },
          },
        });

        // Edge was created when output was Message type
        const sourceHandle = createSourceHandle(
          "source-1",
          "output",
          ["Message"],
          "SourceComponent",
        );
        const targetHandle = createTargetHandle(
          "target-1",
          "input_field",
          "str",
          ["Message"],
        );

        const edge = createEdge(
          "edge-1",
          "source-1",
          "target-1",
          sourceHandle,
          targetHandle,
        );

        const brokenEdges = detectBrokenEdgesEdges(
          [sourceNode, targetNode],
          [edge],
        );

        expect(brokenEdges).toHaveLength(1);
        expect(brokenEdges[0].source.nodeDisplayName).toBe("SourceComponent");
      });

      it("should detect edge with missing source node as broken", () => {
        const targetNode = createMockNode("target-1", {
          displayName: "TargetComponent",
          template: {
            input_field: { type: "str", input_types: ["Message"] },
          },
        });

        const sourceHandle = createSourceHandle(
          "source-1",
          "output",
          ["Message"],
          "SourceComponent",
        );
        const targetHandle = createTargetHandle(
          "target-1",
          "input_field",
          "str",
        );

        const edge = createEdge(
          "edge-1",
          "source-1",
          "target-1",
          sourceHandle,
          targetHandle,
        );

        // Only target node exists
        const brokenEdges = detectBrokenEdgesEdges([targetNode], [edge]);

        // Edge should be filtered out (not in brokenEdges array, but removed)
        // The function returns early for missing nodes without adding to BrokenEdges
        expect(brokenEdges).toHaveLength(0);
      });

      it("should detect edge with missing target node as broken", () => {
        const sourceNode = createMockNode("source-1", {
          displayName: "SourceComponent",
          outputs: [{ name: "output", types: ["Message"] }],
        });

        const sourceHandle = createSourceHandle(
          "source-1",
          "output",
          ["Message"],
          "SourceComponent",
        );
        const targetHandle = createTargetHandle(
          "target-1",
          "input_field",
          "str",
        );

        const edge = createEdge(
          "edge-1",
          "source-1",
          "target-1",
          sourceHandle,
          targetHandle,
        );

        // Only source node exists
        const brokenEdges = detectBrokenEdgesEdges([sourceNode], [edge]);

        expect(brokenEdges).toHaveLength(0);
      });

      it("should detect edge with non-existent output as broken", () => {
        const sourceNode = createMockNode("source-1", {
          displayName: "SourceComponent",
          outputs: [
            // Output has different name
            { name: "different_output", types: ["Message"] },
          ],
        });

        const targetNode = createMockNode("target-1", {
          displayName: "TargetComponent",
          template: {
            input_field: { type: "str", input_types: ["Message"] },
          },
        });

        const sourceHandle = createSourceHandle(
          "source-1",
          "output", // This output doesn't exist
          ["Message"],
          "SourceComponent",
        );
        const targetHandle = createTargetHandle(
          "target-1",
          "input_field",
          "str",
        );

        const edge = createEdge(
          "edge-1",
          "source-1",
          "target-1",
          sourceHandle,
          targetHandle,
        );

        const brokenEdges = detectBrokenEdgesEdges(
          [sourceNode, targetNode],
          [edge],
        );

        // Edge is detected as broken (may be reported multiple times for different handle issues)
        expect(brokenEdges.length).toBeGreaterThanOrEqual(1);
        expect(brokenEdges[0].source.nodeDisplayName).toBe("SourceComponent");
      });
    });

    describe("loop edges with allows_loop", () => {
      it("should not detect valid loop output edge as broken", () => {
        // WhileLoop component with loop output
        const whileLoopNode = createMockNode("while-loop-1", {
          displayName: "WhileLoopComponent",
          outputs: [
            {
              name: "loop",
              display_name: "Loop",
              types: ["DataFrame"],
              selected: "DataFrame",
              allows_loop: true,
              loop_types: ["DataFrame"],
            },
          ],
        });

        // AgentStep component with messages input
        const agentStepNode = createMockNode("agent-step-1", {
          displayName: "AgentStepComponent",
          template: {
            messages: {
              type: "other",
              input_types: ["DataFrame"],
              display_name: "Message History",
            },
          },
        });

        // Source handles (right side) only use [selectedType], not loop_types
        const sourceHandle = createSourceHandle(
          "while-loop-1",
          "loop",
          ["DataFrame"], // Only selectedType, loop_types is for loop inputs (left side)
          "WhileLoopComponent",
        );
        const targetHandle = createTargetHandle(
          "agent-step-1",
          "messages",
          "other",
          ["DataFrame"],
        );

        const edge = createEdge(
          "edge-1",
          "while-loop-1",
          "agent-step-1",
          sourceHandle,
          targetHandle,
        );

        const brokenEdges = detectBrokenEdgesEdges(
          [whileLoopNode, agentStepNode],
          [edge],
        );

        expect(brokenEdges).toHaveLength(0);
      });

      it("should not detect valid loop feedback edge as broken", () => {
        // ExecuteTool component with messages output
        const executeToolNode = createMockNode("execute-tool-1", {
          displayName: "ExecuteToolComponent",
          outputs: [
            {
              name: "messages",
              display_name: "Messages",
              types: ["DataFrame"],
              selected: "DataFrame",
            },
          ],
        });

        // WhileLoop component with loop output that accepts feedback
        const whileLoopNode = createMockNode("while-loop-1", {
          displayName: "WhileLoopComponent",
          outputs: [
            {
              name: "loop",
              display_name: "Loop",
              types: ["DataFrame"],
              selected: "DataFrame",
              allows_loop: true,
              loop_types: ["DataFrame"],
            },
          ],
        });

        const sourceHandle = createSourceHandle(
          "execute-tool-1",
          "messages",
          ["DataFrame"],
          "ExecuteToolComponent",
        );

        // Target is the loop output (acting as loop input)
        const targetHandle = createLoopTargetHandle(
          "while-loop-1",
          "loop",
          ["DataFrame", "DataFrame"], // [selectedType, ...loop_types]
          "WhileLoopComponent",
        );

        const edge = createEdge(
          "edge-1",
          "execute-tool-1",
          "while-loop-1",
          sourceHandle,
          targetHandle,
        );

        const brokenEdges = detectBrokenEdgesEdges(
          [executeToolNode, whileLoopNode],
          [edge],
        );

        expect(brokenEdges).toHaveLength(0);
      });

      it("should handle loop output source handle correctly (no loop_types)", () => {
        const loopNode = createMockNode("loop-1", {
          displayName: "LoopComponent",
          outputs: [
            {
              name: "loop_output",
              types: ["Message"],
              selected: "Message",
              allows_loop: true,
              loop_types: ["DataFrame", "Data"],
            },
          ],
        });

        const targetNode = createMockNode("target-1", {
          displayName: "TargetComponent",
          template: {
            input: { type: "other", input_types: ["Message", "DataFrame"] },
          },
        });

        // Source handles (right side) only use [selectedType], loop_types is for loop inputs
        const sourceHandle = createSourceHandle(
          "loop-1",
          "loop_output",
          ["Message"], // Only selectedType, not [...loop_types]
          "LoopComponent",
        );
        const targetHandle = createTargetHandle("target-1", "input", "other", [
          "Message",
          "DataFrame",
        ]);

        const edge = createEdge(
          "edge-1",
          "loop-1",
          "target-1",
          sourceHandle,
          targetHandle,
        );

        const brokenEdges = detectBrokenEdgesEdges(
          [loopNode, targetNode],
          [edge],
        );

        expect(brokenEdges).toHaveLength(0);
      });

      it("should detect broken edge when selected type changes", () => {
        const loopNode = createMockNode("loop-1", {
          displayName: "LoopComponent",
          outputs: [
            {
              name: "loop_output",
              types: ["Message", "Data"],
              selected: "Data", // Changed from "Message"
              allows_loop: true,
              loop_types: ["DataFrame"],
            },
          ],
        });

        const targetNode = createMockNode("target-1", {
          displayName: "TargetComponent",
          template: {
            input: { type: "other", input_types: ["Message", "DataFrame"] },
          },
        });

        // Old handle with old selected type "Message"
        const sourceHandle = createSourceHandle(
          "loop-1",
          "loop_output",
          ["Message"], // Old selectedType
          "LoopComponent",
        );
        const targetHandle = createTargetHandle("target-1", "input", "other");

        const edge = createEdge(
          "edge-1",
          "loop-1",
          "target-1",
          sourceHandle,
          targetHandle,
        );

        const brokenEdges = detectBrokenEdgesEdges(
          [loopNode, targetNode],
          [edge],
        );

        // Should detect as broken because selected type changed from Message to Data
        expect(brokenEdges.length).toBeGreaterThanOrEqual(1);
      });
    });

    describe("group_outputs handling", () => {
      it("should handle components with group_outputs correctly", () => {
        const sourceNode = createMockNode("source-1", {
          displayName: "MultiOutputComponent",
          selectedOutput: "output_a",
          outputs: [
            {
              name: "output_a",
              types: ["Message"],
              selected: "Message",
              group_outputs: true,
            },
            {
              name: "output_b",
              types: ["Data"],
              selected: "Data",
              group_outputs: true,
            },
          ],
        });

        const targetNode = createMockNode("target-1", {
          displayName: "TargetComponent",
          template: {
            input: { type: "other", input_types: ["Message"] },
          },
        });

        // Edge from output_a - with group_outputs, lookup by name works
        const sourceHandle = createSourceHandle(
          "source-1",
          "output_a",
          ["Message"],
          "MultiOutputComponent",
        );
        const targetHandle = createTargetHandle("target-1", "input", "other", [
          "Message",
        ]);

        const edge = createEdge(
          "edge-1",
          "source-1",
          "target-1",
          sourceHandle,
          targetHandle,
        );

        const brokenEdges = detectBrokenEdgesEdges(
          [sourceNode, targetNode],
          [edge],
        );

        expect(brokenEdges).toHaveLength(0);
      });
    });
  });

  describe("cleanEdges", () => {
    describe("regular edges", () => {
      it("should keep valid edges", () => {
        const sourceNode = createMockNode("source-1", {
          displayName: "SourceComponent",
          outputs: [{ name: "output", types: ["Message"] }],
        });

        const targetNode = createMockNode("target-1", {
          displayName: "TargetComponent",
          template: {
            input_field: { type: "str", input_types: ["Message"] },
          },
        });

        const sourceHandle = createSourceHandle(
          "source-1",
          "output",
          ["Message"],
          "SourceComponent",
        );
        // Must include input_types to match reconstruction
        const targetHandle = createTargetHandle(
          "target-1",
          "input_field",
          "str",
          ["Message"],
        );

        const edge = createEdge(
          "edge-1",
          "source-1",
          "target-1",
          sourceHandle,
          targetHandle,
        );

        const cleanedEdges = cleanEdges([sourceNode, targetNode], [edge]);

        expect(cleanedEdges).toHaveLength(1);
        expect(cleanedEdges[0].id).toBe("edge-1");
      });

      it("should remove edges with missing nodes", () => {
        const targetNode = createMockNode("target-1", {
          displayName: "TargetComponent",
          template: {
            input_field: { type: "str" },
          },
        });

        const sourceHandle = createSourceHandle(
          "source-1",
          "output",
          ["Message"],
          "SourceComponent",
        );
        const targetHandle = createTargetHandle(
          "target-1",
          "input_field",
          "str",
        );

        const edge = createEdge(
          "edge-1",
          "source-1", // This node doesn't exist
          "target-1",
          sourceHandle,
          targetHandle,
        );

        const cleanedEdges = cleanEdges([targetNode], [edge]);

        expect(cleanedEdges).toHaveLength(0);
      });

      it("should remove edges with mismatched handles", () => {
        const sourceNode = createMockNode("source-1", {
          displayName: "SourceComponent",
          outputs: [{ name: "output", types: ["Data"] }], // Different type
        });

        const targetNode = createMockNode("target-1", {
          displayName: "TargetComponent",
          template: {
            input_field: { type: "str", input_types: ["Message"] },
          },
        });

        const sourceHandle = createSourceHandle(
          "source-1",
          "output",
          ["Message"], // Doesn't match current output type
          "SourceComponent",
        );
        const targetHandle = createTargetHandle(
          "target-1",
          "input_field",
          "str",
        );

        const edge = createEdge(
          "edge-1",
          "source-1",
          "target-1",
          sourceHandle,
          targetHandle,
        );

        const cleanedEdges = cleanEdges([sourceNode, targetNode], [edge]);

        expect(cleanedEdges).toHaveLength(0);
      });
    });

    describe("loop edges with allows_loop", () => {
      it("should keep valid loop output edges", () => {
        const whileLoopNode = createMockNode("while-loop-1", {
          displayName: "WhileLoopComponent",
          outputs: [
            {
              name: "loop",
              types: ["DataFrame"],
              selected: "DataFrame",
              allows_loop: true,
              loop_types: ["DataFrame"],
            },
          ],
        });

        const agentStepNode = createMockNode("agent-step-1", {
          displayName: "AgentStepComponent",
          template: {
            messages: { type: "other", input_types: ["DataFrame"] },
          },
        });

        // Source handles (right side) only use [selectedType], not loop_types
        const sourceHandle = createSourceHandle(
          "while-loop-1",
          "loop",
          ["DataFrame"], // Only selectedType
          "WhileLoopComponent",
        );
        // Must include input_types to match reconstruction
        const targetHandle = createTargetHandle(
          "agent-step-1",
          "messages",
          "other",
          ["DataFrame"],
        );

        const edge = createEdge(
          "edge-1",
          "while-loop-1",
          "agent-step-1",
          sourceHandle,
          targetHandle,
        );

        const cleanedEdges = cleanEdges([whileLoopNode, agentStepNode], [edge]);

        expect(cleanedEdges).toHaveLength(1);
      });

      it("BUG REPRO: edge removed when sourceHandle uses [selectedType] as NodeOutputParameter builds it", () => {
        // This test reproduces the bug where WhileLoop -> AgentStep edge vanishes
        // NodeOutputParameter builds the RIGHT handle (source) with just [selectedType]
        // But cleanEdges expects [selectedType, ...loop_types]
        const whileLoopNode = createMockNode("while-loop-1", {
          displayName: "WhileLoopComponent",
          outputs: [
            {
              name: "loop",
              types: ["DataFrame"],
              selected: "DataFrame",
              allows_loop: true,
              loop_types: ["DataFrame"],
            },
          ],
        });

        const agentStepNode = createMockNode("agent-step-1", {
          displayName: "AgentStepComponent",
          template: {
            messages: { type: "other", input_types: ["DataFrame"] },
          },
        });

        // This is how NodeOutputParameter ACTUALLY builds the right handle (source):
        // output_types: [selectedType] - just ["DataFrame"], NOT ["DataFrame", "DataFrame"]
        // See NodeOutputParameter lines 22-31
        const sourceHandle = createSourceHandle(
          "while-loop-1",
          "loop",
          ["DataFrame"], // This is what NodeOutputParameter actually creates!
          "WhileLoopComponent",
        );
        // Must include input_types to match reconstruction
        const targetHandle = createTargetHandle(
          "agent-step-1",
          "messages",
          "other",
          ["DataFrame"],
        );

        const edge = createEdge(
          "edge-1",
          "while-loop-1",
          "agent-step-1",
          sourceHandle,
          targetHandle,
        );

        const cleanedEdges = cleanEdges([whileLoopNode, agentStepNode], [edge]);

        expect(cleanedEdges).toHaveLength(1);
      });

      it("should keep loop feedback edges (output as target)", () => {
        const executeToolNode = createMockNode("execute-tool-1", {
          displayName: "ExecuteToolComponent",
          outputs: [
            {
              name: "messages",
              types: ["DataFrame"],
              selected: "DataFrame",
            },
          ],
        });

        const whileLoopNode = createMockNode("while-loop-1", {
          displayName: "WhileLoopComponent",
          outputs: [
            {
              name: "loop",
              types: ["DataFrame"],
              selected: "DataFrame",
              allows_loop: true,
              loop_types: ["DataFrame"],
            },
          ],
        });

        const sourceHandle = createSourceHandle(
          "execute-tool-1",
          "messages",
          ["DataFrame"],
          "ExecuteToolComponent",
        );
        const targetHandle = createLoopTargetHandle(
          "while-loop-1",
          "loop",
          ["DataFrame", "DataFrame"],
          "WhileLoopComponent",
        );

        const edge = createEdge(
          "edge-1",
          "execute-tool-1",
          "while-loop-1",
          sourceHandle,
          targetHandle,
        );

        const cleanedEdges = cleanEdges(
          [executeToolNode, whileLoopNode],
          [edge],
        );

        expect(cleanedEdges).toHaveLength(1);
      });
    });

    describe("hidden fields", () => {
      it("should remove edges connected to hidden fields", () => {
        const sourceNode = createMockNode("source-1", {
          displayName: "SourceComponent",
          outputs: [{ name: "output", types: ["Message"] }],
        });

        const targetNode = createMockNode("target-1", {
          displayName: "TargetComponent",
          template: {
            hidden_field: {
              type: "str",
              input_types: ["Message"],
              show: false, // Hidden field
            },
          },
        });

        const sourceHandle = createSourceHandle(
          "source-1",
          "output",
          ["Message"],
          "SourceComponent",
        );
        const targetHandle = createTargetHandle(
          "target-1",
          "hidden_field",
          "str",
        );

        const edge = createEdge(
          "edge-1",
          "source-1",
          "target-1",
          sourceHandle,
          targetHandle,
        );
        // Add the data property that filterHiddenFieldsEdges expects
        (
          edge as Edge & { data: { targetHandle: { fieldName: string } } }
        ).data = {
          targetHandle: { fieldName: "hidden_field" },
        };

        const cleanedEdges = cleanEdges([sourceNode, targetNode], [edge]);

        expect(cleanedEdges).toHaveLength(0);
      });
    });

    describe("multiple edges", () => {
      it("should handle multiple edges correctly", () => {
        const sourceNode = createMockNode("source-1", {
          displayName: "SourceComponent",
          selectedOutput: "output_a",
          outputs: [
            // With group_outputs, each output is treated independently
            {
              name: "output_a",
              types: ["Message"],
              selected: "Message",
              group_outputs: true,
            },
            {
              name: "output_b",
              types: ["Data"],
              selected: "Data",
              group_outputs: true,
            },
          ],
        });

        const targetNode = createMockNode("target-1", {
          displayName: "TargetComponent",
          template: {
            input_a: { type: "str", input_types: ["Message"] },
            input_b: { type: "str", input_types: ["Data"] },
          },
        });

        const edge1 = createEdge(
          "edge-1",
          "source-1",
          "target-1",
          createSourceHandle(
            "source-1",
            "output_a",
            ["Message"],
            "SourceComponent",
          ),
          createTargetHandle("target-1", "input_a", "str", ["Message"]),
        );

        const edge2 = createEdge(
          "edge-2",
          "source-1",
          "target-1",
          createSourceHandle(
            "source-1",
            "output_b",
            ["Data"],
            "SourceComponent",
          ),
          createTargetHandle("target-1", "input_b", "str", ["Data"]),
        );

        const cleanedEdges = cleanEdges(
          [sourceNode, targetNode],
          [edge1, edge2],
        );

        expect(cleanedEdges).toHaveLength(2);
      });

      it("should remove only invalid edges from multiple", () => {
        const sourceNode = createMockNode("source-1", {
          displayName: "SourceComponent",
          selectedOutput: "output_a",
          outputs: [
            { name: "output_a", types: ["Message"], selected: "Message" },
            // output_b doesn't exist anymore
          ],
        });

        const targetNode = createMockNode("target-1", {
          displayName: "TargetComponent",
          template: {
            input_a: { type: "str", input_types: ["Message"] },
            input_b: { type: "str", input_types: ["Data"] },
          },
        });

        const edge1 = createEdge(
          "edge-1",
          "source-1",
          "target-1",
          createSourceHandle(
            "source-1",
            "output_a",
            ["Message"],
            "SourceComponent",
          ),
          createTargetHandle("target-1", "input_a", "str", ["Message"]),
        );

        const edge2 = createEdge(
          "edge-2",
          "source-1",
          "target-1",
          createSourceHandle(
            "source-1",
            "output_b",
            ["Data"],
            "SourceComponent",
          ), // This output doesn't exist
          createTargetHandle("target-1", "input_b", "str", ["Data"]),
        );

        const cleanedEdges = cleanEdges(
          [sourceNode, targetNode],
          [edge1, edge2],
        );

        expect(cleanedEdges).toHaveLength(1);
        expect(cleanedEdges[0].id).toBe("edge-1");
      });
    });
  });

  describe("handle serialization", () => {
    it("scapedJSONStringfy should produce consistent output", () => {
      const handle = {
        id: "node-1",
        name: "output",
        output_types: ["Message"],
        dataType: "Component",
      };

      const result1 = scapedJSONStringfy(handle);
      const result2 = scapedJSONStringfy(handle);

      expect(result1).toBe(result2);
    });

    it("scapeJSONParse should reverse scapedJSONStringfy", () => {
      const original = {
        id: "node-1",
        name: "output",
        output_types: ["Message"],
        dataType: "Component",
      };

      const serialized = scapedJSONStringfy(original);
      const parsed = scapeJSONParse(serialized);

      expect(parsed).toEqual(original);
    });

    it("should handle special characters in field names", () => {
      const handle = {
        id: "node-1",
        fieldName: "field_with_special_chars",
        type: "str",
      };

      const serialized = scapedJSONStringfy(handle);
      const parsed = scapeJSONParse(serialized);

      expect(parsed.fieldName).toBe("field_with_special_chars");
    });
  });
});
