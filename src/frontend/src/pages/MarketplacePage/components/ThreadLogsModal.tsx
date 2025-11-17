import React from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ThreadLog } from "./ThreadManager";

interface ThreadLogsModalProps {
  open: boolean;
  onClose: () => void;
  logs: ThreadLog[];
  onClearAll: () => void;
}

export function ThreadLogsModal({ open, onClose, logs, onClearAll }: ThreadLogsModalProps) {
  return (
    <Dialog open={open} onOpenChange={(v) => (!v ? onClose() : null)}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Thread Logs</DialogTitle>
        </DialogHeader>
        {logs.length === 0 ? (
          <div className="text-sm text-muted-foreground">No thread logs yet.</div>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {logs.map((log) => (
              <div key={log.id} className="flex items-center justify-between border rounded-md px-3 py-2">
                <div className="flex flex-col min-w-0">
                  <span className="text-sm font-medium truncate" title={log.id}>{`thread_${log.id}`}</span>
                  <span className="text-xs text-muted-foreground">
                    {new Date(log.createdAt).toLocaleString()} • {log.messagesCount} messages
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigator.clipboard.writeText(log.id)}
                >
                  Copy ID
                </Button>
              </div>
            ))}
          </div>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>Close</Button>
          <Button variant="destructive" onClick={onClearAll}>Clear All</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}