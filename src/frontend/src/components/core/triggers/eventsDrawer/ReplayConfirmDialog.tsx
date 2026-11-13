import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export interface ReplayConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  busy: boolean;
}

/** Says plainly that a replay is a new event; the original keeps its result. */
export function ReplayConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  busy,
}: ReplayConfirmDialogProps) {
  const { t } = useTranslation();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="trigger-replay-dialog">
        <DialogHeader>
          <DialogTitle>{t("triggers.replay.title")}</DialogTitle>
          <DialogDescription>
            {t("triggers.replay.description")}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("triggers.common.cancel")}
          </Button>
          <Button
            onClick={onConfirm}
            loading={busy}
            data-testid="trigger-replay-confirm"
          >
            {t("triggers.replay.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default ReplayConfirmDialog;
