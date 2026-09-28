import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { v4 as uuidv4 } from "uuid";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import useApplyFlowToCanvas from "@/hooks/flows/use-apply-flow-to-canvas";
import useAlertStore from "@/stores/alertStore";
import useVersionPreviewStore from "@/stores/versionPreviewStore";

/**
 * Make an earlier point in the flow's history its current state.
 *
 * The server replays the history itself rather than taking the graph back
 * from the editor: what the editor previewed has its secrets removed, and
 * saving that would blank them. The restore is recorded as new history, so
 * the state it replaces stays one step back in the timeline.
 */
export default function useRestoreRevision(flowId: string) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const clearPreview = useVersionPreviewStore((s) => s.clearPreview);
  const applyFlowToCanvas = useApplyFlowToCanvas();
  const [isRestoring, setIsRestoring] = useState(false);

  const restore = useCallback(
    async (revision: number, options?: { onSuccess?: () => void }) => {
      setIsRestoring(true);
      try {
        const response = await api.post(
          `${getURL("FLOWS")}/${flowId}/revisions/${revision}/restore`,
          { request_id: uuidv4() },
        );
        queryClient.invalidateQueries({ queryKey: ["useGetFlowRevisions"] });
        queryClient.invalidateQueries({ queryKey: ["useGetFlowVersions"] });
        applyFlowToCanvas(response.data);
        // biome-ignore lint/suspicious/noExplicitAny: axios error shape
      } catch (err: any) {
        const detail = err?.response?.data?.detail;
        setErrorData({
          title: t("errors.failedToRestoreVersion"),
          list: [detail?.message ?? detail ?? err?.message ?? "Unknown error"],
        });
        setIsRestoring(false);
        return;
      }
      try {
        useVersionPreviewStore.setState({ didRestore: true });
        clearPreview();
        setSuccessData({ title: t("success.versionRestored") });
        options?.onSuccess?.();
      } finally {
        setIsRestoring(false);
      }
    },
    [
      flowId,
      queryClient,
      applyFlowToCanvas,
      clearPreview,
      setErrorData,
      setSuccessData,
      t,
    ],
  );

  return { restore, isRestoring };
}
