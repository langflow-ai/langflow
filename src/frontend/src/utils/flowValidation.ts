/**
 * Flow Validation Utilities
 *
 * This file contains all validation logic for flow publishing.
 * Easy to modify - just update the constants or add/remove validation functions.
 */

import { AllNodeType, EdgeType, NodeDataType } from "@/types/flow";

// ============================================
// CONFIGURATION - Easy to modify these
// ============================================

/** Input node types - Add/remove types here as needed */
const INPUT_NODE_TYPES = new Set([
  'BlobStorage',
  'ChatInput',
  'FilePath',
  'KnowledgeHub',
  'TextInput'
]);

/** Output node types - Add/remove types here as needed */
const OUTPUT_NODE_TYPES = new Set([
  'ChatOutput',
  'TextOutput'
]);

// ============================================
// HELPER FUNCTIONS - Simple utilities
// ============================================

/**
 * Check if a node is an input node
 */
function isInputNode(node: AllNodeType): boolean {
  return INPUT_NODE_TYPES.has(node.data.type);
}

/**
 * Check if a node is an output node
 */
function isOutputNode(node: AllNodeType): boolean {
  return OUTPUT_NODE_TYPES.has(node.data.type);
}

/**
 * Get all start nodes (nodes with no incoming edges)
 */
function getStartNodes(nodes: AllNodeType[], edges: EdgeType[]): AllNodeType[] {
  const nodesWithIncomingEdges = new Set(edges.map(edge => edge.target));
  return nodes.filter(node =>
    node.type !== "noteNode" && !nodesWithIncomingEdges.has(node.id)
  );
}

/**
 * Get all end nodes (nodes with no outgoing edges)
 */
function getEndNodes(nodes: AllNodeType[], edges: EdgeType[]): AllNodeType[] {
  const nodesWithOutgoingEdges = new Set(edges.map(edge => edge.source));
  return nodes.filter(node =>
    node.type !== "noteNode" && !nodesWithOutgoingEdges.has(node.id)
  );
}

/**
 * Check if there's a path from start nodes to any output node
 * Uses simple BFS (Breadth-First Search) algorithm
 */
function canReachOutputNode(nodes: AllNodeType[], edges: EdgeType[]): boolean {
  const startNodes = getStartNodes(nodes, edges);
  const outputNodes = nodes.filter(isOutputNode);

  if (startNodes.length === 0 || outputNodes.length === 0) {
    return false;
  }

  // Build adjacency map (which nodes connect to which)
  const adjacencyMap = new Map<string, string[]>();
  edges.forEach(edge => {
    if (!edge.source) return;
    if (!adjacencyMap.has(edge.source)) {
      adjacencyMap.set(edge.source, []);
    }
    if (edge.target) {
      adjacencyMap.get(edge.source)?.push(edge.target);
    }
  });

  // Check if any start node can reach any output node
  for (const startNode of startNodes) {
    const visited = new Set<string>();
    const queue = [startNode.id];

    while (queue.length > 0) {
      const currentId = queue.shift()!;

      // Found an output node!
      if (outputNodes.some(n => n.id === currentId)) {
        return true;
      }

      if (visited.has(currentId)) continue;
      visited.add(currentId);

      // Add connected nodes to queue
      const connectedNodes = adjacencyMap.get(currentId) || [];
      queue.push(...connectedNodes);
    }
  }

  return false;
}

// ============================================
// VALIDATION FUNCTIONS - Each checks one thing
// ============================================

/**
 * Validate: Flow must have at least 2 nodes
 */
function validateMinimumNodes(nodes: AllNodeType[]): string[] {
  const errors: string[] = [];

  if (nodes.length < 2) {
    errors.push("The flow must contain at least 2 nodes.");
  }

  return errors;
}

/**
 * Validate: All nodes must be connected
 */
function validateAllNodesConnected(nodes: AllNodeType[], edges: EdgeType[]): string[] {
  const errors: string[] = [];

  const hasDisconnectedNode = nodes.some(node =>
    node.type !== "noteNode" &&
    !edges.some(edge => edge.target === node.id) &&
    !edges.some(edge => edge.source === node.id)
  );

  if (hasDisconnectedNode) {
    errors.push("All nodes must be connected. Please ensure all nodes in the flow are connected.");
  }

  return errors;
}

/**
 * Validate: Flow must have at least one output node
 */
function validateOutputNodeExists(nodes: AllNodeType[]): string[] {
  const errors: string[] = [];

  const hasOutputNode = nodes.some(isOutputNode);

  if (!hasOutputNode) {
    errors.push("The flow must have at least one output component (ChatOutput or TextOutput).");
  }

  return errors;
}

/**
 * Validate: End nodes should be output nodes
 */
function validateOutputNodesAtEnd(nodes: AllNodeType[], edges: EdgeType[]): string[] {
  const errors: string[] = [];

  const endNodes = getEndNodes(nodes, edges);
  const nonOutputEndNodes = endNodes.filter(node => !isOutputNode(node));

  if (nonOutputEndNodes.length > 0) {
    errors.push("The flow must end with an output component (ChatOutput or TextOutput).");
  }

  return errors;
}

/**
 * Validate: All required fields must be filled (except for input nodes)
 */
