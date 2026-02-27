import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useSidebar } from "@/components/ui/sidebar";
import { usePostCreateSnapshot } from "@/controllers/API/queries/flow-history";
import useAlertStore from "@/stores/alertStore";
import useHistoryPreviewStore from "@/stores/historyPreviewStore";
import CanvasBanner, { CanvasBannerButton } from "./CanvasBanner";

interface SaveSnapshotButtonProps {
  flowId: string;
}

export default function SaveSnapshotButton({
  flowId,
}: SaveSnapshotButtonProps) {
  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const clearPreview = useHistoryPreviewStore((s) => s.clearPreview);
  const { setActiveSection, open, toggleSidebar } = useSidebar();
  const { mutate: createSnapshot, isPending: isCreating } =
    usePostCreateSnapshot();
  const [isSavingDisplay, setIsSavingDisplay] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleDismiss = () => {
    setActiveSection("components");
    if (!open) toggleSidebar();
    clearPreview();
  };

  const handleSave = () => {
    setIsSavingDisplay(true);
    setTimeout(() => {
      createSnapshot(
        { flowId, description: null },
        {
          onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["useGetFlowHistory"] });
            setSuccessData({ title: "Version saved" });
            setIsSavingDisplay(false);
            setSavedSuccess(true);
            setTimeout(() => setSavedSuccess(false), 1500);
          },
          onError: (err: any) => {
            const detail = err?.response?.data?.detail;
            setErrorData({
              title: "Failed to save version",
              ...(detail ? { list: [detail] } : {}),
            });
            setIsSavingDisplay(false);
          },
        },
      );
    }, 2000);
  };

  return (
    <CanvasBanner
      icon="BookMarked"
      title="Save a version of your flow"
      description="Capture the current state as a restore point"
      actionSlot={
        <div className="flex items-center gap-2">
          <CanvasBannerButton variant="outline" onClick={handleDismiss}>
            Keep Building
          </CanvasBannerButton>
          <CanvasBannerButton
            onClick={handleSave}
            disabled={isSavingDisplay || isCreating || savedSuccess}
          >
            {isSavingDisplay || isCreating ? (
              <>
                <ForwardedIconComponent
                  name="Loader2"
                  className="h-3.5 w-3.5 animate-spin"
                />
                Saving…
              </>
            ) : savedSuccess ? (
              <>
                <ForwardedIconComponent name="Check" className="h-3.5 w-3.5" />
                Saved
              </>
            ) : (
              "Save"
            )}
          </CanvasBannerButton>
        </div>
      }
    />
  );
}
