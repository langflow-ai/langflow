import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { usePostCreateSnapshot } from "@/controllers/API/queries/flow-version";
import useRestoreVersion from "@/hooks/flows/use-restore-version";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

function preRevertDescription(): string {
  const timestamp = new Date().toISOString().replace("T", " ").slice(0, 19);
  return `pre-revert ${timestamp} UTC`;
}

export interface UseAssistantRevertReturn {
  revert: (
    restoreVersionId: string,
    options?: { onSuccess?: () => void },
  ) => Promise<void>;
  isReverting: boolean;
}

/**
 * Revert the flow to an assistant restore point (the version snapshotted
 * before a canvas-mutating turn). Snapshots the CURRENT state first as a
 * safety net, then activates the target version via the shared restore
 * mechanism so the canvas reloads exactly like the versions screen.
 */
export function useAssistantRevert(): UseAssistantRevertReturn {
  const { t } = useTranslation();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutateAsync: createSnapshot } = usePostCreateSnapshot();
  const { restore, isRestoring } = useRestoreVersion(currentFlowId ?? "");
  const [isSnapshotting, setIsSnapshotting] = useState(false);

  const revert = useCallback(
    async (restoreVersionId: string, options?: { onSuccess?: () => void }) => {
      if (!currentFlowId) return;
      setIsSnapshotting(true);
      try {
        await createSnapshot({
          flowId: currentFlowId,
          description: preRevertDescription(),
        });
      } catch (err) {
        const detail = (err as { response?: { data?: { detail?: string } } })
          ?.response?.data?.detail;
        setErrorData({
          title: t("assistant.revert.errorTitle"),
          ...(detail ? { list: [detail] } : {}),
        });
        setIsSnapshotting(false);
        return;
      }
      setIsSnapshotting(false);
      // saveDraft=false: the pre-revert snapshot above already captured the
      // current state; the activate endpoint's auto-draft would duplicate it.
      await restore(restoreVersionId, {
        saveDraft: false,
        onSuccess: options?.onSuccess,
      });
    },
    [currentFlowId, createSnapshot, restore, setErrorData, t],
  );

  return { revert, isReverting: isSnapshotting || isRestoring };
}
