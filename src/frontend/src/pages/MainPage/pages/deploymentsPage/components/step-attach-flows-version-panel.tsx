import { memo } from "react";
import { Badge } from "@/components/ui/badge";
import type { FlowType } from "@/types/flow";
import type { FlowVersionEntry } from "@/types/flow/version";
import { cn } from "@/utils/utils";

export const VersionPanel = memo(function VersionPanel({
  selectedFlow,
  versions,
  isLoadingVersions,
  selectedVersionByFlow,
  onAttach,
}: {
  selectedFlow: FlowType | undefined;
  versions: FlowVersionEntry[];
  isLoadingVersions: boolean;
  selectedVersionByFlow: Map<string, { versionId: string; versionTag: string }>;
  onAttach: (versionId: string) => void;
}) {
  if (!selectedFlow) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        Select a flow to see versions
      </div>
    );
  }

  const attachedEntry = selectedVersionByFlow.get(selectedFlow.id);

  return (
    <>
      <div className="border-b border-border p-4 text-sm text-muted-foreground">
        Select a version to attach to this deployment
      </div>
      <div className="flex flex-1 flex-col overflow-hidden px-4 py-2">
        <h3 className="py-2 text-lg font-semibold">{selectedFlow.name}</h3>
        <div className="flex-1 space-y-3 overflow-y-auto py-3">
          {isLoadingVersions ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              Loading versions...
            </div>
          ) : versions.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              No versions found
            </div>
          ) : (
            versions.map((version) => {
              const isAttachedVersion = attachedEntry?.versionId === version.id;
              return (
                <button
                  key={version.id}
                  type="button"
                  data-testid={`version-item-${version.id}`}
                  onClick={() => onAttach(version.id)}
                  className={cn(
                    "flex w-full cursor-pointer items-center gap-4 rounded-xl border p-3 text-left transition-colors",
                    isAttachedVersion
                      ? "border-accent-blue-foreground bg-accent-blue-muted/40"
                      : "border-transparent bg-muted hover:border-border",
                  )}
                >
                  <span className="flex flex-col">
                    <span className="flex items-center gap-2 text-sm font-medium leading-tight">
                      {version.version_tag}
                      {isAttachedVersion && (
                        <Badge
                          variant="secondaryStatic"
                          size="tag"
                          className="bg-accent-blue-muted text-accent-blue-muted-foreground"
                        >
                          ATTACHED
                        </Badge>
                      )}
                    </span>
                    <span className="text-sm leading-tight text-muted-foreground">
                      Created:{" "}
                      {new Date(version.created_at).toLocaleDateString()}
                    </span>
                  </span>
                </button>
              );
            })
          )}
        </div>
      </div>
    </>
  );
});
