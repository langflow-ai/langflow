/**
 * Card rendered for each ``WrittenFile`` on an assistant message.
 *
 * Visually mirrors the canvas-flow preview card but for files. Two actions:
 *   - **Open** — surfaces the file content via a modal in the panel. The
 *     parent (assistant-message) supplies the ``onOpen`` handler so the
 *     modal owns the lifecycle.
 *   - **Download** — fetches the file with ``?download=true`` and triggers a
 *     browser download via Blob URL.
 *
 * Path handling: the displayed name is the basename only (no sandbox path
 * leakage). The query param sent over the wire is ``encodeURIComponent``'d
 * so a filename with spaces or special characters can't break out of the
 * URL.
 */

import {
  FileText,
  FilePen,
  Download as DownloadIcon,
  ExternalLink,
} from "lucide-react";
import { useCallback } from "react";

import type { WrittenFile } from "../assistant-panel.types";
import { GHOST_SECONDARY_BUTTON } from "../helpers/button-styles";

interface AssistantFileCardProps {
  file: WrittenFile;
  onOpen: (file: WrittenFile) => void;
}

function basename(p: string): string {
  const last = p.split(/[/\\]/).filter(Boolean).pop();
  return last ?? p;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} kB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function AssistantFileCard({ file, onOpen }: AssistantFileCardProps) {
  const handleDownload = useCallback(() => {
    // Content arrived inline with the SSE event — build the Blob from the
    // in-memory string. No HTTP fetch, no auth concerns, no path-resolution
    // mismatch between writer (agent task) and reader (HTTP request).
    if (file.content === undefined) {
      // Preview not available (e.g., edit_file with no captured content) —
      // delegate to Open so the modal renders the "Preview not available"
      // notice.
      onOpen(file);
      return;
    }
    const blob = new Blob([file.content], { type: "text/plain;charset=utf-8" });
    const objectUrl = URL.createObjectURL(blob);
    try {
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = basename(file.path);
      document.body.appendChild(a);
      a.click();
      a.remove();
    } finally {
      URL.revokeObjectURL(objectUrl);
    }
  }, [file, onOpen]);

  const handleOpen = useCallback(() => onOpen(file), [file, onOpen]);

  const IconForAction = file.action === "edit_file" ? FilePen : FileText;

  return (
    <div
      data-testid={`assistant-file-card-${file.path}`}
      data-action={file.action}
      className="flex max-w-[80%] items-center gap-3 rounded-md bg-muted/30 px-3 py-2"
    >
      <IconForAction className="h-4 w-4 shrink-0 text-foreground/80" />
      <div className="flex min-w-0 flex-1 flex-col">
        <span
          className="truncate text-sm font-semibold text-foreground"
          title={file.path}
        >
          {basename(file.path)}
        </span>
        <span className="text-xs text-muted-foreground">
          {file.action === "edit_file" ? "edited" : "created"} ·{" "}
          {formatSize(file.size)}
        </span>
      </div>
      <div className="flex items-center gap-1">
        <button
          type="button"
          data-testid={`assistant-file-open-button-${file.path}`}
          onClick={handleOpen}
          className={GHOST_SECONDARY_BUTTON}
        >
          <ExternalLink className="h-3.5 w-3.5" />
          <span>Open</span>
        </button>
        <button
          type="button"
          data-testid={`assistant-file-download-button-${file.path}`}
          onClick={handleDownload}
          className={GHOST_SECONDARY_BUTTON}
        >
          <DownloadIcon className="h-3.5 w-3.5" />
          <span>Download</span>
        </button>
      </div>
    </div>
  );
}
