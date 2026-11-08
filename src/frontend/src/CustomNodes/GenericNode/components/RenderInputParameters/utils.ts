import type { Edge } from "@xyflow/react";
import { LANGFLOW_SUPPORTED_TYPES } from "@/constants/constants";
import { isConnectionRefField } from "@/utils/connection-ref-gate";
import { scapedJSONStringfy } from "@/utils/reactflowUtils";

export type DisplayHandleTemplate = {
  type?: string;
  model_type?: string;
  input_types?: string[];
  refresh_button?: boolean;
  tool_mode?: boolean;
};

export type FindPrimaryInputTemplate = DisplayHandleTemplate & {
  show?: boolean;
  advanced?: boolean;
  proxy?: { field: string; id: string };
};

export type FindPrimaryInputResult = {
  displayHandleMap: Map<string, boolean>;
  primaryInputFieldName: string | null;
};

export const computeDisplayHandle = (
  template: DisplayHandleTemplate,
  isToolMode: boolean,
): boolean => {
  const type = template.type;
  const optionalHandle = template.input_types;
  const hasRefreshButton = template.refresh_button;
  const isModelInput = type === "model";
  const hasInputTypes =
    optionalHandle &&
    Array.isArray(optionalHandle) &&
    optionalHandle.length > 0;

  // A connection reference is set only through the connection picker; its
  // value must never come from an edge, so it never gets a handle.
  if (isConnectionRefField(template)) {
    return false;
  }

  // Model inputs always get a handle, except decision models, which take no
  // connections (the backend sends no input types for them).
  if (isModelInput) {
    return template.model_type !== "decision";
  }

  return !!(
    (!LANGFLOW_SUPPORTED_TYPES.has(type ?? "") ||
      (optionalHandle && optionalHandle.length > 0)) &&
    !(isToolMode && template.tool_mode) &&
    !hasRefreshButton
  );
};

export const findPrimaryInput = (
  shownTemplateFields: string[],
  templates: Record<string, FindPrimaryInputTemplate>,
  isToolMode: boolean,
  nodeId: string,
  edges: Edge[],
): FindPrimaryInputResult => {
  const handleMap = new Map<string, boolean>();
  let primaryField: string | null = null;
  let firstHandleField: string | null = null;

  for (const templateField of shownTemplateFields) {
    const template = templates[templateField];
    if (!template) continue;

    const hasHandle = computeDisplayHandle(
      template,
      isToolMode && !!template.tool_mode,
    );
    handleMap.set(templateField, hasHandle);

    // First field with a connected handle becomes the primary input
    if (hasHandle && primaryField === null) {
      // Build the handle ID the same way NodeInputField does
      const handleId = scapedJSONStringfy(
        template.proxy
          ? {
              inputTypes: template.input_types,
              type: template.type,
              id: nodeId,
              fieldName: templateField,
              proxy: template.proxy,
            }
          : {
              inputTypes: template.input_types,
              type: template.type,
              id: nodeId,
              fieldName: templateField,
            },
      );

      if (hasHandle && firstHandleField === null) {
        firstHandleField = templateField;
      }

      const isConnected = edges.some(
        (edge) => edge.target === nodeId && edge.targetHandle === handleId,
      );

      if (isConnected) {
        primaryField = templateField;
      }
    }
  }

  if (primaryField === null) {
    primaryField = firstHandleField;
  }

  return { displayHandleMap: handleMap, primaryInputFieldName: primaryField };
};
