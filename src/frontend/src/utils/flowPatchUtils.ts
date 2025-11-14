import type { Operation } from "fast-json-patch";
import { create } from "jsondiffpatch";
import { format as formatJsonPatch } from "jsondiffpatch/formatters/jsonpatch";
import type { FlowType } from "@/types/flow";

/**
 * Smart differ for flows that handles ID'd arrays (nodes/edges) efficiently.
 *
 * Uses jsondiffpatch with objectHash to compare arrays by ID instead of index.
 * This generates minimal operations (2-3 ops) instead of hundreds when removing nodes.
 *
 * Example: Removing a node generates ~2 operations vs ~225 with index-based diffing.
 */

// Create jsondiffpatch instance configured for flow data
const flowDiffer = create({
  objectHash: (obj: any) => {
    // Use 'id' field to identify nodes and edges
    return obj.id || JSON.stringify(obj);
  },
  arrays: {
    detectMove: true, // Detect when items move within array
    includeValueOnMove: false, // Don't include full value when item moves
  },
  textDiff: {
    minLength: 1000, // Only diff large strings (not relevant for flow data)
  },
});

/**
 * Compare two flow objects and generate RFC 6902 JSON Patch operations.
 * Uses ID-aware array diffing for nodes and edges.
 */
export function compareFlows(
  oldFlow: Partial<FlowType>,
  newFlow: Partial<FlowType>,
): Operation[] {
  // Generate jsondiffpatch delta
  const delta = flowDiffer.diff(oldFlow, newFlow);

  if (!delta) {
    return []; // No changes
  }

  // Convert delta to RFC 6902 JSON Patch format
  const patchOperations = formatJsonPatch(delta);

  return patchOperations as Operation[];
}
