import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createPortal } from "react-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import useApplyFlowToCanvas from "@/hooks/flows/use-apply-flow-to-canvas";
import useAlertStore from "@/stores/alertStore";
import useHistoryPreviewStore from "@/stores/historyPreviewStore";
import { processFlows } from "@/utils/reactflowUtils";

interface RestoreVersionButtonProps {
  flowId: string;
  versionId: string;
  versionTag: string;
}

function getErrorDetail(error: unknown): string | undefined {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof (error as { response?: unknown }).response === "object"
  ) {
    const response = (error as { response?: { data?: { detail?: string } } })
      .response;
    return response?.data?.detail;
  }
  return undefined;
}

export default function RestoreVersionButton({
  flowId,
  versionId,
  versionTag,
}: RestoreVersionButtonProps) {
  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const clearPreview = useHistoryPreviewStore((s) => s.clearPreview);
  const applyFlowToCanvas = useApplyFlowToCanvas();

  const [showConfirm, setShowConfirm] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);

  const handleRestore = async () => {
    setShowConfirm(false);
    setIsRestoring(true);
    try {
      const response = await api.post(
        `${getURL("FLOWS")}/${flowId}/versions/${versionId}/activate`,
        null,
        { params: { save_draft: true } },
      );
      const updatedFlow = response.data;
      queryClient.invalidateQueries({ queryKey: ["useGetFlowVersions"] });
      const flow = {
        ...updatedFlow,
        data: {
          nodes: updatedFlow.data?.nodes ?? [],
          edges: updatedFlow.data?.edges ?? [],
        },
      };
      processFlows([flow]);
      applyFlowToCanvas(flow);
      clearPreview();
      setSuccessData({ title: "Version restored" });
    } catch (err: unknown) {
      const detail = getErrorDetail(err);
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
      <div className="history-preview-banner-enter pointer-events-auto absolute bottom-10 left-1/2 w-[700px]">
        <div className="history-preview-banner flex items-center gap-4 overflow-hidden rounded-xl border border-accent-indigo-foreground/20 bg-gradient-to-r from-accent-indigo via-accent-indigo/70 to-accent-indigo/30 px-5 py-3 backdrop-blur-sm">
          <ForwardedIconComponent
            name="RotateCcw"
            className="h-6 w-6 shrink-0 text-accent-indigo-foreground/80"
          />
          <div className="flex flex-col">
            <p className="font-semibold text-accent-indigo-foreground">
              Restore this version of your flow
            </p>
            <p className="text-accent-indigo-foreground/70">
              Replace the current draft with{" "}
              <span className="font-medium">{versionTag}</span>
            </p>
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={clearPreview}
              disabled={isRestoring}
              className="group flex items-center gap-2 rounded-lg border border-accent-indigo-foreground/30 bg-accent-indigo/60 px-3 py-1.5 font-semibold text-accent-indigo-foreground shadow-sm transition-all duration-200 hover:bg-accent-indigo/80 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-60"
            >
              Keep Building
            </button>
            <button
              onClick={() => setShowConfirm(true)}
              disabled={isRestoring}
              className="group flex items-center gap-2 rounded-lg border border-accent-indigo-foreground/30 bg-accent-indigo/60 px-3 py-1.5 font-semibold text-accent-indigo-foreground shadow-sm transition-all duration-200 hover:bg-accent-indigo/80 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isRestoring ? "Restoring…" : "Restore"}
            </button>
          </div>
        </div>
      </div>

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
                  onClick={() => setShowConfirm(false)}
                >
                  Keep Building
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
