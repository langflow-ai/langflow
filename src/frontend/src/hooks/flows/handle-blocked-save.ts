import i18n from "@/i18n";
import useAlertStore from "@/stores/alertStore";
import useFlowConflictStore from "@/stores/flowConflictStore";
import { FlowSaveBlockedError } from "./save-blocked-error";

/**
 * Turns a save that never happened into something the person can act on.
 *
 * Every caller that announces success has to ask this first. While a blocked save
 * resolved quietly, Ctrl+S and the flow settings dialog both reported "saved" over
 * a write the store had refused to even attempt — the one moment where a false
 * reassurance costs someone their work.
 *
 * Returns true when the error was a blocked save and has been handled.
 */
export const handleBlockedSave = (error: unknown): boolean => {
  if (!(error instanceof FlowSaveBlockedError)) return false;

  const { conflict, openDialog } = useFlowConflictStore.getState();
  if (conflict?.flowId === error.flowId) {
    openDialog();
    return true;
  }
  // No conflict left to resolve means the flow was duplicated out of one, and
  // writing to it is over for this session. Saying so beats a silent no-op.
  useAlertStore.getState().setErrorData({
    title: i18n.t("multiEdit.error.saveBlocked"),
  });
  return true;
};
