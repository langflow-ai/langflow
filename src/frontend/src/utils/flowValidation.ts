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
 * Genesis Prompt Template node info extracted from flow
 */
export interface GenesisPromptNodeInfo {
  promptId: string;
  promptName: string;
  version: number;
  status: string;
}

/**
 * Get all Genesis Prompt Template nodes with their version info.
 * 
 * This extracts prompt_id, version, and status from the node template.
 * The template stores these values directly (prompt_id, prompt_version, version_status)
 * which are more reliable than parsing the dropdown display strings.
 */
export function getPromptTemplateNodes(nodes: AllNodeType[]): GenesisPromptNodeInfo[] {
  const promptNodes: GenesisPromptNodeInfo[] = [];

  nodes.forEach((node) => {
    const nodeData = node.data as NodeDataType;
    // Check if this is a Genesis Prompt Template node
    if (nodeData.type === "Genesis Prompt Template" || nodeData.node?.display_name === "Genesis Prompt Template") {
      const template = nodeData.node?.template;
      if (template) {
        // Get prompt_id from saved_prompt field
        const savedPrompt = template.saved_prompt?.value;
        
        // Get version number - prefer the numeric prompt_version stored in template metadata
        // over parsing the dropdown string
        const templatePromptVersion = template.template?.prompt_version;
        const versionStatus = template.template?.version_status;
        const promptVersionDropdown = template.prompt_version?.value;
        
        if (savedPrompt) {
          let version: number | null = null;
          let status = "UNKNOWN";
          
          // First try to get version from template metadata (most reliable)
          if (typeof templatePromptVersion === "number") {
            version = templatePromptVersion;
          } else if (promptVersionDropdown) {
            // Fallback: parse version from dropdown string like "v1 - DRAFT (Latest)"
            const versionMatch = promptVersionDropdown.match(/v(\d+)/);
            if (versionMatch) {
              version = parseInt(versionMatch[1], 10);
            }
          }
          
          // Get status from template metadata or parse from dropdown
          if (versionStatus) {
            status = versionStatus.toUpperCase();
          } else if (promptVersionDropdown) {
            // Parse status from dropdown string
            if (promptVersionDropdown.includes("DRAFT")) {
              status = "DRAFT";
            } else if (promptVersionDropdown.includes("PENDING")) {
              status = "PENDING_APPROVAL";
            } else if (promptVersionDropdown.includes("PUBLISHED")) {
              status = "PUBLISHED";
            } else if (promptVersionDropdown.includes("REJECTED")) {
              status = "REJECTED";
            }
          }
          
          if (version !== null) {
            promptNodes.push({
              promptId: savedPrompt,
              promptName: savedPrompt,
              version,
              status,
            });
          }
        }
      }
    }
  });

  return promptNodes;
}

/**
 * Validate: All Genesis Prompt Template nodes must use published prompt versions.
 * 
 * This validation only runs if there are Genesis Prompt Template components in the flow.
 * It checks each prompt template node and verifies the selected version is PUBLISHED.
 */
function validatePromptTemplatesPublished(nodes: AllNodeType[]): string[] {
  const errors: string[] = [];
  
  // Get all Genesis Prompt Template nodes from the flow
  const promptNodes = getPromptTemplateNodes(nodes);
  
  // Only validate if there are Genesis Prompt Template components in the flow
  if (promptNodes.length === 0) {
    return errors;
  }

  // Check each prompt node - status must be PUBLISHED
  const unpublishedPrompts = promptNodes.filter((p) => p.status !== "PUBLISHED");

  if (unpublishedPrompts.length > 0) {
    const promptList = unpublishedPrompts
      .map((p) => `"${p.promptName}" (v${p.version})`)
      .join(", ");
    errors.push(
      `Prompt templates used in this agent must be published. The following are not published: ${promptList}`
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
