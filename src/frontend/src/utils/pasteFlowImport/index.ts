/**
 * Shared helpers for importing flow JSON from clipboard (paste).
 * Used by MainPage (new flow) and FlowPage (paste into current flow).
 *
 * Public API: getPastedFlowFile, getFlowFilesFromClipboard, isEditablePasteTarget.
 */

export { getFlowFilesFromClipboard, getPastedFlowFile } from "./parsing";
export { isEditablePasteTarget } from "./validation";
