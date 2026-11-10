import { useState } from "react";
import { useTranslation } from "react-i18next";
import { usePostCreateSnapshot } from "@/controllers/API/queries/flow-version/use-post-create-snapshot";
import { fetchAndAdoptServerVersion } from "@/hooks/flows/conflict-actions";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import useFlowConflictStore from "@/stores/flowConflictStore";
import useFlowStore from "@/stores/flowStore";
import { clearConflictDraft } from "@/utils/conflict-draft";

/**
 * Give up your own edits and take the server's version, keeping yours recoverable.
 *
 * Offered from two places — the banner and the review dialog — and the promise it
 * makes is the same in both: nothing is thrown away that is not first in the
 * version history. One implementation so that promise cannot drift between them.
 */
export function useTakeLatestVersion() {
  const { t } = useTranslation();
  const { mutateAsync: archiveMyVersion } = usePostCreateSnapshot();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const clearConflict = useFlowConflictStore((state) => state.clearConflict);
  const [isTaking, setIsTaking] = useState(false);

  /** The canvas exactly as this person left it, read at the moment they leave. */
  const captureMyCanvas = () => {
    const live = useFlowStore.getState();
    return {
      nodes: live.nodes,
      edges: live.edges,
      viewport: live.reactFlowInstance?.getViewport() ?? {
        x: 0,
        y: 0,
        zoom: 1,
      },
    } as unknown as Record<string, unknown>;
  };

  const takeLatestVersion = async (flowId: string): Promise<boolean> => {
    setIsTaking(true);
    try {
      // Archived before anything is thrown away, and abandoned if it cannot be:
      // the action promises this work stays recoverable, and a discard that
      // silently failed to keep that promise is the one outcome to prevent.
      try {
        await archiveMyVersion({
          flowId,
          description: t("multiEdit.dialog.discardArchiveLabel"),
          data: captureMyCanvas(),
        });
      } catch {
        setErrorData({ title: t("multiEdit.dialog.discardArchiveFailed") });
        return false;
      }

      const adopted = await fetchAndAdoptServerVersion(flowId);
      if (!adopted) {
        setErrorData({ title: t("multiEdit.dialog.overwriteFailed") });
        return false;
      }
      // Safe to drop now: the same work is in version history.
      clearConflictDraft(useAuthStore.getState().userData?.id, flowId);
      clearConflict();
      setSuccessData({ title: t("multiEdit.dialog.discardSucceeded") });
      return true;
    } finally {
      setIsTaking(false);
    }
  };

  return { takeLatestVersion, isTaking };
}
