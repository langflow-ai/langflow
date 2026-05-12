import { memo } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import VersionLabel from "@/components/common/versionLabelComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { FlowType } from "@/types/flow";
import type { FlowVersionEntry } from "@/types/flow/version";
import { cn } from "@/utils/utils";
import {
  type ConnectionItem,
  getSelectedFlowVersionKey,
  type SelectedFlowVersion,
} from "../types";

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export const VersionPanel = memo(function VersionPanel({
  selectedFlow,
  versions,
  isLoadingVersions,
  isCreatingDraftVersion,
  selectedVersionByFlow,
  onAttach,
  onCreateFromDraft,
  onDetach,
  onUndoRemove,
  removedFlowIds = new Set<string>(),
  attachedConnectionByFlow = new Map<string, string[]>(),
  connections = [],
}: {
  selectedFlow: FlowType | undefined;
  versions: FlowVersionEntry[];
  isLoadingVersions: boolean;
  isCreatingDraftVersion: boolean;
  selectedVersionByFlow: Map<string, SelectedFlowVersion>;
  onAttach: (versionId: string) => void;
  onCreateFromDraft: () => void;
  onDetach: (attachmentKey: string) => void;
  onUndoRemove?: (attachmentKey: string) => void;
  removedFlowIds?: Set<string>;
  attachedConnectionByFlow?: Map<string, string[]>;
  connections?: ConnectionItem[];
}) {
  const { t } = useTranslation();
  if (!selectedFlow) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        {t("deployments.selectFlow")}
      </div>
    );
  }

  return (
    <>
      <div className="border-b border-border p-4 text-sm text-muted-foreground">
        {t("deployments.selectVersion")}
      </div>
      <div className="flex flex-1 flex-col overflow-hidden px-4 py-2">
        <h3 className="py-2 text-lg font-semibold">{selectedFlow.name}</h3>
        <div className="flex-1 space-y-3 overflow-y-auto py-3">
          {isLoadingVersions && (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              {t("deployments.loadingVersions")}
            </div>
          )}

          {!isLoadingVersions && versions.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-border bg-muted/30 px-6 py-8 text-center">
              <p className="max-w-sm text-sm text-muted-foreground">
                {t("deployments.deployFromDraft")}
              </p>
              <Button
                onClick={onCreateFromDraft}
                loading={isCreatingDraftVersion}
                disabled={isCreatingDraftVersion}
                ignoreTitleCase
                data-testid="create-version-from-draft"
              >
                {t("deployments.createFromDraft")}
              </Button>
            </div>
          )}

          {!isLoadingVersions &&
            versions.map((version) => {
              const attachmentKey = getSelectedFlowVersionKey(
                selectedFlow.id,
                version.id,
              );
              const isAttachedVersion =
                selectedVersionByFlow.has(attachmentKey);
              const isRemoved = removedFlowIds?.has(attachmentKey) ?? false;
              const connectionNames = (
                attachedConnectionByFlow.get(attachmentKey) ?? []
              )
                .map((cid) => connections.find((c) => c.id === cid)?.name)
                .filter(Boolean);
              return (
                <div
                  key={version.id}
                  data-testid={`version-item-${version.id}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    if (!isRemoved) onAttach(version.id);
                  }}
                  onKeyDown={(event) => {
                    if (
                      (event.key === "Enter" || event.key === " ") &&
                      !isRemoved
                    ) {
                      event.preventDefault();
                      onAttach(version.id);
                    }
                  }}
                  className={cn(
                    "flex w-full items-center gap-4 rounded-xl border p-3 text-left transition-colors",
                    isAttachedVersion && !isRemoved
                      ? "border-accent-blue-foreground bg-accent-blue-muted/40"
                      : isRemoved
                        ? "border-destructive/40 bg-destructive/5 opacity-70"
                        : "border-transparent bg-muted hover:border-border",
                  )}
                >
                  <span className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="flex items-center gap-2 text-sm font-medium leading-tight">
                      <VersionLabel
                        versionTag={version.version_tag}
                        description={version.description}
                        className="truncate"
                      />
                      {isAttachedVersion && !isRemoved && (
                        <Badge
                          variant="secondaryStatic"
                          size="tag"
                          className="shrink-0 bg-accent-blue-muted text-accent-blue-muted-foreground"
                        >
                          {t("deployments.attached")}
                        </Badge>
                      )}
                      {isRemoved && (
                        <Badge
                          variant="secondaryStatic"
                          size="tag"
                          className="shrink-0 bg-destructive/10 text-destructive"
                        >
                          {t("deployments.removed")}
                        </Badge>
                      )}
                    </span>
                    <span className="text-xxs leading-tight text-muted-foreground">
                      {t("deployments.versionCreated", {
                        date: formatDate(version.created_at),
                      })}
                    </span>
                    {connectionNames.length > 0 && !isRemoved && (
                      <span className="truncate text-xxs leading-tight text-muted-foreground">
                        {connectionNames.join(", ")}
                      </span>
                    )}
                  </span>
                  {isRemoved && onUndoRemove ? (
                    <button
                      type="button"
                      className="rounded p-1 text-muted-foreground hover:bg-accent-blue-muted hover:text-accent-blue-muted-foreground"
                      data-testid={`undo-version-${version.id}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onUndoRemove(attachmentKey);
                      }}
                    >
                      <ForwardedIconComponent
                        name="Undo2"
                        className="h-3.5 w-3.5"
                      />
                    </button>
                  ) : isAttachedVersion ? (
                    <>
                      <button
                        type="button"
                        className="rounded px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
                        data-testid={`edit-version-${version.id}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          onAttach(version.id);
                        }}
                      >
                        {t("deployments.edit")}
                      </button>
                      <button
                        type="button"
                        className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                        data-testid={`detach-version-${version.id}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          onDetach(attachmentKey);
                        }}
                      >
                        <ForwardedIconComponent
                          name="X"
                          className="h-3.5 w-3.5"
                        />
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      className="rounded px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
                      data-testid={`attach-version-${version.id}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onAttach(version.id);
                      }}
                    >
                      {t("deployments.attach")}
                    </button>
                  )}
                </div>
              );
            })}
        </div>
      </div>
    </>
  );
});
