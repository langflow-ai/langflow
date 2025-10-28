import { applyPatch, compare, validate } from "fast-json-patch";
import type { PatchOperation } from "@/controllers/API/queries/flows/use-patch-json-patch-flow";

/**
 * Re-export fast-json-patch functions for advanced use cases
 */
export { compare, applyPatch, validate };

/**
 * Helper utilities for creating JSON Patch operations (RFC 6902)
 *
 * NOTE: For automatic diff generation, prefer using `compare(oldObj, newObj)` from fast-json-patch
 * These helpers are useful when you need to manually construct specific operations.
 */

/**
 * Creates a 'replace' operation to update a field value
 * @param path - JSON Pointer path (e.g., "/name", "/data/nodes/0")
 * @param value - The new value
 * @returns PatchOperation object
 */
export function createReplaceOperation(
  path: string,
  value: any,
): PatchOperation {
  return {
    op: "replace",
    path,
    value,
  };
}

/**
 * Creates an 'add' operation to add a new field or array element
 * @param path - JSON Pointer path (e.g., "/tags", "/data/nodes/-")
 * @param value - The value to add
 * @returns PatchOperation object
 */
export function createAddOperation(path: string, value: any): PatchOperation {
  return {
    op: "add",
    path,
    value,
  };
}

/**
 * Creates a 'remove' operation to delete a field or array element
 * @param path - JSON Pointer path (e.g., "/tags/0", "/endpoint_name")
 * @returns PatchOperation object
 */
export function createRemoveOperation(path: string): PatchOperation {
  return {
    op: "remove",
    path,
  };
}

/**
 * Creates a 'move' operation to move a value from one location to another
 * @param from - Source JSON Pointer path
 * @param path - Destination JSON Pointer path
 * @returns PatchOperation object
 */
export function createMoveOperation(
  from: string,
  path: string,
): PatchOperation {
  return {
    op: "move",
    from,
    path,
  };
}

/**
 * Creates a 'copy' operation to copy a value from one location to another
 * @param from - Source JSON Pointer path
 * @param path - Destination JSON Pointer path
 * @returns PatchOperation object
 */
export function createCopyOperation(
  from: string,
  path: string,
): PatchOperation {
  return {
    op: "copy",
    from,
    path,
  };
}

/**
 * Creates a 'test' operation to verify a value before applying other operations
 * @param path - JSON Pointer path
 * @param value - The expected value
 * @returns PatchOperation object
 */
export function createTestOperation(path: string, value: any): PatchOperation {
  return {
    op: "test",
    path,
    value,
  };
}

/**
 * Example usage:
 *
 * // Automatic diff generation (recommended):
 * import { compare } from "@/utils/json-patch-utils";
 * const operations = compare(oldFlow, newFlow);
 *
 * // Manual operation construction:
 * import { createReplaceOperation } from "@/utils/json-patch-utils";
 * const operations = [
 *   createReplaceOperation("/name", "Updated Flow Name"),
 *   createReplaceOperation("/description", "Updated description"),
 * ];
 *
 * // Use the operations:
 * const { mutate } = usePatchJsonPatchFlow();
 * mutate({ id: flowId, operations });
 */
