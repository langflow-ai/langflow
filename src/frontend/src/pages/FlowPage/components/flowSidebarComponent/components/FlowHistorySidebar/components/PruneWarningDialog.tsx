import { createPortal } from "react-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

interface PruneWarningDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isCreating: boolean;
  versionsLength: number;
  maxEntries: number;
}

export default function PruneWarningDialog({
  open,
  onClose,
  onConfirm,
  isCreating,
  versionsLength,
  maxEntries,
}: PruneWarningDialogProps) {
  if (!open) return null;

  const pruneCount = versionsLength + 1 - maxEntries;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="mx-4 flex w-full max-w-md flex-col gap-4 rounded-xl border bg-background p-6 shadow-lg">
        <div className="flex items-center gap-2">
          <ForwardedIconComponent
            name="AlertTriangle"
            className="h-5 w-5 text-warning"
          />
          <span className="text-lg font-semibold">Version Limit Reached</span>
        </div>
        <p className="text-sm text-muted-foreground">
          {pruneCount <= 1 ? (
            <>
              You've reached the maximum of <strong>{maxEntries}</strong> saved
              versions. Saving a new version will automatically delete the
              oldest version. Do you want to continue?
            </>
          ) : (
            <>
              You have <strong>{versionsLength}</strong> versions but the limit
              is <strong>{maxEntries}</strong>. Saving a new version will
              automatically delete the <strong>{pruneCount}</strong> oldest
              versions. Do you want to continue?
            </>
          )}
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={onConfirm}
            loading={isCreating}
          >
            Continue
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
