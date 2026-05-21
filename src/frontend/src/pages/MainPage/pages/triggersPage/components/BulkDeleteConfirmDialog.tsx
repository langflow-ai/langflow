import { Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface BulkDeleteConfirmDialogProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  count: number;
  isLoading: boolean;
  onConfirm: () => void;
}

/**
 * Reusable confirmation for both "delete selected" and "delete all".
 * The page passes the count it intends to delete and a single callback
 * so the dialog stays oblivious to whether the action is bulk or
 * single — it only renders the message and routes the click.
 */
export default function BulkDeleteConfirmDialog({
  open,
  setOpen,
  count,
  isLoading,
  onConfirm,
}: BulkDeleteConfirmDialogProps) {
  const { t } = useTranslation();

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            <div className="flex items-center">
              <Trash2 className="h-6 w-6 pr-1 text-foreground" strokeWidth={1.5} />
              <span className="pl-2">{t("triggers.bulkDeleteTitle")}</span>
            </div>
          </DialogTitle>
        </DialogHeader>
        <p className="pb-3 text-sm text-muted-foreground">
          {t("triggers.bulkDeleteBody", { count })}
        </p>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => setOpen(false)}
            disabled={isLoading}
          >
            {t("triggers.cancel")}
          </Button>
          <Button
            type="button"
            variant="destructive"
            loading={isLoading}
            onClick={onConfirm}
            data-testid="bulk-delete-confirm"
          >
            {t("triggers.bulkDeleteConfirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
