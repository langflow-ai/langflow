/**
 * Client for interacting with the enhanced registry API
 */
import { BASE_URL_API } from "../../../constants/constants";
import { apiRequest } from "../../../controllers/API/helpers/request";
import { 
  EnhancedRegistry, 
  EnhancedNodeEntry, 
  ConnectionSuggestion 
} from "./types";

/**
 * Get the complete enhanced registry
 */
export async function getEnhancedRegistry(): Promise<EnhancedRegistry> {
  const response = await apiRequest<EnhancedRegistry>({
    url: `${BASE_URL_API}/monkey-agent/registry`,
    method: "GET",
  });
  return response;
}

/**
 * Get a specific node entry from the enhanced registry
 */
export async function getNodeRegistryEntry(nodeId: string): Promise<EnhancedNodeEntry> {
  const response = await apiRequest<EnhancedNodeEntry>({
    url: `${BASE_URL_API}/monkey-agent/registry/node/${nodeId}`,
    method: "GET",
  });
  return response;
}

/**
 * Get the type compatibility matrix
 */
export async function getTypeCompatibilityMatrix(): Promise<Record<string, string[]>> {
  const response = await apiRequest<Record<string, string[]>>({
    url: `${BASE_URL_API}/monkey-agent/registry/compatibility`,
    method: "GET",
  });
  return response;
}

/**
 * Get connection suggestions between two node types
 */
export async function getConnectionSuggestions(
  sourceId: string,
  targetId: string
): Promise<ConnectionSuggestion[]> {
  const response = await apiRequest<ConnectionSuggestion[]>({
    url: `${BASE_URL_API}/monkey-agent/connection/suggest`,
    method: "POST",
    body: { source_id: sourceId, target_id: targetId },
  });
  return response;
}