function validateRequiredFields(nodes: AllNodeType[], edges: EdgeType[]): string[] {
  const errors: string[] = [];

  // Build a map of which fields are connected via edges
  const targetFieldMap = new Map<string, string[]>();
  edges.forEach(edge => {
    if (!edge.target) return;
    const fieldName = edge.data?.targetHandle?.fieldName ?? '';
    if (!targetFieldMap.has(edge.target)) {
      targetFieldMap.set(edge.target, []);
    }
    targetFieldMap.get(edge.target)?.push(fieldName);
  });

  // Check each non-input node
  const nodesWithMissingFields = nodes.filter(node => {
    // Skip note nodes and input nodes
    if (node.type === "noteNode" || isInputNode(node)) {
      return false;
    }

    const nodeData = node.data as NodeDataType;
    const template = nodeData.node?.template;

    if (!template) return false;

    // Check if any required field is empty and not connected
    const connectedFields = targetFieldMap.get(node.id) || [];

    return Object.values(template).some((field: any) => {
      return (
        field.name &&
        field.show &&
        !field.advanced &&
        field.required &&
        !field.value &&
        !connectedFields.includes(field.name)
      );
    });
  });

  if (nodesWithMissingFields.length > 0) {
    errors.push(
      "All required fields must be filled. Please check that all components have their required fields configured properly."
    );
  }

  return errors;
}

/**
 * Validate: Output nodes must be reachable from start nodes
 */
function validateOutputNodesReachable(nodes: AllNodeType[], edges: EdgeType[]): string[] {
  const errors: string[] = [];

  if (!canReachOutputNode(nodes, edges)) {
    errors.push(
      "Output nodes must be reachable from the start of the flow. Please ensure there's a valid path from start to output."
    );
  }

  return errors;
}

/**
 * Get all Genesis Prompt Template nodes with their version status
 * Returns info about prompts that are in Draft or Pending status
 */
export function getPromptTemplateNodes(nodes: AllNodeType[]): {
  promptId: string;
  promptName: string;
  version: number;
  status: string;
}[] {
  const promptNodes: {
    promptId: string;
    promptName: string;
    version: number;
    status: string;
  }[] = [];

  nodes.forEach((node) => {
    const nodeData = node.data as NodeDataType;
    // Check if this is a Genesis Prompt Template node
    if (nodeData.type === "Genesis Prompt Template" || nodeData.node?.display_name === "Genesis Prompt Template") {
      const template = nodeData.node?.template;
      if (template) {
        const savedPrompt = template.saved_prompt?.value;
        const promptVersion = template.prompt_version?.value;
        
        if (savedPrompt && promptVersion) {
          // Parse version info from the formatted string like "v1 (Latest) [Draft]"
          const versionMatch = promptVersion.match(/v(\d+)/);
          const statusMatch = promptVersion.match(/\[(Draft|Pending)\]/i);
          
          if (versionMatch) {
            promptNodes.push({
              promptId: savedPrompt,
              promptName: savedPrompt,
              version: parseInt(versionMatch[1], 10),
              status: statusMatch ? statusMatch[1].toUpperCase() : "PUBLISHED",
            });
          }
        }
      }
    }
  });

  return promptNodes;
}

/**
 * Validate: All prompt templates must be published (not Draft or Pending)
 */
function validatePromptTemplatesPublished(nodes: AllNodeType[]): string[] {
  const errors: string[] = [];
  
  const promptNodes = getPromptTemplateNodes(nodes);
  const unpublishedPrompts = promptNodes.filter(
    (p) => p.status === "DRAFT" || p.status === "PENDING" || p.status === "PENDING_APPROVAL"
  );

  if (unpublishedPrompts.length > 0) {
    const promptList = unpublishedPrompts
      .map((p) => `"${p.promptName}" (v${p.version} - ${p.status})`)
      .join(", ");
    errors.push(
      `The following prompt templates are not published and must be approved before submitting the workflow: ${promptList}`
    );
  }

  return errors;
}

// ============================================
// MAIN VALIDATION FUNCTION
// ============================================

/**
 * Validate a flow before publishing
 *
 * Returns an array of error messages. Empty array means validation passed.
 *
 * To enable/disable validations, just comment out the lines below.
 * To add new validations, create a new function above and call it here.
 *
 * @param nodes - Array of flow nodes
 * @param edges - Array of flow edges
 * @returns Array of error messages (empty if valid)
 */
export function validateFlowForPublish(
  nodes: AllNodeType[],
  edges: EdgeType[]
): string[] {
  const errors: string[] = [];

  // Run each validation - easy to enable/disable by commenting out
  errors.push(...validateMinimumNodes(nodes));
  errors.push(...validateAllNodesConnected(nodes, edges));
  errors.push(...validateOutputNodeExists(nodes));
  errors.push(...validateOutputNodesAtEnd(nodes, edges));
  // errors.push(...validateRequiredFields(nodes, edges));
  errors.push(...validateOutputNodesReachable(nodes, edges));
  errors.push(...validatePromptTemplatesPublished(nodes));

  // Return all errors found
  return errors;
}

// ============================================
// EXPORTS - For use in other files
// ============================================

export {
  isInputNode,
  isOutputNode,
  getStartNodes,
  getEndNodes,
};
