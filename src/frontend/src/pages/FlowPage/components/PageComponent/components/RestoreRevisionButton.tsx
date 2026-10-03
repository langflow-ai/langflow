import { useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useSidebar } from "@/components/ui/sidebar";
import useRestoreRevision from "@/hooks/flows/use-restore-revision";
import CanvasBanner, { CanvasBannerButton } from "./CanvasBanner";

interface RestoreRevisionButtonProps {
  flowId: string;
  revision: number;
  label: string;
  /** False inside an entry, where the slider shows steps no one saved. */
  restorable: boolean;
}

/**
 * Restores the flow to the previewed point in its history.
 *
 * Unlike restoring a saved version, there is no draft to save first: the
 * current state is already in the history, one step back once this restore
 * is recorded.
 */
export default function RestoreRevisionButton({
  flowId,
  revision,
  label,
  restorable,
}: RestoreRevisionButtonProps) {
  const { t } = useTranslation();
  const { restore, isRestoring } = useRestoreRevision(flowId);
  const { setActiveSection } = useSidebar();
  const [showConfirm, setShowConfirm] = useState(false);

  const handleRestore = async () => {
    setShowConfirm(false);
    await restore(revision, {
      // Leaving the versions section runs its cleanup, which re-enables autosave.
      onSuccess: () => setActiveSection("components"),
    });
  };

  return (
    <>
      <CanvasBanner
        icon="RotateCcw"
        title={t("flowHistory.restore.title")}
        description={
          restorable
            ? t("flowHistory.restore.description", { label })
            : t("flowHistory.restore.onlyAtEntryEnd")
        }
        actionSlot={
          <CanvasBannerButton
            onClick={() => setShowConfirm(true)}
            disabled={isRestoring || !restorable}
          >
            {isRestoring
              ? t("flowHistory.restore.restoring")
              : t("flowHistory.restore.action")}
          </CanvasBannerButton>
        }
      />
      {showConfirm &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div
              role="alertdialog"
              aria-labelledby="restore-revision-title"
              className="mx-4 flex w-full max-w-md flex-col gap-4 rounded-xl border bg-background p-6 shadow-lg"
            >
              <div className="flex items-center gap-2">
                <ForwardedIconComponent
                  name="RotateCcw"
                  className="h-5 w-5 text-primary"
                />
                <span
                  id="restore-revision-title"
                  className="text-lg font-semibold"
                >
                  {t("flowHistory.restore.title")}
                </span>
              </div>
              <p className="text-sm text-muted-foreground">
                {t("flowHistory.restore.confirm", { label })}
              </p>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowConfirm(false)}
                >
                  {t("flowHistory.repair.cancel")}
                </Button>
                <Button size="sm" onClick={handleRestore} loading={isRestoring}>
                  {t("flowHistory.restore.action")}
                </Button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
