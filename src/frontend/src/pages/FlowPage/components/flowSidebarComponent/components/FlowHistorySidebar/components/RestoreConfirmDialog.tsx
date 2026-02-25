import { createPortal } from "react-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import type { FlowHistoryEntry } from "@/types/flow/history";

interface RestoreConfirmDialogProps {
  entry: FlowHistoryEntry | null;
  onClose: () => void;
  onConfirm: (entry: FlowHistoryEntry) => void;
  isRestoring: boolean;
}

export default function RestoreConfirmDialog({
  entry,
  onClose,
  onConfirm,
  isRestoring,
}: RestoreConfirmDialogProps) {
  if (!entry) return null;

  return createPortal(
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
          Restore <strong>{entry.version_tag}</strong>? Your current draft will
          be saved before restoring.
        </p>
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onClose}
            disabled={isRestoring}
          >
            Keep Building
          </Button>
          <Button
            size="sm"
            onClick={() => onConfirm(entry)}
            loading={isRestoring}
          >
            Restore
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
