import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createPortal } from "react-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useSidebar } from "@/components/ui/sidebar";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import useApplyFlowToCanvas from "@/hooks/flows/use-apply-flow-to-canvas";
import useAlertStore from "@/stores/alertStore";
import useHistoryPreviewStore from "@/stores/historyPreviewStore";
import CanvasBanner, { CanvasBannerButton } from "./CanvasBanner";

interface RestoreVersionButtonProps {
  flowId: string;
  historyId: string;
  versionTag: string;
}

export default function RestoreVersionButton({
  flowId,
  historyId,
  versionTag,
}: RestoreVersionButtonProps) {
  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const clearPreview = useHistoryPreviewStore((s) => s.clearPreview);
  const applyFlowToCanvas = useApplyFlowToCanvas();
  const { setActiveSection, open, toggleSidebar } = useSidebar();

  const handleDismiss = () => {
    setActiveSection("components");
    if (!open) toggleSidebar();
    clearPreview();
  };

  const [showConfirm, setShowConfirm] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);

  const handleRestore = async () => {
    setShowConfirm(false);
    setIsRestoring(true);
    try {
      const response = await api.post(
        `${getURL("FLOWS")}/${flowId}/history/${historyId}/activate`,
        null,
        { params: { save_draft: true } },
      );
      const updatedFlow = response.data;
      queryClient.invalidateQueries({ queryKey: ["useGetFlowHistory"] });
      const flow = {
        ...updatedFlow,
        data: {
          nodes: updatedFlow.data?.nodes ?? [],
          edges: updatedFlow.data?.edges ?? [],
        },
      };
      applyFlowToCanvas(flow);
      clearPreview();
      setSuccessData({ title: "Version restored" });
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setErrorData({
        title: "Failed to restore version",
        ...(detail ? { list: [detail] } : {}),
      });
    } finally {
      setIsRestoring(false);
    }
  };

  return (
    <>
      <CanvasBanner
        icon="RotateCcw"
        title="Restore this version of your flow"
        description={
          <>
            Replace the current draft with{" "}
            <span className="font-medium">{versionTag}</span>
          </>
        }
        actionSlot={
          <div className="flex items-center gap-2">
            <CanvasBannerButton
              variant="outline"
              onClick={handleDismiss}
              disabled={isRestoring}
            >
              Keep Building
            </CanvasBannerButton>
            <CanvasBannerButton
              onClick={() => setShowConfirm(true)}
              disabled={isRestoring}
            >
              {isRestoring ? "Restoring…" : "Restore"}
            </CanvasBannerButton>
          </div>
        }
      />

      {showConfirm &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="mx-4 flex w-full max-w-md flex-col gap-4 rounded-xl border bg-background p-6 shadow-lg">
              <div className="flex items-center gap-2">
                <ForwardedIconComponent
                  name="RotateCcw"
                  className="h-5 w-5 text-primary"
                />
                <span className="text-lg font-semibold">Restore Version</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Restore <strong>{versionTag}</strong>? Your current draft will
                be saved before restoring.
              </p>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setShowConfirm(false);
                  }}
                >
                  Cancel
                </Button>
                <Button size="sm" onClick={handleRestore} loading={isRestoring}>
                  Restore
                </Button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
