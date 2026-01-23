import { LANGFLOW_SUPPORTED_TYPES } from "@/constants/constants";

export type DisplayHandleTemplate = {
  type?: string;
  input_types?: string[];
  refresh_button?: boolean;
  tool_mode?: boolean;
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

  return !!(
    (!LANGFLOW_SUPPORTED_TYPES.has(type ?? "") ||
      (optionalHandle && optionalHandle.length > 0)) &&
    !(isToolMode && template.tool_mode) &&
    (!hasRefreshButton || isModelInput) &&
    (!isModelInput || hasInputTypes)
  );
};

export type FindPrimaryInputTemplate = DisplayHandleTemplate & {
  show?: boolean;
  advanced?: boolean;
};

export type FindPrimaryInputResult = {
  displayHandleMap: Map<string, boolean>;
  primaryInputFieldName: string | null;
};

/**
 * Finds the primary input field (first field with a displayable handle)
 * and builds a map of which fields should display handles.
 *
 * @param shownTemplateFields - Array of field names that are already filtered to shown fields
 * @param templates - Record of field name to template configuration
 * @param isToolMode - Whether the component is in tool mode
 */
export const findPrimaryInput = (
  shownTemplateFields: string[],
  templates: Record<string, FindPrimaryInputTemplate>,
  isToolMode: boolean,
): FindPrimaryInputResult => {
  const handleMap = new Map<string, boolean>();
  let primaryField: string | null = null;

  for (const templateField of shownTemplateFields) {
    const template = templates[templateField];
    if (!template) continue;

    const hasHandle = computeDisplayHandle(
      template,
      isToolMode && !!template.tool_mode,
    );
    handleMap.set(templateField, hasHandle);

    // First field with a handle becomes the primary input
    if (hasHandle && primaryField === null) {
      primaryField = templateField;
    }
  }

  return { displayHandleMap: handleMap, primaryInputFieldName: primaryField };
};
