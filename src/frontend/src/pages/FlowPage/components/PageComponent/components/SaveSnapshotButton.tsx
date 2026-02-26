import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useSidebar } from "@/components/ui/sidebar";
import { usePostCreateSnapshot } from "@/controllers/API/queries/flow-history";
import useAlertStore from "@/stores/alertStore";
import useHistoryPreviewStore from "@/stores/historyPreviewStore";

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
  };

  return (
    <div className="history-preview-banner-enter pointer-events-auto absolute bottom-10 left-1/2 w-[700px]">
      <div className="history-preview-banner flex items-center gap-4 overflow-hidden rounded-xl border border-accent-indigo-foreground/20 bg-gradient-to-r from-accent-indigo via-accent-indigo/70 to-accent-indigo/30 px-5 py-3 backdrop-blur-sm">
        <div className="flex items-center gap-4 flex-1">
          <ForwardedIconComponent
            name="BookMarked"
            className="h-6 w-6 shrink-0 text-accent-indigo-foreground/80"
          />
          <div className="flex flex-col pr-3">
            <p className="font-semibold text-accent-indigo-foreground">
              Save a version of your flow
            </p>
            <p className="text-accent-indigo-foreground/70">
              Capture the current state as a restore point
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDismiss}
            className="group flex items-center gap-2 rounded-lg border border-accent-indigo-foreground/30 bg-accent-indigo/60 px-3 py-1.5 font-semibold text-accent-indigo-foreground shadow-sm transition-all duration-200 hover:bg-accent-indigo/80 hover:shadow-md"
          >
            Keep Building
          </button>
          <button
            onClick={handleSave}
            disabled={isSavingDisplay || isCreating || savedSuccess}
            className="group flex items-center gap-2 rounded-lg border border-accent-indigo-foreground/30 bg-accent-indigo/60 px-3 py-1.5 font-semibold text-accent-indigo-foreground shadow-sm transition-all duration-200 hover:bg-accent-indigo/80 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-60"
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
          </button>
        </div>
      </div>
    </div>
  );
}
