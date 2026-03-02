import { createPortal } from "react-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import type { FlowVersionEntry } from "@/types/flow/version";

interface DeleteConfirmDialogProps {
  entry: FlowVersionEntry | null;
  onClose: () => void;
  onConfirm: (entry: FlowVersionEntry) => void;
  isDeleting: boolean;
}

export default function DeleteConfirmDialog({
  entry,
  onClose,
  onConfirm,
  isDeleting,
}: DeleteConfirmDialogProps) {
  if (!entry) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="mx-4 flex w-full max-w-md flex-col gap-4 rounded-xl border bg-background p-6 shadow-lg">
        <div className="flex items-center gap-2">
          <ForwardedIconComponent
            name="Trash2"
            className="h-5 w-5 text-destructive"
          />
          <span className="text-lg font-semibold">Delete Version</span>
        </div>
        <p className="text-sm text-muted-foreground">
          This will permanently delete <strong>{entry.version_tag}</strong>.
          This can't be undone.
        </p>
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onClose}
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => onConfirm(entry)}
            loading={isDeleting}
          >
            Delete
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
