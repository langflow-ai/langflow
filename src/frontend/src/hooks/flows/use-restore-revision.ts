import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { v4 as uuidv4 } from "uuid";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import {
  clientViolations,
  type GraphViolation,
  previewFixesFor,
} from "@/hooks/flows/refused-restore";
import useApplyFlowToCanvas from "@/hooks/flows/use-apply-flow-to-canvas";
import useAlertStore from "@/stores/alertStore";
import useVersionPreviewStore from "@/stores/versionPreviewStore";
import type { FlowOperation } from "@/utils/flow-operations/apply";

/**
 * Make an earlier point in the flow's history its current state.
 *
 * The server replays the history itself rather than taking the graph back
 * from the editor: what the editor previewed has its secrets removed, and
 * saving that would blank them. The restore is recorded as new history, so
 * the state it replaces stays one step back in the timeline.
 *
 * A revision can break the edge rules in ways only the editor can fix, which
 * the server refuses with violations marked `client`. The restore is then
 * sent once more with the edge fixes the preview already shows for the edges
 * the server flagged (see edge-fixes); the server checks and applies them and
 * keeps the unfixed revision as a view-only version.
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
      const send = (fixes?: FlowOperation[]) =>
        api.post(`${getURL("FLOWS")}/${flowId}/revisions/${revision}/restore`, {
          request_id: uuidv4(),
          ...(fixes ? { fixes } : {}),
        });
      let fixed: GraphViolation[] | null = null;
      try {
        let response: Awaited<ReturnType<typeof send>>;
        try {
          response = await send();
        } catch (err) {
          fixed = clientViolations(err);
          if (!fixed) throw err;
          const fixes = previewFixesFor(fixed);
          if (fixes.length === 0) throw err;
          response = await send(fixes);
        }
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
        setSuccessData(
          fixed
            ? {
                title: t("flowHistory.restore.withoutBrokenConnections"),
                list: fixed.map((violation) => violation.message),
              }
            : { title: t("success.versionRestored") },
        );
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
