import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useState,
} from "react";
import { usePostDetectEnvVars } from "@/controllers/API/queries/variables/use-post-detect-env-vars";
import useAlertStore from "@/stores/alertStore";

export type RightPanelView = "versions" | "connections";

interface PendingAttachment {
  flowId: string;
  versionId: string;
  versionTag: string;
}

interface UseFlowAttachmentParams {
  initialFlowId?: string;
  onSelectVersion: (
    flowId: string,
    versionId: string,
    versionTag: string,
  ) => void;
  setToolNameByFlow: Dispatch<SetStateAction<Map<string, string>>>;
  handleRemoveAttachedFlow: (flowId: string) => void;
}

export function useFlowAttachment({
  initialFlowId,
  onSelectVersion,
  setToolNameByFlow,
  handleRemoveAttachedFlow,
}: UseFlowAttachmentParams) {
  const [selectedFlowId, setSelectedFlowId] = useState<string | null>(
    initialFlowId ?? null,
  );
  const [pendingAttachment, setPendingAttachment] =
    useState<PendingAttachment | null>(null);
  const [rightPanel, setRightPanel] = useState<RightPanelView>("versions");

  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutateAsync: detectEnvVars } = usePostDetectEnvVars();

  const commitPendingAttachment = useCallback(() => {
    if (!pendingAttachment) {
      return;
    }

    onSelectVersion(
      pendingAttachment.flowId,
      pendingAttachment.versionId,
      pendingAttachment.versionTag,
    );
    setPendingAttachment(null);
  }, [pendingAttachment, onSelectVersion]);

  const resetPendingAttachment = useCallback(() => {
    setPendingAttachment(null);
  }, []);

  const beginPendingAttachment = useCallback(
    (attachment: PendingAttachment) => {
      setPendingAttachment(attachment);
      setRightPanel("connections");
    },
    [],
  );

  const detectEnvVarsForVersion = useCallback(
    async (
      versionId: string,
      onDetected: (variableNames: string[]) => void,
    ) => {
      try {
        const result = await detectEnvVars({
          flow_version_ids: [versionId],
        });
        onDetected(result.variables ?? []);
      } catch {
        onDetected([]);
        setErrorData({
          title: "Could not auto-detect environment variables",
          list: ["Add them manually in the connection form."],
        });
      }
    },
    [detectEnvVars, setErrorData],
  );

  const handleDetachFlow = useCallback(
    (flowId: string) => {
      handleRemoveAttachedFlow(flowId);
      setToolNameByFlow((prev) => {
        const next = new Map(prev);
        next.delete(flowId);
        return next;
      });
      setRightPanel("versions");
    },
    [handleRemoveAttachedFlow, setToolNameByFlow],
  );

  const handleSelectFlow = useCallback(
    (flowId: string, onResetSelection: () => void) => {
      setSelectedFlowId(flowId);
      setRightPanel("versions");
      onResetSelection();
    },
    [],
  );

  return {
    selectedFlowId,
    rightPanel,
    setRightPanel,
    commitPendingAttachment,
    resetPendingAttachment,
    beginPendingAttachment,
    detectEnvVarsForVersion,
    handleDetachFlow,
    handleSelectFlow,
  };
}
