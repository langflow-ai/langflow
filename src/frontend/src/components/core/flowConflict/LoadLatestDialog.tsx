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
 * Confirms the one conflict exit that ends with your own edits off the canvas.
 *
 * Worth a stop even though nothing is lost — the work goes to version history
 * first — because "my canvas just changed under me" is the surprise this whole
 * feature exists to prevent.
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
        className="w-[400px] max-w-[400px] gap-0 rounded-xl border-muted bg-background p-0 shadow-[0_25px_25px_rgba(0,0,0,0.25)]"
        data-testid="load-latest-dialog"
      >
        <div className="flex items-center justify-between border-b border-muted px-5 py-[15px]">
          <DialogTitle className="text-[13px] font-semibold leading-[19.5px] text-foreground">
            {t("multiEdit.loadLatest.title")}
          </DialogTitle>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="text-muted-foreground transition-colors hover:text-foreground"
            aria-label={t("common.close")}
          >
            <ForwardedIconComponent
              name="X"
              className="h-3.5 w-3.5"
              aria-hidden="true"
            />
          </button>
        </div>

        <div className="px-5 py-[18px]">
          <DialogDescription className="text-[13px] leading-5 text-muted-foreground">
            {t("multiEdit.loadLatest.description")}
          </DialogDescription>
        </div>

        <div className="flex justify-end gap-2.5 border-t border-muted px-5 py-3.5">
          <Button
            variant="ghost"
            size="dialogFooter"
            onClick={() => onOpenChange(false)}
            disabled={isTaking}
            className="text-muted-foreground"
          >
            {t("multiEdit.loadLatest.cancel")}
          </Button>
          <Button
            variant="conflictConfirm"
            size="dialogFooter"
            loading={isTaking}
            onClick={() => void confirm()}
            data-testid="load-latest-confirm-button"
            className="font-semibold [&_svg]:size-3"
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
