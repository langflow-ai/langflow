import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import {
  type GraphViolation,
  manualViolations,
  previewFixesFor,
} from "@/hooks/flows/refused-restore";
import useApplyFlowToCanvas from "@/hooks/flows/use-apply-flow-to-canvas";
import useAlertStore from "@/stores/alertStore";
import useVersionPreviewStore from "@/stores/versionPreviewStore";
import type { FlowOperation } from "@/utils/flow-operations/apply";

/** One beat, then try again: long enough for the competing write to commit. */
const RETRY_BUSY_MS = 700;

export default function useRestoreVersion(flowId: string) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const clearPreview = useVersionPreviewStore((s) => s.clearPreview);
  const applyFlowToCanvas = useApplyFlowToCanvas();
  const [isRestoring, setIsRestoring] = useState(false);

  const restore = useCallback(
    async (
      versionId: string,
      options?: { saveDraft?: boolean; onSuccess?: () => void },
    ) => {
      const saveDraft = options?.saveDraft ?? true;
      setIsRestoring(true);
      let fixed: GraphViolation[] | null = null;
      try {
        // --- Phase 1: API call + canvas application ---
        // Errors here are shown to the user and abort the restore.
        const activate = (fixes?: FlowOperation[]) =>
          api.post(
            `${getURL("FLOWS")}/${flowId}/versions/${versionId}/activate`,
            fixes ? { fixes } : null,
            { params: { save_draft: saveDraft } },
          );
        // A restore that lands at the same moment as an autosave finds the row
        // locked. Nothing is wrong with either write, so the second attempt is
        // the answer rather than telling the person the restore failed.
        const send = async (fixes?: FlowOperation[]) => {
          try {
            return await activate(fixes);
            // biome-ignore lint/suspicious/noExplicitAny: axios error shape
          } catch (busy: any) {
            if (busy?.response?.status !== 503) throw busy;
            await new Promise((resolve) => setTimeout(resolve, RETRY_BUSY_MS));
            return activate(fixes);
          }
        };
        // A version whose edges break rules only the editor can fix is refused
        // with them; it is sent once more with the fixes its preview shows for
        // those edges (see refused-restore).
        let response: Awaited<ReturnType<typeof activate>>;
        try {
          response = await send();
        } catch (err) {
          fixed = manualViolations(err);
          if (!fixed) throw err;
          const fixes = previewFixesFor(fixed);
          if (fixes.length === 0) throw err;
          response = await send(fixes);
        }
        const updatedFlow = response.data;

        if (!updatedFlow.data) {
          throw new Error("Restored version contains no flow data");
        }

        queryClient.invalidateQueries({ queryKey: ["useGetFlowVersions"] });
        applyFlowToCanvas(updatedFlow);
        // biome-ignore lint/suspicious/noExplicitAny: legacy
      } catch (err: any) {
        const apiDetail = err?.response?.data?.detail;
        const message =
          apiDetail?.message ?? apiDetail ?? err?.message ?? "Unknown error";
        setErrorData({
          title: t("errors.failedToRestoreVersion"),
          list: [message],
        });
        setIsRestoring(false);
        return;
      }

      // --- Phase 2: Post-restore cleanup ---
      // The restore succeeded. Errors here are logged but should not
      // undo the restore or show a misleading "failed to restore" toast.
      try {
        useVersionPreviewStore.setState({ didRestore: true });
        clearPreview();
        setSuccessData(
          fixed
            ? {
                title: t("flowHistory.restore.withoutBrokenConnections"),
                list: fixed.map((violation) => violation.message),
              }
            : { title: t("success.versionRestored") },
        );
        options?.onSuccess?.();
      } catch (err) {
        console.error("useRestoreVersion: post-restore cleanup failed", err);
      } finally {
        setIsRestoring(false);
      }
    },
    [
      flowId,
      queryClient,
      applyFlowToCanvas,
      clearPreview,
      setSuccessData,
      setErrorData,
    ],
  );

  return { restore, isRestoring };
}
