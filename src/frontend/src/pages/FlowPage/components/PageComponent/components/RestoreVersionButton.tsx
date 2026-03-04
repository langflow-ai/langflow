import { useState } from "react";
import { createPortal } from "react-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useSidebar } from "@/components/ui/sidebar";
import useRestoreVersion from "@/hooks/flows/use-restore-version";
import CanvasBanner, { CanvasBannerButton } from "./CanvasBanner";

interface RestoreVersionButtonProps {
  flowId: string;
  versionId: string;
  versionTag: string;
}

export default function RestoreVersionButton({
  flowId,
  versionId,
  versionTag,
}: RestoreVersionButtonProps) {
  const { restore, isRestoring } = useRestoreVersion(flowId);
  const { setActiveSection } = useSidebar();

  const [showConfirm, setShowConfirm] = useState(false);
  const [saveDraft, setSaveDraft] = useState(true);

  const handleRestore = async () => {
    setShowConfirm(false);
    await restore(versionId, {
      saveDraft,
      onSuccess: () => {
        // Switch sidebar away from "versions" to trigger the version sidebar's
        // unmount cleanup, which re-enables auto-save and restores the
        // inspection panel.
        setActiveSection("components");
      },
    });
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
          <CanvasBannerButton
            onClick={() => setShowConfirm(true)}
            disabled={isRestoring}
          >
            {isRestoring ? "Restoring…" : "Restore"}
          </CanvasBannerButton>
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
                Restore <strong>{versionTag}</strong>? This will replace your
                current canvas.
              </p>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="save-draft"
                  checked={saveDraft}
                  onCheckedChange={(checked: boolean) => setSaveDraft(checked)}
                />
                <label
                  htmlFor="save-draft"
                  className="text-sm text-muted-foreground"
                >
                  Save current draft before restoring
                </label>
              </div>
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
