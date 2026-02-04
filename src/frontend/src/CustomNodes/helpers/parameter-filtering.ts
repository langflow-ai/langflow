import { InputFieldType } from "@/types/api";

export function isInternalField(templateField: string) {
  return templateField.charAt(0) === "_";
}

export function isCodeField(templateField: string, template: InputFieldType) {
  return (
    (templateField === "code" && template.type === "code") ||
    (templateField.includes("code") && template.proxy)
  );
}

export function isHandleInput(template: InputFieldType) {
  return template?.type === "other";
}

export function isToolModeEnabled(template: InputFieldType) {
  return template?.tool_mode;
}

export function isHidden(template: InputFieldType, isToolMode: boolean) {
  return !template?.show || (template?.tool_mode && isToolMode);
}

/**
 * Determines if a field should be considered for rendering on the canvas.
 * This includes fields that might be visually hidden but are still rendered for logic.
 */
export function isCanvasVisible(template: InputFieldType, isToolMode: boolean) {
  if (isHidden(template, isToolMode)) return false;
  if (template?.advanced) return false;
  return true;
}

/**
 * Determines if a field should be shown in the InspectionPanel.
 */
export function shouldRenderInspectionPanelField(
  templateField: string,
  template: InputFieldType,
  isToolMode: boolean | undefined,
) {
  if (isInternalField(templateField)) return false;
  if (!template?.show) return false;
  if (isCodeField(templateField, template)) return false;
  if (isToolModeEnabled(template) && isToolMode) return false;
  // Only show advanced fields in the inspector panel
  if (!template?.advanced) return false;

  return true;
}
