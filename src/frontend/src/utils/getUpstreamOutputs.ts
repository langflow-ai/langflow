import type { Edge, Node } from "@xyflow/react";
import type { UpstreamOutput } from "@/types/references";

/**
 * Output types that can be meaningfully referenced as text content.
 *
 * These types can be converted to string representations when resolving @references:
 * - Message: Extracts the `.text` property
 * - str/string/text/Text: Used directly as string
 * - Data: JSON stringified from the `.data` property
 * - int/float/number: Converted to string representation
 * - bool/boolean: Converted to "true" or "false"
 *
 * Types NOT included (and why):
 * - Tool: Not meaningful as text content
 * - Agent: Not meaningful as text content
 * - Embeddings: Binary/vector data, not text
 * - LanguageModel: Object reference, not text
 */
const REFERENCEABLE_TYPES = new Set([
  "Message",
  "str",
  "string",
  "text",
  "Text",
  "Data",
  "int",
  "float",
  "number",
  "bool",
  "boolean",
]);

/**
 * Check if an output type can be meaningfully referenced as text content.
 *
 * @param type - The output type to check
 * @returns True if the type can be converted to text for reference resolution
 */
function isReferenceableType(type: string): boolean {
  return REFERENCEABLE_TYPES.has(type);
}

/**
 * Collect all outputs from upstream nodes that can be referenced.
 *
 * This function traverses the graph backwards from the given node to find all
 * upstream nodes (nodes connected via edges that point to this node, recursively).
 * It then collects all outputs from those nodes that have types suitable for
 * text interpolation.
 *
 * @param nodeId - The ID of the current node
 * @param nodes - All nodes in the flow
 * @param edges - All edges in the flow
 * @param slugs - Map of node IDs to their reference slugs (e.g., "ChatInput", "TextSplitter")
 * @returns Array of upstream outputs that can be referenced using @NodeSlug.outputName syntax
 *
 * @example
 * ```ts
 * const outputs = getUpstreamOutputs("node3", nodes, edges, nodeReferenceSlugs);
 * // Returns outputs from all nodes connected upstream of node3
 * // e.g., [{ nodeSlug: "ChatInput", outputName: "message", outputType: "Message", ... }]
 * ```
 */
export function getUpstreamOutputs(
  nodeId: string,
  nodes: Node[],
  edges: Edge[],
  slugs: Record<string, string>,
): UpstreamOutput[] {
  const outputs: UpstreamOutput[] = [];
  const visited = new Set<string>();

  // Recursively find all upstream nodes
  function collectUpstreamNodes(currentNodeId: string): string[] {
    if (visited.has(currentNodeId)) return [];
    visited.add(currentNodeId);

    const upstreamIds: string[] = [];

    // Find all edges where target is current node
    const incomingEdges = edges.filter((edge) => edge.target === currentNodeId);

    for (const edge of incomingEdges) {
      const sourceId = edge.source;
      upstreamIds.push(sourceId);
      // Recursively get upstream nodes of this source
      upstreamIds.push(...collectUpstreamNodes(sourceId));
    }

    return upstreamIds;
  }

  // Get all unique upstream node IDs
  const allUpstreamIds = Array.from(new Set(collectUpstreamNodes(nodeId)));

  // For each upstream node, get its outputs
  for (const sourceId of allUpstreamIds) {
    const sourceNode = nodes.find((n) => n.id === sourceId);
    if (!sourceNode) continue;

    const nodeData = sourceNode.data?.node as
      | {
          display_name?: string;
          outputs?: Array<{
            name: string;
            display_name?: string;
            types?: string[];
          }>;
        }
      | undefined;
    if (!nodeData) continue;

    const nodeOutputs = nodeData.outputs || [];
    const nodeSlug = slugs[sourceId] || "Node";
    const nodeName = nodeData.display_name || "Node";

    for (const output of nodeOutputs) {
      const outputType = output.types?.[0] || "Any";
      // Only include outputs with types that can be meaningfully referenced as text
      if (!isReferenceableType(outputType)) continue;

      outputs.push({
        nodeId: sourceId,
        nodeSlug,
        nodeName,
        outputName: output.name,
        outputDisplayName: output.display_name || output.name,
        outputType,
      });
    }
  }

  return outputs;
}
