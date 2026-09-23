import { ENABLE_INTEGRATIONS } from "@/customization/feature-flags";
import { InputFieldType } from "@/types/api";
import { isConnectionRefField } from "@/utils/connection-ref-gate";

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

/**
 * With ENABLE_INTEGRATIONS OFF there is no connection picker, so a
 * `connection_ref` field would show a label with an empty control. Keep those
 * fields off the canvas and out of the Inspector Panel in that case.
 */
function isUnrenderedConnectionRef(template: InputFieldType | undefined) {
  return !ENABLE_INTEGRATIONS && isConnectionRefField(template);
}

export function isHidden(template: InputFieldType, isToolMode: boolean) {
  return (
    !template?.show ||
    (template?.tool_mode && isToolMode) ||
    isUnrenderedConnectionRef(template)
  );
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
 * Determines if a parameter is manageable in the Inspector Panel (LE-1810).
 * The panel lists every manageable parameter regardless of canvas visibility —
 * `advanced` is the add/remove axis, not a listing filter. Connected fields
 * stay listed (their actions are disabled by the row).
 */
export function isManageableParameter(
  templateField: string,
  template: InputFieldType | undefined,
  isToolMode: boolean | undefined,
) {
  if (!template) return false;
  if (isInternalField(templateField)) return false;
  if (!template.show) return false;
  if (isUnrenderedConnectionRef(template)) return false;
  if (isCodeField(templateField, template)) return false;
  if (isToolModeEnabled(template) && isToolMode) return false;
  if (template.readonly) return false;
  return true;
}
