import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import { formatFileSize } from "../utils";
import { MetadataEditor, type MetadataPair } from "./MetadataEditor";

interface FilesPanelProps {
  files: File[];
  onRemoveFile: (index: number) => void;
  perFileMetadata: Record<string, MetadataPair[]>;
  onPerFileMetadataChange: (next: Record<string, MetadataPair[]>) => void;
}

/**
 * Side panel listing every staged file plus an inline per-file metadata
 * override editor.
 *
 * The override editor is collapsed by default and toggled per file so the
 * panel stays compact for the typical batch-tag flow. Per-file pairs are
 * keyed by ``file.name`` — for batches uploading two files with the same
 * basename, the API merges per-file metadata onto every match (acceptable
 * trade-off vs. needing a stable per-row id at upload time).
 */
export function FilesPanel({
  files,
  onRemoveFile,
  perFileMetadata,
  onPerFileMetadataChange,
}: FilesPanelProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggleExpanded = (key: string) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const setPairsForFile = (fileName: string, pairs: MetadataPair[]) => {
    const next = { ...perFileMetadata };
    if (pairs.length === 0) {
      delete next[fileName];
    } else {
      next[fileName] = pairs;
    }
    onPerFileMetadataChange(next);
  };

  return (
    <div className="flex h-full flex-col">
      {/* Sticky header */}
      <div className="flex items-center gap-2 text-base font-semibold p-3 pb-1">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
          <ForwardedIconComponent name="FileStack" className="h-4 w-4" />
        </div>
        {t("knowledge.sourcesLabel")}
        {files.length > 0 && (
          <span className="text-xs font-normal text-muted-foreground">
            ({files.length}{" "}
            {files.length === 1 ? t("knowledge.file") : t("knowledge.files")},{" "}
            {formatFileSize(files)})
          </span>
        )}
      </div>
      {/* Scrollable file list */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        <div className="flex flex-col gap-1">
          {files.map((file, index) => {
            const key = `${file.name}-${index}`;
            const isOpen = expanded[key] ?? false;
            const pairs = perFileMetadata[file.name] ?? [];
            const hasMetadata = pairs.length > 0;
            return (
              <div
                key={key}
                className="group flex flex-col rounded-md hover:bg-muted"
              >
                <div className="flex items-center justify-between px-2 py-1.5">
                  <div className="flex items-center gap-2 truncate">
                    <ForwardedIconComponent
                      name="FileText"
                      className="h-4 w-4 shrink-0 text-muted-foreground"
                    />
                    <span className="truncate text-sm">{file.name}</span>
                    {hasMetadata && (
                      <span
                        className="ml-1 rounded bg-accent-emerald-foreground/10 px-1 text-[10px] uppercase text-accent-emerald-foreground"
                        data-testid={`kb-file-metadata-badge-${index}`}
                      >
                        {pairs.length === 1
                          ? t("knowledge.oneTag")
                          : t("knowledge.nTags", { count: pairs.length })}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className={cn(
                        "h-6 w-6 shrink-0 transition-opacity",
                        hasMetadata
                          ? "opacity-100"
                          : "opacity-0 group-hover:opacity-100",
                      )}
                      onClick={() => toggleExpanded(key)}
                      aria-label={
                        isOpen
                          ? t("knowledge.collapseMetadataFor", {
                              name: file.name,
                            })
                          : t("knowledge.expandMetadataFor", {
                              name: file.name,
                            })
                      }
                      data-testid={`kb-file-metadata-toggle-${index}`}
                    >
                      <ForwardedIconComponent
                        name={isOpen ? "ChevronUp" : "Tag"}
                        className="h-3 w-3"
                      />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                      onClick={() => onRemoveFile(index)}
                    >
                      <ForwardedIconComponent name="X" className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
                {isOpen && (
                  <div
                    className="border-t border-border/60 bg-background/40 px-3 py-2"
                    data-testid={`kb-file-metadata-editor-${index}`}
                  >
                    <MetadataEditor
                      pairs={pairs}
                      onPairsChange={(next) => setPairsForFile(file.name, next)}
                      testIdScope={`kb-file-${index}`}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
