import type { Edge, Node } from "@xyflow/react";
import type { GlobalVariable } from "@/types/global_variables";
import { getUpstreamOutputs } from "../getUpstreamOutputs";
import { VARS_SLUG } from "../referenceParser";

describe("getUpstreamOutputs", () => {
  const createNode = (
    id: string,
    displayName: string,
    outputs: Array<{ name: string; display_name?: string; types?: string[] }>,
  ): Node => ({
    id,
    position: { x: 0, y: 0 },
    data: {
      node: {
        display_name: displayName,
        outputs,
      },
    },
  });

  const createEdge = (source: string, target: string): Edge => ({
    id: `${source}-${target}`,
    source,
    target,
  });

  describe("basic functionality", () => {
    it("should return empty array when no upstream nodes", () => {
      const nodes = [
        createNode("node1", "Node 1", [{ name: "output", types: ["Message"] }]),
      ];
      const edges: Edge[] = [];
      const slugs = { node1: "Node1" };

      const outputs = getUpstreamOutputs("node1", nodes, edges, slugs);
      expect(outputs).toHaveLength(0);
    });

    it("should return upstream outputs from directly connected node", () => {
      const nodes = [
        createNode("node1", "Chat Input", [
          { name: "message", display_name: "Message", types: ["Message"] },
        ]),
        createNode("node2", "Prompt", [{ name: "output", types: ["str"] }]),
      ];
      const edges = [createEdge("node1", "node2")];
      const slugs = { node1: "ChatInput", node2: "Prompt" };

      const outputs = getUpstreamOutputs("node2", nodes, edges, slugs);
      expect(outputs).toHaveLength(1);
      expect(outputs[0]).toEqual({
        nodeId: "node1",
        nodeSlug: "ChatInput",
        nodeName: "Chat Input",
        outputName: "message",
        outputDisplayName: "Message",
        outputType: "Message",
      });
    });

    it("should return outputs from multiple upstream nodes", () => {
      const nodes = [
        createNode("node1", "Node 1", [{ name: "out1", types: ["Message"] }]),
        createNode("node2", "Node 2", [{ name: "out2", types: ["str"] }]),
        createNode("node3", "Node 3", [{ name: "out3", types: ["int"] }]),
      ];
      const edges = [
        createEdge("node1", "node3"),
        createEdge("node2", "node3"),
      ];
      const slugs = { node1: "Node1", node2: "Node2", node3: "Node3" };

      const outputs = getUpstreamOutputs("node3", nodes, edges, slugs);
      expect(outputs).toHaveLength(2);
    });
  });

  describe("recursive upstream traversal", () => {
    it("should find outputs from indirectly connected nodes", () => {
      const nodes = [
        createNode("node1", "Source", [{ name: "data", types: ["Message"] }]),
        createNode("node2", "Middle", [{ name: "processed", types: ["str"] }]),
        createNode("node3", "Target", [{ name: "final", types: ["Message"] }]),
      ];
      const edges = [
        createEdge("node1", "node2"),
        createEdge("node2", "node3"),
      ];
      const slugs = { node1: "Source", node2: "Middle", node3: "Target" };

      const outputs = getUpstreamOutputs("node3", nodes, edges, slugs);
      expect(outputs).toHaveLength(2);
      expect(outputs.find((o) => o.nodeSlug === "Source")).toBeDefined();
      expect(outputs.find((o) => o.nodeSlug === "Middle")).toBeDefined();
    });

    it("should handle diamond-shaped graphs without duplicates", () => {
      // node1 -> node2 -> node4
      // node1 -> node3 -> node4
      const nodes = [
        createNode("node1", "Source", [{ name: "data", types: ["Message"] }]),
        createNode("node2", "Branch A", [{ name: "a", types: ["str"] }]),
        createNode("node3", "Branch B", [{ name: "b", types: ["str"] }]),
        createNode("node4", "Merge", [{ name: "merged", types: ["Message"] }]),
      ];
      const edges = [
        createEdge("node1", "node2"),
        createEdge("node1", "node3"),
        createEdge("node2", "node4"),
        createEdge("node3", "node4"),
      ];
      const slugs = {
        node1: "Source",
        node2: "BranchA",
        node3: "BranchB",
        node4: "Merge",
      };

      const outputs = getUpstreamOutputs("node4", nodes, edges, slugs);
      // Should have 3 outputs: Source.data, BranchA.a, BranchB.b
      expect(outputs).toHaveLength(3);
      // Source should only appear once
      const sourceOutputs = outputs.filter((o) => o.nodeSlug === "Source");
      expect(sourceOutputs).toHaveLength(1);
    });
  });

  describe("output type filtering", () => {
    it("should include Message type outputs", () => {
      const nodes = [
        createNode("node1", "Input", [{ name: "message", types: ["Message"] }]),
        createNode("node2", "Output", []),
      ];
      const edges = [createEdge("node1", "node2")];
      const slugs = { node1: "Input", node2: "Output" };

      const outputs = getUpstreamOutputs("node2", nodes, edges, slugs);
      expect(outputs).toHaveLength(1);
      expect(outputs[0].outputType).toBe("Message");
    });

    it("should include str type outputs", () => {
      const nodes = [
        createNode("node1", "Input", [{ name: "text", types: ["str"] }]),
        createNode("node2", "Output", []),
      ];
      const edges = [createEdge("node1", "node2")];
      const slugs = { node1: "Input", node2: "Output" };

      const outputs = getUpstreamOutputs("node2", nodes, edges, slugs);
      expect(outputs).toHaveLength(1);
    });

    it("should include Data type outputs", () => {
      const nodes = [
        createNode("node1", "API", [{ name: "response", types: ["Data"] }]),
        createNode("node2", "Output", []),
      ];
      const edges = [createEdge("node1", "node2")];
      const slugs = { node1: "API", node2: "Output" };

      const outputs = getUpstreamOutputs("node2", nodes, edges, slugs);
      expect(outputs).toHaveLength(1);
    });

    it("should include int and float type outputs", () => {
      const nodes = [
        createNode("node1", "Math", [
          { name: "count", types: ["int"] },
          { name: "average", types: ["float"] },
        ]),
        createNode("node2", "Output", []),
      ];
      const edges = [createEdge("node1", "node2")];
      const slugs = { node1: "Math", node2: "Output" };

      const outputs = getUpstreamOutputs("node2", nodes, edges, slugs);
      expect(outputs).toHaveLength(2);
    });

    it("should exclude Tool type outputs", () => {
      const nodes = [
        createNode("node1", "Tools", [
          { name: "tool", types: ["Tool"] },
          { name: "text", types: ["str"] },
        ]),
        createNode("node2", "Output", []),
      ];
      const edges = [createEdge("node1", "node2")];
      const slugs = { node1: "Tools", node2: "Output" };

      const outputs = getUpstreamOutputs("node2", nodes, edges, slugs);
      expect(outputs).toHaveLength(1);
      expect(outputs[0].outputName).toBe("text");
    });

    it("should exclude Agent type outputs", () => {
      const nodes = [
        createNode("node1", "Agent", [{ name: "agent", types: ["Agent"] }]),
        createNode("node2", "Output", []),
      ];
      const edges = [createEdge("node1", "node2")];
      const slugs = { node1: "Agent", node2: "Output" };

      const outputs = getUpstreamOutputs("node2", nodes, edges, slugs);
      expect(outputs).toHaveLength(0);
    });

    it("should exclude Embeddings type outputs", () => {
      const nodes = [
        createNode("node1", "Embedder", [
          { name: "embeddings", types: ["Embeddings"] },
        ]),
        createNode("node2", "Output", []),
      ];
      const edges = [createEdge("node1", "node2")];
      const slugs = { node1: "Embedder", node2: "Output" };

      const outputs = getUpstreamOutputs("node2", nodes, edges, slugs);
      expect(outputs).toHaveLength(0);
    });
  });

  describe("edge cases", () => {
    it("should handle node with no outputs", () => {
      const nodes = [
        createNode("node1", "Empty", []),
        createNode("node2", "Output", []),
      ];
      const edges = [createEdge("node1", "node2")];
      const slugs = { node1: "Empty", node2: "Output" };

      const outputs = getUpstreamOutputs("node2", nodes, edges, slugs);
      expect(outputs).toHaveLength(0);
    });

    it("should handle missing slug by using 'Node' as default", () => {
      const nodes = [
        createNode("node1", "Input", [{ name: "out", types: ["Message"] }]),
        createNode("node2", "Output", []),
      ];
      const edges = [createEdge("node1", "node2")];
      const slugs = {}; // No slugs defined

      const outputs = getUpstreamOutputs("node2", nodes, edges, slugs);
      expect(outputs).toHaveLength(1);
      expect(outputs[0].nodeSlug).toBe("Node");
    });

    it("should handle missing display_name in output", () => {
      const nodes = [
        createNode("node1", "Input", [{ name: "out", types: ["Message"] }]),
        createNode("node2", "Output", []),
      ];
      const edges = [createEdge("node1", "node2")];
      const slugs = { node1: "Input", node2: "Output" };

      const outputs = getUpstreamOutputs("node2", nodes, edges, slugs);
      expect(outputs[0].outputDisplayName).toBe("out"); // Falls back to name
    });

    it("should handle output with no types", () => {
      const nodes = [
        createNode("node1", "Input", [{ name: "out" }]), // No types array
        createNode("node2", "Output", []),
      ];
      const edges = [createEdge("node1", "node2")];
      const slugs = { node1: "Input", node2: "Output" };

      const outputs = getUpstreamOutputs("node2", nodes, edges, slugs);
      // Should be excluded because "Any" is not in REFERENCEABLE_TYPES
      expect(outputs).toHaveLength(0);
    });

    it("should handle node not found in nodes array", () => {
      const nodes = [createNode("node2", "Output", [])];
      const edges = [createEdge("node1", "node2")]; // node1 doesn't exist
      const slugs = { node2: "Output" };

      const outputs = getUpstreamOutputs("node2", nodes, edges, slugs);
      expect(outputs).toHaveLength(0);
    });
  });

  describe("global variables", () => {
    const makeGlobalVar = (
      name: string,
      type: "Generic" | "Credential" = "Generic",
    ): GlobalVariable => ({
      id: `gv-${name}`,
      type,
      default_fields: [],
      name,
    });

    it("should include Generic global variables under Vars slug", () => {
      const nodes = [createNode("node1", "Output", [])];
      const slugs = { node1: "Output" };
      const globalVars = [makeGlobalVar("api_key"), makeGlobalVar("model")];

      const outputs = getUpstreamOutputs("node1", nodes, [], slugs, globalVars);
      const varsOutputs = outputs.filter((o) => o.nodeSlug === VARS_SLUG);
      expect(varsOutputs).toHaveLength(2);
      expect(varsOutputs[0]).toEqual({
        nodeId: "__vars__",
        nodeSlug: VARS_SLUG,
        nodeName: "Global Variables",
        outputName: "api_key",
        outputDisplayName: "api_key",
        outputType: "str",
      });
    });

    it("should exclude Credential type global variables", () => {
      const nodes = [createNode("node1", "Output", [])];
      const slugs = { node1: "Output" };
      const globalVars = [
        makeGlobalVar("api_key", "Generic"),
        makeGlobalVar("secret", "Credential"),
      ];

      const outputs = getUpstreamOutputs("node1", nodes, [], slugs, globalVars);
      const varsOutputs = outputs.filter((o) => o.nodeSlug === VARS_SLUG);
      expect(varsOutputs).toHaveLength(1);
      expect(varsOutputs[0].outputName).toBe("api_key");
    });

    it("should return no Vars outputs when globalVariables is undefined", () => {
      const nodes = [createNode("node1", "Output", [])];
      const slugs = { node1: "Output" };

      const outputs = getUpstreamOutputs("node1", nodes, [], slugs);
      const varsOutputs = outputs.filter((o) => o.nodeSlug === VARS_SLUG);
      expect(varsOutputs).toHaveLength(0);
    });

    it("should return no Vars outputs when globalVariables is empty", () => {
      const nodes = [createNode("node1", "Output", [])];
      const slugs = { node1: "Output" };

      const outputs = getUpstreamOutputs("node1", nodes, [], slugs, []);
      const varsOutputs = outputs.filter((o) => o.nodeSlug === VARS_SLUG);
      expect(varsOutputs).toHaveLength(0);
    });

    it("should combine upstream node outputs with global variables", () => {
      const nodes = [
        createNode("node1", "Chat Input", [
          { name: "message", types: ["Message"] },
        ]),
        createNode("node2", "Prompt", []),
      ];
      const edges = [createEdge("node1", "node2")];
      const slugs = { node1: "ChatInput", node2: "Prompt" };
      const globalVars = [makeGlobalVar("model")];

      const outputs = getUpstreamOutputs(
        "node2",
        nodes,
        edges,
        slugs,
        globalVars,
      );
      expect(outputs).toHaveLength(2);
      expect(outputs[0].nodeSlug).toBe("ChatInput");
      expect(outputs[1].nodeSlug).toBe(VARS_SLUG);
    });
  });
});
