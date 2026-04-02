import { memo } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { FlowType } from "@/types/flow";
import type { FlowVersionEntry } from "@/types/flow/version";
import { RadioSelectItem } from "./radio-select-item";

export const VersionPanel = memo(function VersionPanel({
  selectedFlow,
  versions,
  isLoadingVersions,
  pendingVersion,
  selectedVersionByFlow,
  toolName,
  onToolNameChange,
  onSelectPending,
  onAttach,
  onManageConnections,
}: {
  selectedFlow: FlowType | undefined;
  versions: FlowVersionEntry[];
  isLoadingVersions: boolean;
  pendingVersion: string | null;
  selectedVersionByFlow: Map<string, { versionId: string; versionTag: string }>;
  toolName: string;
  onToolNameChange: (name: string) => void;
  onSelectPending: (id: string) => void;
  onAttach: () => void;
  onManageConnections?: () => void;
}) {
  if (!selectedFlow) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        Select a flow to see versions
      </div>
    );
  }

  const attachedEntry = selectedVersionByFlow.get(selectedFlow.id);
  const isAlreadyAttached = !!attachedEntry;
  const pendingIsSameAsAttached =
    isAlreadyAttached && pendingVersion === attachedEntry.versionId;
  const pendingIsDifferentVersion =
    isAlreadyAttached && pendingVersion && !pendingIsSameAsAttached;

  return (
    <>
      <div className="border-b border-border p-4 text-sm text-muted-foreground">
        {isAlreadyAttached
          ? "This flow is attached. Select a different version to update, or manage connections."
          : "Select a version to attach to this deployment"}
      </div>
      <div className="flex flex-1 flex-col overflow-hidden px-4 py-2">
        <h3 className="py-2 text-lg font-semibold">{selectedFlow.name}</h3>
        <div
          className="flex-1 space-y-3 overflow-y-auto py-3"
          role="radiogroup"
          aria-label="Flow versions"
        >
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
              const isAttachedVersion =
                attachedEntry?.versionId === version.id;
              const isSelected = pendingVersion === version.id;
              return (
                <RadioSelectItem
                  key={version.id}
                  name="flow-version"
                  value={version.id}
                  selected={isSelected}
                  onChange={() => onSelectPending(version.id)}
                  data-testid={`version-item-${version.id}`}
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
                </RadioSelectItem>
              );
            })
          )}
        </div>
        {/* Tool name input — only for new attachments */}
        {pendingVersion && !isAlreadyAttached && (
          <div className="flex flex-col gap-1 pb-2">
            <span className="text-xs font-medium text-muted-foreground">
              Tool Name
            </span>
            <Input
              placeholder={selectedFlow.name}
              className="bg-muted"
              value={toolName}
              onChange={(e) => onToolNameChange(e.target.value)}
              data-testid="tool-name-input"
            />
          </div>
        )}
        <div className="flex flex-col gap-2">
          {isAlreadyAttached ? (
            <>
              <Button
                className="w-full"
                disabled={!pendingVersion || pendingIsSameAsAttached}
                onClick={onAttach}
              >
                {pendingIsSameAsAttached
                  ? "Already Attached"
                  : pendingIsDifferentVersion
                    ? "Change Version"
                    : "Select a Version"}
              </Button>
              {onManageConnections && (
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={onManageConnections}
                >
                  Manage Connections
                </Button>
              )}
            </>
          ) : (
            <Button
              className="w-full"
              disabled={!pendingVersion}
              onClick={onAttach}
            >
              Attach Flow
            </Button>
          )}
        </div>
      </div>
    </>
  );
});
