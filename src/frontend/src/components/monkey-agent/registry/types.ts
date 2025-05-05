/**
 * Type definitions for the enhanced registry
 */
export interface ConnectionFormat {
  fieldName: string;
  handleFormat: string;
}

export interface InputField {
  type: string[];
  displayName: string;
  required: boolean;
  connectionFormat: ConnectionFormat;
}

export interface OutputField {
  type: string[];
  displayName: string;
  connectionFormat: ConnectionFormat;
}

export interface EnhancedNodeEntry {
  id: string;
  displayName: string;
  description: string;
  category: string;
  inputs: {
    [fieldName: string]: InputField;
  };
  outputs: {
    [fieldName: string]: OutputField;
  };
}

export interface EnhancedRegistry {
  [nodeId: string]: EnhancedNodeEntry;
}

export interface ConnectionSuggestion {
  source_field: string;
  target_field: string;
  source_type: string;
  target_type: string;
  source_handle: string;
  target_handle: string;
}
