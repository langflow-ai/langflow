/**
 * Utilities for enhanced node connections
 */
import useFlowStore from "../../../stores/flowStore";
import { useEnhancedRegistryStore } from "../registry/store";
import { getConnectionSuggestions } from "../registry/client";
import { scapedJSONStringfy } from "../../../utils/reactflowUtils";

/**
 * Helper to extract node type from ID
 */
export function getNodeTypeFromId(nodeId: string): string {
  const flowStore = useFlowStore.getState();
  const node = flowStore.nodes.find(n => n.id === nodeId);
  return node?.data?.node?.template_type || node?.type || "";
}

/**
 * Generate a source handle string using the enhanced registry
 */
export function createEnhancedSourceHandle(
  sourceNodeId: string,
  sourceFieldName: string
): string | null {
  const store = useEnhancedRegistryStore.getState();
  
  // Make sure the registry is loaded
  if (!store.isLoaded) {
    console.error("Enhanced registry not loaded");
    return null;
  }
  
  // Find the node in the registry
  const nodeType = getNodeTypeFromId(sourceNodeId);
  const nodeEntry = store.registry[nodeType];
  if (!nodeEntry) {
    console.error(`Node type ${nodeType} not found in registry`);
    return null;
  }
  
  // Get the output field
  const outputField = nodeEntry.outputs[sourceFieldName];
  if (!outputField) {
    console.error(`Output field ${sourceFieldName} not found in node ${nodeType}`);
    return null;
  }
  
  // Replace NODE_ID with actual ID in the handle format
  const handleFormat = outputField.connectionFormat.handleFormat.replace("NODE_ID", sourceNodeId);
  return handleFormat;
}

/**
 * Generate a target handle string using the enhanced registry
 */
export function createEnhancedTargetHandle(
  targetNodeId: string,
  targetFieldName: string
): string | null {
  const store = useEnhancedRegistryStore.getState();
  
  // Make sure the registry is loaded
  if (!store.isLoaded) {
    console.error("Enhanced registry not loaded");
    return null;
  }
  
  // Find the node in the registry
  const nodeType = getNodeTypeFromId(targetNodeId);
  const nodeEntry = store.registry[nodeType];
  if (!nodeEntry) {
    console.error(`Node type ${nodeType} not found in registry`);
    return null;
  }
  
  // Get the input field
  const inputField = nodeEntry.inputs[targetFieldName];
  if (!inputField) {
    console.error(`Input field ${targetFieldName} not found in node ${nodeType}`);
    return null;
  }
  
  // Replace NODE_ID with actual ID in the handle format
  const handleFormat = inputField.connectionFormat.handleFormat.replace("NODE_ID", targetNodeId);
  return handleFormat;
}

/**
 * Find compatible connections between two nodes
 */
export async function findCompatibleNodeConnections(
  sourceNodeId: string,
  targetNodeId: string
): Promise<{ sourceField: string; targetField: string; sourceHandle: string; targetHandle: string }[]> {
  // Get node types
  const sourceType = getNodeTypeFromId(sourceNodeId);
  const targetType = getNodeTypeFromId(targetNodeId);
  
  // Call the API to get connection suggestions
  try {
    const suggestions = await getConnectionSuggestions(sourceType, targetType);
    
    // Format for easy use
    return suggestions.map(suggestion => ({
      sourceField: suggestion.source_field,
      targetField: suggestion.target_field,
      sourceHandle: suggestion.source_handle.replace("NODE_ID", sourceNodeId),
      targetHandle: suggestion.target_handle.replace("NODE_ID", targetNodeId)
    }));
  } catch (error) {
    console.error("Error getting connection suggestions:", error);
    return [];
  }
}

/**
 * Create a connection between two nodes using the enhanced registry
 */
export async function connectNodesWithRegistry(
  sourceNodeId: string,
  targetNodeId: string,
  onConnect: Function
): Promise<{
  success: boolean;
  message: string;
  action: string;
  details?: any;
}> {
  console.log(`Connecting nodes with registry: ${sourceNodeId} → ${targetNodeId}`);
  
  // Get compatible connections
  const connections = await findCompatibleNodeConnections(sourceNodeId, targetNodeId);
  
  if (connections.length === 0) {
    return {
      success: false,
      message: "No compatible connections found between these nodes",
      action: "connection_failed"
    };
  }
  
  // Use the first suggested connection
  const connection = {
    source: sourceNodeId,
    sourceHandle: connections[0].sourceHandle,
    target: targetNodeId,
    targetHandle: connections[0].targetHandle
  };
  
  console.log("Creating connection:", connection);
  
  try {
    // Connect the nodes
    onConnect(connection);
    
    return {
      success: true,
      message: `Connected nodes: ${connections[0].sourceField} → ${connections[0].targetField}`,
      action: "connected_nodes",
      details: {
        sourceNodeId,
        targetNodeId,
        sourceField: connections[0].sourceField,
        targetField: connections[0].targetField
      }
    };
  } catch (error) {
    console.error("Error connecting nodes:", error);
    return {
      success: false,
      message: "Error connecting nodes: " + (error instanceof Error ? error.message : "Unknown error"),
      action: "connection_error"
    };
  }
}
