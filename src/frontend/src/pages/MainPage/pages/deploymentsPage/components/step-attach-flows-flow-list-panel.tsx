import { memo } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type { FlowType } from "@/types/flow";
import { cn } from "@/utils/utils";
import type { ConnectionItem, SelectedFlowVersion } from "../types";

export const FlowListPanel = memo(function FlowListPanel({
  flows,
  selectedFlowId,
  selectedVersionByFlow,
  attachedConnectionByFlow,
  connections,
  removedFlowIds,
  onSelectFlow,
}: {
  flows: FlowType[];
  selectedFlowId: string | null;
  selectedVersionByFlow: Map<string, SelectedFlowVersion>;
  attachedConnectionByFlow: Map<string, string[]>;
  connections: ConnectionItem[];
  removedFlowIds?: Set<string>;
  onSelectFlow: (flowId: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex w-[280px] flex-shrink-0 flex-col border-r border-border">
      <div className="border-b border-border p-4 text-sm text-muted-foreground">
        {t("deployments.available")}
      </div>
      <div className="flex-1 space-y-1 overflow-y-auto p-2">
        {flows.map((flow) => {
          const entries = Array.from(selectedVersionByFlow.values()).filter(
            (entry) => entry.flowId === flow.id,
          );
          const attached = entries.length > 0;
          const removedEntries = entries.filter(
            (entry) => removedFlowIds?.has(entry.key) ?? false,
          );
          const activeEntries = entries.filter(
            (entry) => !(removedFlowIds?.has(entry.key) ?? false),
          );
          const isRemoved = attached && activeEntries.length === 0;
          const versionLabels = activeEntries.map((entry) => entry.versionTag);
          const connectionIds = activeEntries.flatMap(
            (entry) => attachedConnectionByFlow.get(entry.key) ?? [],
          );
          const connectionNames = connectionIds
            .map((cid) => connections.find((c) => c.id === cid)?.name)
            .filter(Boolean);
          return (
            <div
              key={flow.id}
              role="button"
              tabIndex={0}
              data-testid={`flow-item-${flow.id}`}
              onClick={() => onSelectFlow(flow.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelectFlow(flow.id);
                }
              }}
              className={cn(
                "flex w-full cursor-pointer items-center gap-3 rounded-lg p-3 text-left transition-colors",
                isRemoved && "opacity-50",
                selectedFlowId === flow.id ? "bg-muted" : "hover:bg-muted/60",
              )}
            >
              <div className="flex min-w-0 flex-1 items-center gap-3 text-left">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-border bg-muted">
                  <ForwardedIconComponent
                    name={flow.icon ?? "Workflow"}
                    className="h-4 w-4 text-muted-foreground"
                  />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="truncate text-sm font-semibold">
                      {flow.name}
                    </span>
                    {versionLabels.map((label) => (
                      <Badge
                        key={label}
                        variant="secondaryStatic"
                        size="tag"
                        className="bg-accent-purple-muted text-accent-purple-muted-foreground"
                      >
                        {label}
                      </Badge>
                    ))}
                    {attached && !isRemoved && (
                      <Badge
                        variant="secondaryStatic"
                        size="tag"
                        className="bg-accent-blue-muted text-accent-blue-muted-foreground"
                      >
                        {activeEntries.length === 1
                          ? t("deployments.oneVersion")
                          : t("deployments.manyVersions", {
                              count: activeEntries.length,
                            })}
                      </Badge>
                    )}
                    {isRemoved && (
                      <Badge
                        variant="secondaryStatic"
                        size="tag"
                        className="bg-destructive/10 text-destructive"
                      >
                        {t("deployments.removed")}
                      </Badge>
                    )}
                  </div>
                  {connectionNames.length > 0 && !isRemoved && (
                    <p className="truncate text-xs text-muted-foreground">
                      {connectionNames.join(", ")}
                    </p>
                  )}
                  {removedEntries.length > 0 && !isRemoved && (
                    <p className="truncate text-xs text-muted-foreground">
                      {t("deployments.removedCount", {
                        count: removedEntries.length,
                      })}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});
