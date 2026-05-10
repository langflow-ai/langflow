import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { formatTimestamp } from "../helpers";
import { MemoryDocumentPanelProps } from "../types";

export function MemoryDocumentPanel({
  open,
  onOpenChange,
  selectedDocument,
}: MemoryDocumentPanelProps) {
  const titleId = "memories-document-panel-title";
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        aria-labelledby={titleId}
        className={
          "right-0 top-[3rem] h-[calc(100dvh-3rem)] w-full max-w-none rounded-l-xl rounded-r-none p-0 sm:w-[80vw] " +
          "data-[state=open]:animate-in data-[state=closed]:animate-out " +
          "data-[state=open]:slide-in-from-right-1/2 data-[state=closed]:slide-out-to-right-1/2"
        }
        closeButtonClassName="top-1"
        data-testid="memories-document-panel"
      >
        <DialogTitle id={titleId} className="sr-only">
          Memory chunk details
        </DialogTitle>
        {!selectedDocument ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            No chunk selected.
          </div>
        ) : (
          <div className="flex h-full flex-col overflow-hidden">
            <div className="border-b border-border px-4 py-3 pr-12">
              <div className="flex min-w-0 flex-nowrap items-center gap-2 overflow-hidden whitespace-nowrap">
                <span className="shrink-0 text-sm font-medium">
                  Chunk Details
                </span>
                <span className="shrink-0 text-sm text-muted-foreground">
                  -
                </span>
                <span className="shrink-0 text-sm font-medium">
                  {selectedDocument.message_id || "(no id)"}
                </span>
              </div>
            </div>

            <div className="flex-1 overflow-auto p-4">
              <div className="mb-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
                <span>
                  <span className="font-medium text-foreground">Session:</span>{" "}
                  {selectedDocument.session_id || "(no session)"}
                </span>
                <span>
                  <span className="font-medium text-foreground">Sender:</span>{" "}
                  {selectedDocument.sender || "-"}
                </span>
                <span>
                  <span className="font-medium text-foreground">
                    Timestamp:
                  </span>{" "}
                  {formatTimestamp(selectedDocument.timestamp)}
                </span>
              </div>

              <div className="rounded-lg border border-border bg-background p-4">
                <div className="mb-2 text-xs font-semibold text-muted-foreground">
                  Content
                </div>
                <div className="whitespace-pre-wrap break-words text-sm">
                  {selectedDocument.content || ""}
                </div>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
