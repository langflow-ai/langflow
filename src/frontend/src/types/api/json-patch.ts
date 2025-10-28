/**
 * JSON Patch operation types as defined in RFC 6902
 */
export type JsonPatchOperationType =
  | "add"
  | "remove"
  | "replace"
  | "move"
  | "copy"
  | "test";

/**
 * JSON Patch operation as defined in RFC 6902
 */
export interface JsonPatchOperation {
  /**
   * The operation to perform
   */
  op: JsonPatchOperationType;

  /**
   * JSON Pointer to the target location
   */
  path: string;

  /**
   * The value to add, replace, or test against (null is a valid value)
   */
  value?: any;

  /**
   * JSON Pointer to the source location for move/copy operations
   */
  from?: string;
}

/**
 * JSON Patch document as defined in RFC 6902
 */
export interface JsonPatch {
  /**
   * List of patch operations to apply
   */
  operations: JsonPatchOperation[];
}

/**
 * Response from a JSON Patch operation
 */
export interface JsonPatchResponse {
  /**
   * Whether the patch was successful
   */
  success: boolean;

  /**
   * When the resource was updated
   */
  updated_at: string;

  /**
   * List of fields that were updated by the patch
   */
  updated_fields: string[];

  /**
   * Number of operations that were applied
   */
  operations_applied: number;
}

// Made with Bob
