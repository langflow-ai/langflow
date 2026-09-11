import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { useTakeLatestVersion } from "@/hooks/flows/use-take-latest-version";

type LoadLatestDialogProps = {
  flowId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/**
 * Confirms the one exit that ends with your own edits off the canvas.
 *
 * Worth a stop even though nothing is lost — the work goes to version history
 * first — because "my canvas just changed under me" is the surprise this whole
 * feature exists to prevent. Destructive in tone for the same reason.
 */
export function LoadLatestDialog({
  flowId,
  open,
  onOpenChange,
}: LoadLatestDialogProps) {
  const { t } = useTranslation();
  const { takeLatestVersion, isTaking } = useTakeLatestVersion();

  const confirm = async () => {
    const done = await takeLatestVersion(flowId);
    if (done) onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideCloseButton
        overlayClassName="bg-black/60"
        className="w-[460px] max-w-[460px] gap-0 rounded-xl border-muted bg-background p-0 shadow-[0_24px_64px_rgba(0,0,0,0.6)]"
        data-testid="load-latest-dialog"
      >
        <div className="flex items-start gap-3 px-5 py-4">
          <ForwardedIconComponent
            name="TriangleAlert"
            className="mt-0.5 h-4 w-4 shrink-0 text-destructive"
            aria-hidden="true"
          />
          <div className="flex min-w-0 flex-col gap-1">
            <DialogTitle className="text-[13px] font-semibold leading-[19.5px] text-foreground">
              {t("multiEdit.loadLatest.title")}
            </DialogTitle>
            <DialogDescription className="text-xs leading-[18px] text-muted-foreground">
              {t("multiEdit.loadLatest.description")}
            </DialogDescription>
          </div>
        </div>
        <div className="flex justify-end gap-2 border-t border-muted px-5 py-4">
          <Button
            variant="conflictQuiet"
            size="dialogAction"
            onClick={() => onOpenChange(false)}
            disabled={isTaking}
          >
            {t("multiEdit.loadLatest.cancel")}
          </Button>
          <Button
            variant="destructive"
            size="dialogAction"
            loading={isTaking}
            onClick={() => void confirm()}
            data-testid="load-latest-confirm-button"
          >
            <ForwardedIconComponent name="RefreshCw" aria-hidden="true" />
            {t("multiEdit.loadLatest.confirm")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default LoadLatestDialog;
