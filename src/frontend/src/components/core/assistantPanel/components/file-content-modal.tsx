/**
 * Modal that renders a sandboxed file's text content with XSS-safe markdown.
 *
 * Content comes inline from the SSE ``file_written`` event — no extra HTTP
 * fetch. The trade-off is the event payload carries the file body once over
 * the wire; for typical docs (≤ a few KB) this is negligible and saves us
 * an authenticated round-trip + an extra endpoint surface.
 *
 * XSS: agent-generated content is rendered through ``SanitizedMarkdown``
 * which delegates to ``rehype-sanitize`` with the project allow-list. We
 * NEVER use ``dangerouslySetInnerHTML``.
 */

import { useTranslation } from "react-i18next";

import { SanitizedMarkdown } from "@/components/core/sanitizedMarkdown";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface FileContentModalProps {
  path: string;
  content: string | undefined;
  open: boolean;
  onClose: () => void;
}

function basename(p: string): string {
  const last = p.split(/[/\\]/).filter(Boolean).pop();
  return last ?? p;
}

export function FileContentModal({
  path,
  content,
  open,
  onClose,
}: FileContentModalProps) {
  const { t } = useTranslation();
  const hasContent = content !== undefined;
  const isEmpty = !content || content.trim() === "";

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? null : onClose())}>
      <DialogContent
        className="flex max-h-[80vh] max-w-3xl flex-col"
        data-testid="file-content-modal"
      >
        <DialogHeader>
          <DialogTitle>{basename(path)}</DialogTitle>
        </DialogHeader>
        <div className="flex-1 overflow-auto pr-2">
          {!hasContent && (
            <div
              data-testid="file-content-modal-empty"
              className="rounded-md border border-border bg-muted/30 p-3 text-sm text-muted-foreground"
            >
              {t("Preview not available for this file.", {
                defaultValue: "Preview not available for this file.",
              })}
            </div>
          )}
          {hasContent && (
            <SanitizedMarkdown
              chatMessage={content as string}
              isEmpty={isEmpty}
              emptyMessage={t("(empty file)", { defaultValue: "(empty file)" })}
              className="max-w-full"
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
